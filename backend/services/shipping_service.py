"""
ShippingService — centralized shipping calculation and zone/rule management.

Priority evaluation:
  1. Promotional rules (valid date window, highest priority number first)
  2. Remaining active rules sorted by priority DESC
  3. First matching rule wins.

Zone matching:
  - If a rule has a zone, the delivery address must match at least one area
    in that zone (by city, neighborhood, or zip prefix).
  - Rules without a zone (zone_id=None) are global fallbacks.

RULE: all shipping calculations go through ShippingService.calculate().
      OrderService uses this internally; nothing else should call the DB directly.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.core.events import bus, ShippingCalculated
from backend.core.exceptions import ShippingZoneNotFound, ShippingRuleNotFound
from backend.models.shipping import (
    ShippingRule, ShippingRuleType, ShippingZone, ShippingZoneArea, AreaType,
)
from backend.schemas.shipping import (
    ShippingCalculateIn, ShippingCalculateOut,
    ShippingZoneCreate, ShippingZoneOut,
    ShippingRuleCreate, ShippingRuleOut,
)


class ShippingService:
    """
    Single authority for shipping calculations, zone, and rule management.

    Instantiate per-request:
        svc = ShippingService(db)
    """

    def __init__(self, db: Session):
        self._db = db

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _address_matches_zone(self, zone_id: str, payload: ShippingCalculateIn) -> bool:
        areas: list[ShippingZoneArea] = (
            self._db.query(ShippingZoneArea)
            .filter(ShippingZoneArea.zone_id == zone_id)
            .all()
        )
        for area in areas:
            if area.area_type == AreaType.city:
                if payload.city.lower() == area.value.lower():
                    return True
            elif area.area_type == AreaType.neighborhood:
                if payload.neighborhood and payload.neighborhood.lower() == area.value.lower():
                    return True
            elif area.area_type == AreaType.zip_prefix:
                if payload.zip_code and payload.zip_code.startswith(area.value):
                    return True
        return False

    @staticmethod
    def _apply_rule(rule: ShippingRule, payload: ShippingCalculateIn) -> float:
        if rule.rule_type == ShippingRuleType.fixed:
            return rule.base_price

        if rule.rule_type == ShippingRuleType.free_above:
            if payload.order_subtotal >= (rule.free_above_amount or 0):
                return 0.0
            return rule.base_price

        if rule.rule_type == ShippingRuleType.promotional:
            return rule.base_price

        if rule.rule_type == ShippingRuleType.per_distance:
            # Without real coordinates we fall back to base_price.
            # In a real integration, geocode the address and use Haversine / Google Maps.
            return rule.base_price

        return rule.base_price

    # ── Calculate (used by OrderService and the /shipping/calculate endpoint) ──

    def calculate(
        self,
        payload: ShippingCalculateIn,
        *,
        order_id: str | None = None,
    ) -> ShippingCalculateOut:
        """
        Evaluate all active shipping rules in priority order and return the
        first matching result. Falls back to a R$5 flat fee if nothing matches.

        Publishes ShippingCalculated event after every calculation.
        """
        now = datetime.now(timezone.utc)

        rules: list[ShippingRule] = (
            self._db.query(ShippingRule)
            .filter(ShippingRule.active == True)  # noqa: E712
            .order_by(ShippingRule.priority.desc())
            .all()
        )

        promotional = [
            r for r in rules
            if r.rule_type == ShippingRuleType.promotional
            and (r.valid_from is None or r.valid_from <= now)
            and (r.valid_until is None or r.valid_until >= now)
        ]
        others = [r for r in rules if r.rule_type != ShippingRuleType.promotional]

        matched_rule: ShippingRule | None = None
        for rule in promotional + others:
            if rule.zone_id and not self._address_matches_zone(rule.zone_id, payload):
                continue
            if rule.rule_type == ShippingRuleType.free_above:
                if payload.order_subtotal < (rule.free_above_amount or 0):
                    continue
            matched_rule = rule
            break

        if matched_rule:
            price = self._apply_rule(matched_rule, payload)
            result = ShippingCalculateOut(
                shipping_price=round(price, 2),
                shipping_type=matched_rule.rule_type,
                rule_name=matched_rule.name,
                free=price == 0.0,
            )
        else:
            result = ShippingCalculateOut(
                shipping_price=5.0,
                shipping_type=ShippingRuleType.fixed,
                rule_name="Padrão",
                free=False,
            )

        bus.publish(ShippingCalculated(
            order_id=order_id,
            city=payload.city,
            rule_name=result.rule_name,
            shipping_price=result.shipping_price,
            free=result.free,
        ))

        return result

    # ── Zone CRUD ─────────────────────────────────────────────────────────────

    def list_zones(self) -> list[ShippingZoneOut]:
        zones = self._db.query(ShippingZone).all()
        return [self._zone_to_out(z) for z in zones]

    def create_zone(self, payload: ShippingZoneCreate) -> ShippingZoneOut:
        zone = ShippingZone(
            id=str(uuid.uuid4()),
            name=payload.name,
            active=payload.active,
        )
        self._db.add(zone)
        self._db.flush()

        for area_in in payload.areas:
            self._db.add(ShippingZoneArea(
                id=str(uuid.uuid4()),
                zone_id=zone.id,
                area_type=area_in.area_type,
                value=area_in.value,
            ))

        self._db.commit()
        self._db.refresh(zone)
        return self._zone_to_out(zone)

    def delete_zone(self, zone_id: str) -> None:
        zone = self._db.query(ShippingZone).filter(ShippingZone.id == zone_id).first()
        if not zone:
            raise ShippingZoneNotFound(zone_id)
        self._db.delete(zone)
        self._db.commit()

    # ── Rule CRUD ─────────────────────────────────────────────────────────────

    def list_rules(self) -> list[ShippingRuleOut]:
        rules = self._db.query(ShippingRule).order_by(ShippingRule.priority.desc()).all()
        return [ShippingRuleOut.model_validate(r) for r in rules]

    def create_rule(self, payload: ShippingRuleCreate) -> ShippingRuleOut:
        if payload.zone_id:
            exists = self._db.query(ShippingZone).filter(
                ShippingZone.id == payload.zone_id
            ).first()
            if not exists:
                raise ShippingZoneNotFound(payload.zone_id)

        rule = ShippingRule(
            id=str(uuid.uuid4()),
            **payload.model_dump(exclude_none=True),
        )
        self._db.add(rule)
        self._db.commit()
        self._db.refresh(rule)
        return ShippingRuleOut.model_validate(rule)

    def delete_rule(self, rule_id: str) -> None:
        rule = self._db.query(ShippingRule).filter(ShippingRule.id == rule_id).first()
        if not rule:
            raise ShippingRuleNotFound(rule_id)
        self._db.delete(rule)
        self._db.commit()

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _zone_to_out(zone: ShippingZone) -> ShippingZoneOut:
        return ShippingZoneOut(
            id=zone.id,
            name=zone.name,
            active=zone.active,
            areas=[
                {"id": a.id, "area_type": a.area_type, "value": a.value}
                for a in zone.areas
            ],
        )


# ── Module-level backward compat (existing routes call this) ─────────────────

def calculate_shipping(payload: ShippingCalculateIn, db: Session) -> ShippingCalculateOut:
    return ShippingService(db).calculate(payload)

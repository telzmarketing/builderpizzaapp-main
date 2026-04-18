"""
ShippingService V2 — comprehensive freight calculation and management.

Calculation priority (highest to lowest):
  1. Active ShippingPromotions (sorted by priority DESC, within date window)
  2. Active FreightTypeConfigs (sorted by priority DESC):
       pickup | free | by_neighborhood | by_cep_range |
       by_distance | by_order_value | fixed | scheduled
  3. ExtraRules applied AFTER base fee (surcharges / blocks)
  4. Fallback: ShippingConfig.default_base_fee

Backward compat: legacy ShippingZone / ShippingRule still usable via
  the old calculate() path for zone-based rules.
"""
from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.core.events import bus, ShippingCalculated
from backend.core.exceptions import DomainError

# Legacy models (kept for backward compat)
from backend.models.shipping import (
    ShippingRule, ShippingRuleType, ShippingZone, ShippingZoneArea, AreaType,
)

# V2 models
from backend.models.shipping_v2 import (
    ShippingConfig, FreightTypeConfig,
    ShippingNeighborhood, ShippingCepRange,
    ShippingDistanceRule, ShippingOrderValueTier,
    ShippingPromotion, ShippingExtraRule,
)

# Schemas
from backend.schemas.shipping import (
    ShippingZoneCreate, ShippingZoneOut,
    ShippingRuleCreate, ShippingRuleOut,
)
from backend.schemas.shipping_v2 import (
    ShippingCalculateIn, ShippingCalculateOut,
    ShippingConfigOut, ShippingConfigUpdate,
    FreightTypeConfigOut, FreightTypeConfigUpdate,
    ShippingNeighborhoodCreate, ShippingNeighborhoodUpdate, ShippingNeighborhoodOut,
    ShippingCepRangeCreate, ShippingCepRangeUpdate, ShippingCepRangeOut,
    ShippingDistanceRuleCreate, ShippingDistanceRuleUpdate, ShippingDistanceRuleOut,
    ShippingOrderValueTierCreate, ShippingOrderValueTierUpdate, ShippingOrderValueTierOut,
    ShippingPromotionCreate, ShippingPromotionUpdate, ShippingPromotionOut,
    ShippingExtraRuleCreate, ShippingExtraRuleUpdate, ShippingExtraRuleOut,
)

_FREIGHT_TYPES = [
    "fixed", "by_neighborhood", "by_cep_range",
    "by_distance", "by_order_value", "free", "pickup", "scheduled",
]


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in km between two coordinates."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _strip_cep(cep: str) -> str:
    return cep.replace("-", "").replace(".", "").strip()


class ShippingService:
    def __init__(self, db: Session):
        self._db = db

    # ─── Config ──────────────────────────────────────────────────────────────

    def get_config(self) -> ShippingConfig:
        cfg = self._db.query(ShippingConfig).filter(ShippingConfig.id == "default").first()
        if not cfg:
            cfg = ShippingConfig(id="default")
            self._db.add(cfg)
            self._db.commit()
            self._db.refresh(cfg)
        return cfg

    def update_config(self, payload: ShippingConfigUpdate) -> ShippingConfigOut:
        cfg = self.get_config()
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(cfg, field, value)
        self._db.commit()
        self._db.refresh(cfg)
        return ShippingConfigOut.model_validate(cfg)

    # ─── FreightTypeConfig ────────────────────────────────────────────────────

    def list_type_configs(self) -> list[FreightTypeConfigOut]:
        self._ensure_type_configs()
        rows = self._db.query(FreightTypeConfig).order_by(FreightTypeConfig.priority.desc()).all()
        return [FreightTypeConfigOut.model_validate(r) for r in rows]

    def update_type_config(self, freight_type: str, payload: FreightTypeConfigUpdate) -> FreightTypeConfigOut:
        self._ensure_type_configs()
        row = self._db.query(FreightTypeConfig).filter(FreightTypeConfig.freight_type == freight_type).first()
        if not row:
            raise DomainError(f"Tipo de frete '{freight_type}' não encontrado.", "FreightTypeNotFound", 404)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(row, field, value)
        self._db.commit()
        self._db.refresh(row)
        return FreightTypeConfigOut.model_validate(row)

    def _ensure_type_configs(self):
        for ft in _FREIGHT_TYPES:
            exists = self._db.query(FreightTypeConfig).filter(FreightTypeConfig.freight_type == ft).first()
            if not exists:
                self._db.add(FreightTypeConfig(id=str(uuid.uuid4()), freight_type=ft, active=False, priority=0))
        self._db.commit()

    # ─── Neighborhoods ────────────────────────────────────────────────────────

    def list_neighborhoods(self) -> list[ShippingNeighborhoodOut]:
        rows = self._db.query(ShippingNeighborhood).order_by(ShippingNeighborhood.priority.desc(), ShippingNeighborhood.name).all()
        return [ShippingNeighborhoodOut.model_validate(r) for r in rows]

    def create_neighborhood(self, payload: ShippingNeighborhoodCreate) -> ShippingNeighborhoodOut:
        row = ShippingNeighborhood(id=str(uuid.uuid4()), **payload.model_dump())
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return ShippingNeighborhoodOut.model_validate(row)

    def update_neighborhood(self, nid: str, payload: ShippingNeighborhoodUpdate) -> ShippingNeighborhoodOut:
        row = self._db.query(ShippingNeighborhood).filter(ShippingNeighborhood.id == nid).first()
        if not row:
            raise DomainError("Bairro não encontrado.", "NeighborhoodNotFound", 404)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(row, field, value)
        self._db.commit()
        self._db.refresh(row)
        return ShippingNeighborhoodOut.model_validate(row)

    def delete_neighborhood(self, nid: str) -> None:
        row = self._db.query(ShippingNeighborhood).filter(ShippingNeighborhood.id == nid).first()
        if not row:
            raise DomainError("Bairro não encontrado.", "NeighborhoodNotFound", 404)
        self._db.delete(row)
        self._db.commit()

    # ─── CEP Ranges ──────────────────────────────────────────────────────────

    def list_cep_ranges(self) -> list[ShippingCepRangeOut]:
        rows = self._db.query(ShippingCepRange).order_by(ShippingCepRange.priority.desc()).all()
        return [ShippingCepRangeOut.model_validate(r) for r in rows]

    def create_cep_range(self, payload: ShippingCepRangeCreate) -> ShippingCepRangeOut:
        row = ShippingCepRange(id=str(uuid.uuid4()), **payload.model_dump())
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return ShippingCepRangeOut.model_validate(row)

    def update_cep_range(self, rid: str, payload: ShippingCepRangeUpdate) -> ShippingCepRangeOut:
        row = self._db.query(ShippingCepRange).filter(ShippingCepRange.id == rid).first()
        if not row:
            raise DomainError("Faixa de CEP não encontrada.", "CepRangeNotFound", 404)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(row, field, value)
        self._db.commit()
        self._db.refresh(row)
        return ShippingCepRangeOut.model_validate(row)

    def delete_cep_range(self, rid: str) -> None:
        row = self._db.query(ShippingCepRange).filter(ShippingCepRange.id == rid).first()
        if not row:
            raise DomainError("Faixa de CEP não encontrada.", "CepRangeNotFound", 404)
        self._db.delete(row)
        self._db.commit()

    # ─── Distance Rules ───────────────────────────────────────────────────────

    def list_distance_rules(self) -> list[ShippingDistanceRuleOut]:
        rows = self._db.query(ShippingDistanceRule).order_by(ShippingDistanceRule.km_min).all()
        return [ShippingDistanceRuleOut.model_validate(r) for r in rows]

    def create_distance_rule(self, payload: ShippingDistanceRuleCreate) -> ShippingDistanceRuleOut:
        row = ShippingDistanceRule(id=str(uuid.uuid4()), **payload.model_dump())
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return ShippingDistanceRuleOut.model_validate(row)

    def update_distance_rule(self, rid: str, payload: ShippingDistanceRuleUpdate) -> ShippingDistanceRuleOut:
        row = self._db.query(ShippingDistanceRule).filter(ShippingDistanceRule.id == rid).first()
        if not row:
            raise DomainError("Regra de distância não encontrada.", "DistanceRuleNotFound", 404)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(row, field, value)
        self._db.commit()
        self._db.refresh(row)
        return ShippingDistanceRuleOut.model_validate(row)

    def delete_distance_rule(self, rid: str) -> None:
        row = self._db.query(ShippingDistanceRule).filter(ShippingDistanceRule.id == rid).first()
        if not row:
            raise DomainError("Regra de distância não encontrada.", "DistanceRuleNotFound", 404)
        self._db.delete(row)
        self._db.commit()

    # ─── Order Value Tiers ────────────────────────────────────────────────────

    def list_order_value_tiers(self) -> list[ShippingOrderValueTierOut]:
        rows = self._db.query(ShippingOrderValueTier).order_by(ShippingOrderValueTier.order_value_min).all()
        return [ShippingOrderValueTierOut.model_validate(r) for r in rows]

    def create_order_value_tier(self, payload: ShippingOrderValueTierCreate) -> ShippingOrderValueTierOut:
        row = ShippingOrderValueTier(id=str(uuid.uuid4()), **payload.model_dump())
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return ShippingOrderValueTierOut.model_validate(row)

    def update_order_value_tier(self, tid: str, payload: ShippingOrderValueTierUpdate) -> ShippingOrderValueTierOut:
        row = self._db.query(ShippingOrderValueTier).filter(ShippingOrderValueTier.id == tid).first()
        if not row:
            raise DomainError("Faixa de valor não encontrada.", "ValueTierNotFound", 404)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(row, field, value)
        self._db.commit()
        self._db.refresh(row)
        return ShippingOrderValueTierOut.model_validate(row)

    def delete_order_value_tier(self, tid: str) -> None:
        row = self._db.query(ShippingOrderValueTier).filter(ShippingOrderValueTier.id == tid).first()
        if not row:
            raise DomainError("Faixa de valor não encontrada.", "ValueTierNotFound", 404)
        self._db.delete(row)
        self._db.commit()

    # ─── Promotions ───────────────────────────────────────────────────────────

    def list_promotions(self) -> list[ShippingPromotionOut]:
        rows = self._db.query(ShippingPromotion).order_by(ShippingPromotion.priority.desc()).all()
        return [ShippingPromotionOut.model_validate(r) for r in rows]

    def create_promotion(self, payload: ShippingPromotionCreate) -> ShippingPromotionOut:
        row = ShippingPromotion(id=str(uuid.uuid4()), **payload.model_dump())
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return ShippingPromotionOut.model_validate(row)

    def update_promotion(self, pid: str, payload: ShippingPromotionUpdate) -> ShippingPromotionOut:
        row = self._db.query(ShippingPromotion).filter(ShippingPromotion.id == pid).first()
        if not row:
            raise DomainError("Promoção não encontrada.", "PromotionNotFound", 404)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(row, field, value)
        self._db.commit()
        self._db.refresh(row)
        return ShippingPromotionOut.model_validate(row)

    def delete_promotion(self, pid: str) -> None:
        row = self._db.query(ShippingPromotion).filter(ShippingPromotion.id == pid).first()
        if not row:
            raise DomainError("Promoção não encontrada.", "PromotionNotFound", 404)
        self._db.delete(row)
        self._db.commit()

    # ─── Extra Rules ─────────────────────────────────────────────────────────

    def list_extra_rules(self) -> list[ShippingExtraRuleOut]:
        rows = self._db.query(ShippingExtraRule).order_by(ShippingExtraRule.priority.desc()).all()
        return [ShippingExtraRuleOut.model_validate(r) for r in rows]

    def create_extra_rule(self, payload: ShippingExtraRuleCreate) -> ShippingExtraRuleOut:
        row = ShippingExtraRule(id=str(uuid.uuid4()), **payload.model_dump())
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return ShippingExtraRuleOut.model_validate(row)

    def update_extra_rule(self, rid: str, payload: ShippingExtraRuleUpdate) -> ShippingExtraRuleOut:
        row = self._db.query(ShippingExtraRule).filter(ShippingExtraRule.id == rid).first()
        if not row:
            raise DomainError("Regra extra não encontrada.", "ExtraRuleNotFound", 404)
        for field, value in payload.model_dump(exclude_none=True).items():
            setattr(row, field, value)
        self._db.commit()
        self._db.refresh(row)
        return ShippingExtraRuleOut.model_validate(row)

    def delete_extra_rule(self, rid: str) -> None:
        row = self._db.query(ShippingExtraRule).filter(ShippingExtraRule.id == rid).first()
        if not row:
            raise DomainError("Regra extra não encontrada.", "ExtraRuleNotFound", 404)
        self._db.delete(row)
        self._db.commit()

    # ─── Calculate ────────────────────────────────────────────────────────────

    def calculate(self, payload: ShippingCalculateIn, *, order_id: str | None = None) -> ShippingCalculateOut:
        cfg = self.get_config()
        now = datetime.now(timezone.utc)
        nbhd_lower = (payload.neighborhood or "").lower().strip()
        city_lower = (payload.city or "").lower().strip()
        cep_clean = _strip_cep(payload.zip_code or "")

        # ── 1. Check if delivery is enabled ──────────────────────────────────
        if not cfg.delivery_enabled and not payload.is_pickup:
            result = ShippingCalculateOut(
                shipping_price=0.0,
                shipping_type="unavailable",
                rule_name="Entrega indisponível",
                free=False,
                estimated_time=0,
                available=False,
                message=cfg.unavailable_message,
            )
            self._publish(result, payload, order_id)
            return result

        # ── 2. Pickup ────────────────────────────────────────────────────────
        if payload.is_pickup and cfg.pickup_enabled:
            result = ShippingCalculateOut(
                shipping_price=0.0,
                shipping_type="pickup",
                rule_name=cfg.pickup_message,
                free=True,
                estimated_time=15,
                available=True,
                message=cfg.pickup_message,
            )
            self._publish(result, payload, order_id)
            return result

        # ── 3. Region blocks (extra rules) ───────────────────────────────────
        blocks = (
            self._db.query(ShippingExtraRule)
            .filter(ShippingExtraRule.active == True, ShippingExtraRule.rule_type == "region_block")
            .all()
        )
        for block in blocks:
            cond = block.condition.lower().strip()
            if cond and (cond in nbhd_lower or cond in city_lower):
                msg = block.message or cfg.unavailable_message
                result = ShippingCalculateOut(
                    shipping_price=0.0,
                    shipping_type="blocked",
                    rule_name=block.name,
                    free=False,
                    estimated_time=0,
                    available=False,
                    message=msg,
                )
                self._publish(result, payload, order_id)
                return result

        # ── 4. Check min order value ─────────────────────────────────────────
        if cfg.min_order_value > 0 and payload.order_subtotal < cfg.min_order_value:
            result = ShippingCalculateOut(
                shipping_price=0.0,
                shipping_type="min_order",
                rule_name="Pedido mínimo não atingido",
                free=False,
                estimated_time=0,
                available=False,
                message=f"Pedido mínimo de R$ {cfg.min_order_value:.2f} não atingido.",
            )
            self._publish(result, payload, order_id)
            return result

        # ── 5. Promotions (highest priority) ─────────────────────────────────
        promos = (
            self._db.query(ShippingPromotion)
            .filter(ShippingPromotion.active == True)
            .order_by(ShippingPromotion.priority.desc())
            .all()
        )
        for promo in promos:
            if promo.valid_from and promo.valid_from > now:
                continue
            if promo.valid_until and promo.valid_until < now:
                continue
            matched = False
            if promo.promo_type == "free_above_value":
                matched = payload.order_subtotal >= promo.min_order_value
            elif promo.promo_type == "promotional_period":
                matched = True
            elif promo.promo_type == "free_by_neighborhood":
                try:
                    nbhd_ids = json.loads(promo.neighborhood_ids or "[]")
                except Exception:
                    nbhd_ids = []
                if nbhd_ids and nbhd_lower:
                    nbhds = self._db.query(ShippingNeighborhood).filter(ShippingNeighborhood.id.in_(nbhd_ids)).all()
                    for n in nbhds:
                        if n.name.lower() == nbhd_lower:
                            matched = True
                            break
            elif promo.promo_type == "free_campaign":
                matched = True
            if matched:
                price = promo.shipping_value
                result = ShippingCalculateOut(
                    shipping_price=round(price, 2),
                    shipping_type="promotional",
                    rule_name=promo.name,
                    free=price == 0.0,
                    estimated_time=cfg.default_estimated_time,
                    available=True,
                    message="🎉 " + promo.name if price == 0.0 else "",
                )
                result = self._apply_extra_surcharges(result, payload, cfg, now)
                self._publish(result, payload, order_id)
                return result

        # ── 6. Freight type rules (priority order) ────────────────────────────
        self._ensure_type_configs()
        type_cfgs = (
            self._db.query(FreightTypeConfig)
            .filter(FreightTypeConfig.active == True)
            .order_by(FreightTypeConfig.priority.desc())
            .all()
        )

        for tc in type_cfgs:
            result = None

            if tc.freight_type == "free":
                if tc.free_above_value == 0 or payload.order_subtotal >= tc.free_above_value:
                    result = ShippingCalculateOut(
                        shipping_price=0.0,
                        shipping_type="free",
                        rule_name="Frete Grátis",
                        free=True,
                        estimated_time=cfg.default_estimated_time,
                        available=True,
                        message="🎉 Frete grátis!",
                    )

            elif tc.freight_type == "fixed":
                result = ShippingCalculateOut(
                    shipping_price=round(tc.fixed_value, 2),
                    shipping_type="fixed",
                    rule_name="Frete Fixo",
                    free=tc.fixed_value == 0.0,
                    estimated_time=cfg.default_estimated_time,
                    available=True,
                )

            elif tc.freight_type == "by_neighborhood" and nbhd_lower:
                nbhds = (
                    self._db.query(ShippingNeighborhood)
                    .filter(ShippingNeighborhood.active == True)
                    .order_by(ShippingNeighborhood.priority.desc())
                    .all()
                )
                for n in nbhds:
                    if n.name.lower() == nbhd_lower:
                        if n.min_order_value > 0 and payload.order_subtotal < n.min_order_value:
                            continue
                        price = 0.0 if n.is_free else n.shipping_value
                        result = ShippingCalculateOut(
                            shipping_price=round(price, 2),
                            shipping_type="by_neighborhood",
                            rule_name=f"Bairro: {n.name}",
                            free=n.is_free or price == 0.0,
                            estimated_time=n.estimated_time_min,
                            available=True,
                            message=n.notes or "",
                        )
                        break

            elif tc.freight_type == "by_cep_range" and cep_clean:
                ranges = (
                    self._db.query(ShippingCepRange)
                    .filter(ShippingCepRange.active == True)
                    .order_by(ShippingCepRange.priority.desc())
                    .all()
                )
                for r in ranges:
                    cs = _strip_cep(r.cep_start)
                    ce = _strip_cep(r.cep_end)
                    if cs <= cep_clean <= ce:
                        if r.min_order_value > 0 and payload.order_subtotal < r.min_order_value:
                            continue
                        result = ShippingCalculateOut(
                            shipping_price=round(r.shipping_value, 2),
                            shipping_type="by_cep_range",
                            rule_name=r.name or f"CEP {r.cep_start}–{r.cep_end}",
                            free=r.shipping_value == 0.0,
                            estimated_time=r.estimated_time_min,
                            available=True,
                        )
                        break

            elif tc.freight_type == "by_distance":
                km = payload.distance_km
                if km is None:
                    # Try Haversine if store coords known
                    km = None  # geocoding would go here
                if km is not None:
                    d_rules = (
                        self._db.query(ShippingDistanceRule)
                        .filter(ShippingDistanceRule.active == True)
                        .order_by(ShippingDistanceRule.km_min)
                        .all()
                    )
                    for dr in d_rules:
                        if dr.km_min <= km <= dr.km_max:
                            raw = dr.base_fee + dr.fee_per_km * km
                            price = max(dr.min_fee, min(dr.max_fee, raw))
                            result = ShippingCalculateOut(
                                shipping_price=round(price, 2),
                                shipping_type="by_distance",
                                rule_name=dr.name or f"{dr.km_min:.0f}–{dr.km_max:.0f} km",
                                free=price == 0.0,
                                estimated_time=dr.estimated_time_min,
                                available=True,
                            )
                            break

            elif tc.freight_type == "by_order_value":
                tiers = (
                    self._db.query(ShippingOrderValueTier)
                    .filter(ShippingOrderValueTier.active == True)
                    .order_by(ShippingOrderValueTier.order_value_min.desc())
                    .all()
                )
                for tier in tiers:
                    if payload.order_subtotal >= tier.order_value_min:
                        if tier.order_value_max is not None and payload.order_subtotal > tier.order_value_max:
                            continue
                        price = 0.0 if tier.is_free else tier.shipping_value
                        result = ShippingCalculateOut(
                            shipping_price=round(price, 2),
                            shipping_type="by_order_value",
                            rule_name=tier.name or f"Pedido acima de R$ {tier.order_value_min:.2f}",
                            free=tier.is_free or price == 0.0,
                            estimated_time=cfg.default_estimated_time,
                            available=True,
                        )
                        break

            elif tc.freight_type == "scheduled" and payload.is_scheduled:
                base = cfg.default_base_fee
                surcharge = tc.scheduled_surcharge
                if tc.scheduled_surcharge_type == "percentage":
                    surcharge = base * (tc.scheduled_surcharge / 100)
                price = base + surcharge
                result = ShippingCalculateOut(
                    shipping_price=round(price, 2),
                    shipping_type="scheduled",
                    rule_name="Entrega Agendada",
                    free=False,
                    estimated_time=cfg.default_estimated_time,
                    available=True,
                )

            if result is not None:
                result = self._apply_extra_surcharges(result, payload, cfg, now)
                self._publish(result, payload, order_id)
                return result

        # ── 7. Fallback ───────────────────────────────────────────────────────
        result = ShippingCalculateOut(
            shipping_price=round(cfg.default_base_fee, 2),
            shipping_type="fixed",
            rule_name="Taxa padrão",
            free=cfg.default_base_fee == 0.0,
            estimated_time=cfg.default_estimated_time,
            available=True,
        )
        result = self._apply_extra_surcharges(result, payload, cfg, now)
        self._publish(result, payload, order_id)
        return result

    # ─── Internal helpers ─────────────────────────────────────────────────────

    def _apply_extra_surcharges(
        self,
        base: ShippingCalculateOut,
        payload: ShippingCalculateIn,
        cfg: ShippingConfig,
        now: datetime,
    ) -> ShippingCalculateOut:
        if not base.available:
            return base
        extras = (
            self._db.query(ShippingExtraRule)
            .filter(ShippingExtraRule.active == True, ShippingExtraRule.rule_type != "region_block")
            .order_by(ShippingExtraRule.priority.desc())
            .all()
        )
        total_surcharge = 0.0
        nbhd_lower = (payload.neighborhood or "").lower().strip()
        city_lower = (payload.city or "").lower().strip()
        current_time = now.strftime("%H:%M")

        for rule in extras:
            if rule.rule_type == "time_surcharge":
                if rule.time_start and rule.time_end:
                    if rule.time_start <= current_time <= rule.time_end:
                        total_surcharge += self._surcharge_value(rule, base.shipping_price)
            elif rule.rule_type == "demand_surcharge":
                total_surcharge += self._surcharge_value(rule, base.shipping_price)
            elif rule.rule_type == "area_surcharge":
                cond = rule.condition.lower().strip()
                if cond and (cond in nbhd_lower or cond in city_lower):
                    total_surcharge += self._surcharge_value(rule, base.shipping_price)
            elif rule.rule_type == "scheduled_surcharge" and payload.is_scheduled:
                total_surcharge += self._surcharge_value(rule, base.shipping_price)

        if total_surcharge > 0:
            new_price = round(base.shipping_price + total_surcharge, 2)
            return ShippingCalculateOut(
                shipping_price=new_price,
                shipping_type=base.shipping_type,
                rule_name=base.rule_name,
                free=new_price == 0.0,
                estimated_time=base.estimated_time,
                available=base.available,
                message=base.message,
            )
        return base

    @staticmethod
    def _surcharge_value(rule: ShippingExtraRule, base_price: float) -> float:
        if rule.value_type == "percentage":
            return base_price * (rule.value / 100)
        return rule.value

    def _publish(self, result: ShippingCalculateOut, payload: ShippingCalculateIn, order_id: str | None):
        try:
            bus.publish(ShippingCalculated(
                order_id=order_id,
                city=payload.city,
                rule_name=result.rule_name,
                shipping_price=result.shipping_price,
                free=result.free,
            ))
        except Exception:
            pass

    # ─── Legacy zone/rule CRUD (backward compat) ──────────────────────────────

    def list_zones(self) -> list[ShippingZoneOut]:
        zones = self._db.query(ShippingZone).all()
        return [self._zone_to_out(z) for z in zones]

    def create_zone(self, payload: ShippingZoneCreate) -> ShippingZoneOut:
        from backend.core.exceptions import ShippingZoneNotFound
        zone = ShippingZone(id=str(uuid.uuid4()), name=payload.name, active=payload.active)
        self._db.add(zone)
        self._db.flush()
        for area_in in payload.areas:
            self._db.add(ShippingZoneArea(id=str(uuid.uuid4()), zone_id=zone.id, area_type=area_in.area_type, value=area_in.value))
        self._db.commit()
        self._db.refresh(zone)
        return self._zone_to_out(zone)

    def delete_zone(self, zone_id: str) -> None:
        from backend.core.exceptions import ShippingZoneNotFound
        zone = self._db.query(ShippingZone).filter(ShippingZone.id == zone_id).first()
        if not zone:
            raise ShippingZoneNotFound(zone_id)
        self._db.delete(zone)
        self._db.commit()

    def list_rules(self) -> list[ShippingRuleOut]:
        rules = self._db.query(ShippingRule).order_by(ShippingRule.priority.desc()).all()
        return [ShippingRuleOut.model_validate(r) for r in rules]

    def create_rule(self, payload: ShippingRuleCreate) -> ShippingRuleOut:
        from backend.core.exceptions import ShippingZoneNotFound
        if payload.zone_id:
            if not self._db.query(ShippingZone).filter(ShippingZone.id == payload.zone_id).first():
                raise ShippingZoneNotFound(payload.zone_id)
        rule = ShippingRule(id=str(uuid.uuid4()), **payload.model_dump(exclude_none=True))
        self._db.add(rule)
        self._db.commit()
        self._db.refresh(rule)
        return ShippingRuleOut.model_validate(rule)

    def delete_rule(self, rule_id: str) -> None:
        from backend.core.exceptions import ShippingRuleNotFound
        rule = self._db.query(ShippingRule).filter(ShippingRule.id == rule_id).first()
        if not rule:
            raise ShippingRuleNotFound(rule_id)
        self._db.delete(rule)
        self._db.commit()

    @staticmethod
    def _zone_to_out(zone: ShippingZone) -> ShippingZoneOut:
        return ShippingZoneOut(
            id=zone.id, name=zone.name, active=zone.active,
            areas=[{"id": a.id, "area_type": a.area_type, "value": a.value} for a in zone.areas],
        )


# ── Module-level backward compat ─────────────────────────────────────────────

def calculate_shipping(payload: ShippingCalculateIn, db: Session) -> ShippingCalculateOut:
    return ShippingService(db).calculate(payload)

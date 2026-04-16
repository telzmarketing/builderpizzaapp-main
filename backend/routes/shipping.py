"""
Shipping endpoints.

All business logic lives in ShippingService.
The /calculate endpoint is called internally by OrderService at checkout
and can also be called directly by the front-end to show the shipping
fee preview before the user completes the order.

Endpoints:
  POST /shipping/calculate      → calculate shipping for an address + subtotal
  GET  /shipping/zones          → list all zones
  POST /shipping/zones          → create zone
  DELETE /shipping/zones/{id}   → delete zone
  GET  /shipping/rules          → list all rules (priority order)
  POST /shipping/rules          → create rule
  DELETE /shipping/rules/{id}   → delete rule
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import ok, created, no_content, err
from backend.database import get_db
from backend.schemas.shipping import (
    ShippingCalculateIn,
    ShippingZoneCreate,
    ShippingRuleCreate,
)
from backend.services.shipping_service import ShippingService

router = APIRouter(prefix="/shipping", tags=["shipping"])


# ── Calculate ─────────────────────────────────────────────────────────────────

@router.post("/calculate")
def calculate_shipping(body: ShippingCalculateIn, db: Session = Depends(get_db)):
    """
    Calculate the shipping fee for a delivery address and order subtotal.

    Priority evaluation (highest first):
      1. Promotional rules (within valid date window)
      2. All other active rules, sorted by priority DESC
      First matching rule wins.

    Zone matching: city / neighborhood / zip_code prefix.
    Fallback: R$5,00 flat fee if no rule matches.

    Shipping fee is snapshotted into the order at checkout — future rule
    changes do NOT affect existing orders.
    """
    try:
        result = ShippingService(db).calculate(body)
        return ok(result)
    except DomainError as exc:
        return err(exc)


# ── Zones ─────────────────────────────────────────────────────────────────────

@router.get("/zones")
def list_zones(db: Session = Depends(get_db)):
    """List all shipping zones with their areas."""
    try:
        return ok(ShippingService(db).list_zones())
    except DomainError as exc:
        return err(exc)


@router.post("/zones", status_code=201)
def create_zone(body: ShippingZoneCreate, db: Session = Depends(get_db)):
    """Create a shipping zone with its coverage areas (city / neighborhood / zip prefix)."""
    try:
        zone = ShippingService(db).create_zone(body)
        return created(zone, "Zona de frete criada.")
    except DomainError as exc:
        return err(exc)


@router.delete("/zones/{zone_id}", status_code=204)
def delete_zone(zone_id: str, db: Session = Depends(get_db)):
    """Delete a shipping zone and all its areas."""
    try:
        ShippingService(db).delete_zone(zone_id)
        return no_content()
    except DomainError as exc:
        return err(exc)


# ── Rules ─────────────────────────────────────────────────────────────────────

@router.get("/rules")
def list_rules(db: Session = Depends(get_db)):
    """List all shipping rules ordered by priority (highest first)."""
    try:
        return ok(ShippingService(db).list_rules())
    except DomainError as exc:
        return err(exc)


@router.post("/rules", status_code=201)
def create_rule(body: ShippingRuleCreate, db: Session = Depends(get_db)):
    """
    Create a shipping rule.

    Rule types:
      fixed        → flat fee (base_price)
      free_above   → free when subtotal ≥ free_above_amount, else base_price
      per_distance → base_price (geocode integration pending)
      promotional  → base_price, evaluated first within valid_from/valid_until window
    """
    try:
        rule = ShippingService(db).create_rule(body)
        return created(rule, "Regra de frete criada.")
    except DomainError as exc:
        return err(exc)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: str, db: Session = Depends(get_db)):
    """Delete a shipping rule."""
    try:
        ShippingService(db).delete_rule(rule_id)
        return no_content()
    except DomainError as exc:
        return err(exc)

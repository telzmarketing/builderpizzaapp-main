"""
Shipping routes — V2 comprehensive + legacy V1 endpoints.

V2 endpoints (new):
  GET/PUT  /shipping/config
  GET/PUT  /shipping/types/{freight_type}
  GET      /shipping/types
  CRUD     /shipping/neighborhoods
  CRUD     /shipping/cep-ranges
  CRUD     /shipping/distance-rules
  CRUD     /shipping/order-value-tiers
  CRUD     /shipping/promotions
  CRUD     /shipping/extra-rules

Legacy endpoints (kept for backward compat):
  POST     /shipping/calculate
  GET/POST/DELETE  /shipping/zones
  GET/POST/DELETE  /shipping/rules
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import ok, created, no_content, err
from backend.database import get_db
from backend.routes.admin_auth import get_current_admin

# Legacy schemas
from backend.schemas.shipping import ShippingZoneCreate, ShippingRuleCreate

# V2 schemas
from backend.schemas.shipping_v2 import (
    ShippingCalculateIn,
    ShippingConfigUpdate,
    FreightTypeConfigUpdate,
    ShippingNeighborhoodCreate, ShippingNeighborhoodUpdate,
    ShippingCepRangeCreate, ShippingCepRangeUpdate,
    ShippingDistanceRuleCreate, ShippingDistanceRuleUpdate,
    ShippingOrderValueTierCreate, ShippingOrderValueTierUpdate,
    ShippingPromotionCreate, ShippingPromotionUpdate,
    ShippingExtraRuleCreate, ShippingExtraRuleUpdate,
)
from backend.services.shipping_service import ShippingService

router = APIRouter(prefix="/shipping", tags=["shipping"])


# ─── Calculate (V2 — enhanced output) ────────────────────────────────────────

@router.post("/calculate")
def calculate_shipping(body: ShippingCalculateIn, db: Session = Depends(get_db)):
    """
    Calculate shipping fee with full V2 rule evaluation.
    Returns enhanced ShippingCalculateOut with estimated_time, available, message.
    """
    try:
        result = ShippingService(db).calculate(body)
        return ok(result)
    except DomainError as exc:
        return err(exc)


# ─── Config ───────────────────────────────────────────────────────────────────

@router.get("/config")
def get_config(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return ok(ShippingService(db).get_config())
    except DomainError as exc:
        return err(exc)


@router.put("/config")
def update_config(body: ShippingConfigUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return ok(ShippingService(db).update_config(body))
    except DomainError as exc:
        return err(exc)


# ─── Freight Type Configs ─────────────────────────────────────────────────────

@router.get("/types")
def list_type_configs(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return ok(ShippingService(db).list_type_configs())
    except DomainError as exc:
        return err(exc)


@router.put("/types/{freight_type}")
def update_type_config(freight_type: str, body: FreightTypeConfigUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return ok(ShippingService(db).update_type_config(freight_type, body))
    except DomainError as exc:
        return err(exc)


# ─── Neighborhoods ────────────────────────────────────────────────────────────

@router.get("/neighborhoods")
def list_neighborhoods(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return ok(ShippingService(db).list_neighborhoods())
    except DomainError as exc:
        return err(exc)


@router.post("/neighborhoods", status_code=201)
def create_neighborhood(body: ShippingNeighborhoodCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return created(ShippingService(db).create_neighborhood(body), "Bairro criado.")
    except DomainError as exc:
        return err(exc)


@router.put("/neighborhoods/{nid}")
def update_neighborhood(nid: str, body: ShippingNeighborhoodUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return ok(ShippingService(db).update_neighborhood(nid, body))
    except DomainError as exc:
        return err(exc)


@router.delete("/neighborhoods/{nid}", status_code=204)
def delete_neighborhood(nid: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        ShippingService(db).delete_neighborhood(nid)
        return no_content()
    except DomainError as exc:
        return err(exc)


# ─── CEP Ranges ───────────────────────────────────────────────────────────────

@router.get("/cep-ranges")
def list_cep_ranges(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return ok(ShippingService(db).list_cep_ranges())
    except DomainError as exc:
        return err(exc)


@router.post("/cep-ranges", status_code=201)
def create_cep_range(body: ShippingCepRangeCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return created(ShippingService(db).create_cep_range(body), "Faixa de CEP criada.")
    except DomainError as exc:
        return err(exc)


@router.put("/cep-ranges/{rid}")
def update_cep_range(rid: str, body: ShippingCepRangeUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return ok(ShippingService(db).update_cep_range(rid, body))
    except DomainError as exc:
        return err(exc)


@router.delete("/cep-ranges/{rid}", status_code=204)
def delete_cep_range(rid: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        ShippingService(db).delete_cep_range(rid)
        return no_content()
    except DomainError as exc:
        return err(exc)


# ─── Distance Rules ───────────────────────────────────────────────────────────

@router.get("/distance-rules")
def list_distance_rules(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return ok(ShippingService(db).list_distance_rules())
    except DomainError as exc:
        return err(exc)


@router.post("/distance-rules", status_code=201)
def create_distance_rule(body: ShippingDistanceRuleCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return created(ShippingService(db).create_distance_rule(body), "Regra de distância criada.")
    except DomainError as exc:
        return err(exc)


@router.put("/distance-rules/{rid}")
def update_distance_rule(rid: str, body: ShippingDistanceRuleUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return ok(ShippingService(db).update_distance_rule(rid, body))
    except DomainError as exc:
        return err(exc)


@router.delete("/distance-rules/{rid}", status_code=204)
def delete_distance_rule(rid: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        ShippingService(db).delete_distance_rule(rid)
        return no_content()
    except DomainError as exc:
        return err(exc)


# ─── Order Value Tiers ────────────────────────────────────────────────────────

@router.get("/order-value-tiers")
def list_order_value_tiers(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return ok(ShippingService(db).list_order_value_tiers())
    except DomainError as exc:
        return err(exc)


@router.post("/order-value-tiers", status_code=201)
def create_order_value_tier(body: ShippingOrderValueTierCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return created(ShippingService(db).create_order_value_tier(body), "Faixa criada.")
    except DomainError as exc:
        return err(exc)


@router.put("/order-value-tiers/{tid}")
def update_order_value_tier(tid: str, body: ShippingOrderValueTierUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return ok(ShippingService(db).update_order_value_tier(tid, body))
    except DomainError as exc:
        return err(exc)


@router.delete("/order-value-tiers/{tid}", status_code=204)
def delete_order_value_tier(tid: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        ShippingService(db).delete_order_value_tier(tid)
        return no_content()
    except DomainError as exc:
        return err(exc)


# ─── Promotions ───────────────────────────────────────────────────────────────

@router.get("/promotions")
def list_promotions(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return ok(ShippingService(db).list_promotions())
    except DomainError as exc:
        return err(exc)


@router.post("/promotions", status_code=201)
def create_promotion(body: ShippingPromotionCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return created(ShippingService(db).create_promotion(body), "Promoção criada.")
    except DomainError as exc:
        return err(exc)


@router.put("/promotions/{pid}")
def update_promotion(pid: str, body: ShippingPromotionUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return ok(ShippingService(db).update_promotion(pid, body))
    except DomainError as exc:
        return err(exc)


@router.delete("/promotions/{pid}", status_code=204)
def delete_promotion(pid: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        ShippingService(db).delete_promotion(pid)
        return no_content()
    except DomainError as exc:
        return err(exc)


# ─── Extra Rules ──────────────────────────────────────────────────────────────

@router.get("/extra-rules")
def list_extra_rules(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return ok(ShippingService(db).list_extra_rules())
    except DomainError as exc:
        return err(exc)


@router.post("/extra-rules", status_code=201)
def create_extra_rule(body: ShippingExtraRuleCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return created(ShippingService(db).create_extra_rule(body), "Regra extra criada.")
    except DomainError as exc:
        return err(exc)


@router.put("/extra-rules/{rid}")
def update_extra_rule(rid: str, body: ShippingExtraRuleUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return ok(ShippingService(db).update_extra_rule(rid, body))
    except DomainError as exc:
        return err(exc)


@router.delete("/extra-rules/{rid}", status_code=204)
def delete_extra_rule(rid: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        ShippingService(db).delete_extra_rule(rid)
        return no_content()
    except DomainError as exc:
        return err(exc)


# ─── Legacy V1 (backward compat) ─────────────────────────────────────────────

@router.get("/zones")
def list_zones(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return ok(ShippingService(db).list_zones())
    except DomainError as exc:
        return err(exc)


@router.post("/zones", status_code=201)
def create_zone(body: ShippingZoneCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return created(ShippingService(db).create_zone(body), "Zona criada.")
    except DomainError as exc:
        return err(exc)


@router.delete("/zones/{zone_id}", status_code=204)
def delete_zone(zone_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        ShippingService(db).delete_zone(zone_id)
        return no_content()
    except DomainError as exc:
        return err(exc)


@router.get("/rules")
def list_rules(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return ok(ShippingService(db).list_rules())
    except DomainError as exc:
        return err(exc)


@router.post("/rules", status_code=201)
def create_rule(body: ShippingRuleCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        return created(ShippingService(db).create_rule(body), "Regra criada.")
    except DomainError as exc:
        return err(exc)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        ShippingService(db).delete_rule(rule_id)
        return no_content()
    except DomainError as exc:
        return err(exc)

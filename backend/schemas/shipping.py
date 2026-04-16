from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from backend.models.shipping import ShippingRuleType, AreaType


# ── Zone ────────────────────────────────────────────────────────────────────
class ZoneAreaIn(BaseModel):
    area_type: AreaType
    value: str


class ShippingZoneCreate(BaseModel):
    name: str
    active: bool = True
    areas: list[ZoneAreaIn] = []


class ShippingZoneOut(BaseModel):
    id: str
    name: str
    active: bool
    areas: list[dict] = []

    model_config = {"from_attributes": True}


# ── Rule ─────────────────────────────────────────────────────────────────────
class ShippingRuleCreate(BaseModel):
    zone_id: Optional[str] = None
    name: str
    rule_type: ShippingRuleType
    priority: int = 0
    active: bool = True
    base_price: float = 0.0
    per_km_price: float = 0.0
    store_lat: Optional[float] = None
    store_lng: Optional[float] = None
    free_above_amount: Optional[float] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class ShippingRuleOut(ShippingRuleCreate):
    id: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Calculate request / response ─────────────────────────────────────────────
class ShippingCalculateIn(BaseModel):
    city: str
    neighborhood: Optional[str] = None
    zip_code: Optional[str] = None
    order_subtotal: float = 0.0


class ShippingCalculateOut(BaseModel):
    shipping_price: float
    shipping_type: ShippingRuleType
    rule_name: str
    free: bool

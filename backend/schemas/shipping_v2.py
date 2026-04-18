"""
Pydantic schemas for Shipping V2.

All CRUD DTOs plus the enhanced ShippingCalculateOut
(now includes estimated_time, available flag, message).
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ─── Config ──────────────────────────────────────────────────────────────────

class ShippingConfigOut(BaseModel):
    id: str
    delivery_enabled: bool
    pickup_enabled: bool
    pickup_message: str
    min_order_value: float
    default_estimated_time: int
    max_delivery_distance: float
    default_base_fee: float
    unavailable_message: str
    store_lat: Optional[float]
    store_lng: Optional[float]
    updated_at: datetime

    model_config = {"from_attributes": True}


class ShippingConfigUpdate(BaseModel):
    delivery_enabled: Optional[bool] = None
    pickup_enabled: Optional[bool] = None
    pickup_message: Optional[str] = None
    min_order_value: Optional[float] = None
    default_estimated_time: Optional[int] = None
    max_delivery_distance: Optional[float] = None
    default_base_fee: Optional[float] = None
    unavailable_message: Optional[str] = None
    store_lat: Optional[float] = None
    store_lng: Optional[float] = None


# ─── Freight Type Config ──────────────────────────────────────────────────────

class FreightTypeConfigOut(BaseModel):
    id: str
    freight_type: str
    active: bool
    priority: int
    fixed_value: float
    free_above_value: float
    scheduled_surcharge: float
    scheduled_surcharge_type: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class FreightTypeConfigUpdate(BaseModel):
    active: Optional[bool] = None
    priority: Optional[int] = None
    fixed_value: Optional[float] = None
    free_above_value: Optional[float] = None
    scheduled_surcharge: Optional[float] = None
    scheduled_surcharge_type: Optional[str] = None


# ─── Neighborhood ─────────────────────────────────────────────────────────────

class ShippingNeighborhoodCreate(BaseModel):
    name: str = Field(..., min_length=1)
    city: str = ""
    shipping_value: float = 0.0
    is_free: bool = False
    min_order_value: float = 0.0
    estimated_time_min: int = 45
    notes: str = ""
    active: bool = True
    priority: int = 0


class ShippingNeighborhoodUpdate(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None
    shipping_value: Optional[float] = None
    is_free: Optional[bool] = None
    min_order_value: Optional[float] = None
    estimated_time_min: Optional[int] = None
    notes: Optional[str] = None
    active: Optional[bool] = None
    priority: Optional[int] = None


class ShippingNeighborhoodOut(ShippingNeighborhoodCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── CEP Range ───────────────────────────────────────────────────────────────

class ShippingCepRangeCreate(BaseModel):
    name: str = ""
    cep_start: str = Field(..., min_length=8, max_length=9)
    cep_end: str = Field(..., min_length=8, max_length=9)
    shipping_value: float = 0.0
    min_order_value: float = 0.0
    estimated_time_min: int = 45
    active: bool = True
    priority: int = 0


class ShippingCepRangeUpdate(BaseModel):
    name: Optional[str] = None
    cep_start: Optional[str] = None
    cep_end: Optional[str] = None
    shipping_value: Optional[float] = None
    min_order_value: Optional[float] = None
    estimated_time_min: Optional[int] = None
    active: Optional[bool] = None
    priority: Optional[int] = None


class ShippingCepRangeOut(ShippingCepRangeCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Distance Rule ────────────────────────────────────────────────────────────

class ShippingDistanceRuleCreate(BaseModel):
    name: str = ""
    km_min: float = 0.0
    km_max: float = 5.0
    base_fee: float = 0.0
    fee_per_km: float = 0.0
    min_fee: float = 0.0
    max_fee: float = 999.0
    estimated_time_min: int = 45
    active: bool = True
    priority: int = 0


class ShippingDistanceRuleUpdate(BaseModel):
    name: Optional[str] = None
    km_min: Optional[float] = None
    km_max: Optional[float] = None
    base_fee: Optional[float] = None
    fee_per_km: Optional[float] = None
    min_fee: Optional[float] = None
    max_fee: Optional[float] = None
    estimated_time_min: Optional[int] = None
    active: Optional[bool] = None
    priority: Optional[int] = None


class ShippingDistanceRuleOut(ShippingDistanceRuleCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Order Value Tier ─────────────────────────────────────────────────────────

class ShippingOrderValueTierCreate(BaseModel):
    name: str = ""
    order_value_min: float = 0.0
    order_value_max: Optional[float] = None
    shipping_value: float = 0.0
    is_free: bool = False
    active: bool = True
    priority: int = 0


class ShippingOrderValueTierUpdate(BaseModel):
    name: Optional[str] = None
    order_value_min: Optional[float] = None
    order_value_max: Optional[float] = None
    shipping_value: Optional[float] = None
    is_free: Optional[bool] = None
    active: Optional[bool] = None
    priority: Optional[int] = None


class ShippingOrderValueTierOut(ShippingOrderValueTierCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Promotion ────────────────────────────────────────────────────────────────

class ShippingPromotionCreate(BaseModel):
    name: str = Field(..., min_length=1)
    promo_type: str
    min_order_value: float = 0.0
    shipping_value: float = 0.0
    neighborhood_ids: str = "[]"   # JSON array string
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    active: bool = True
    priority: int = 100


class ShippingPromotionUpdate(BaseModel):
    name: Optional[str] = None
    promo_type: Optional[str] = None
    min_order_value: Optional[float] = None
    shipping_value: Optional[float] = None
    neighborhood_ids: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    active: Optional[bool] = None
    priority: Optional[int] = None


class ShippingPromotionOut(ShippingPromotionCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Extra Rule ───────────────────────────────────────────────────────────────

class ShippingExtraRuleCreate(BaseModel):
    rule_type: str
    name: str = Field(..., min_length=1)
    value: float = 0.0
    value_type: str = "fixed"
    condition: str = ""
    message: str = ""
    active: bool = True
    priority: int = 0
    time_start: Optional[str] = None
    time_end: Optional[str] = None


class ShippingExtraRuleUpdate(BaseModel):
    rule_type: Optional[str] = None
    name: Optional[str] = None
    value: Optional[float] = None
    value_type: Optional[str] = None
    condition: Optional[str] = None
    message: Optional[str] = None
    active: Optional[bool] = None
    priority: Optional[int] = None
    time_start: Optional[str] = None
    time_end: Optional[str] = None


class ShippingExtraRuleOut(ShippingExtraRuleCreate):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Calculate ───────────────────────────────────────────────────────────────

class ShippingCalculateIn(BaseModel):
    """Input for shipping calculation — matches both V1 and V2."""
    city: str = ""
    neighborhood: Optional[str] = None
    zip_code: Optional[str] = None
    order_subtotal: float = 0.0
    is_pickup: bool = False
    is_scheduled: bool = False
    distance_km: Optional[float] = None   # pass if caller already knows distance


class ShippingCalculateOut(BaseModel):
    shipping_price: float
    shipping_type: str
    rule_name: str
    free: bool
    estimated_time: int = 45
    available: bool = True
    message: str = ""

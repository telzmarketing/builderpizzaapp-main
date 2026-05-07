from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

UpsellTriggerType = Literal["product_in_cart", "category", "min_value", "min_quantity"]
UpsellEventType = Literal["viewed", "accepted", "rejected"]


# ── Embedded product summary returned inside upsells ─────────────────────────

class UpsellProductSizeOut(BaseModel):
    id: str
    label: str
    price: float
    is_default: bool
    active: bool
    sort_order: int

    model_config = {"from_attributes": True}


class UpsellProductOut(BaseModel):
    id: str
    name: str
    description: str
    price: float
    icon: str
    category: str | None = None
    product_type: str | None = None
    active: bool
    sizes: list[UpsellProductSizeOut] = []

    model_config = {"from_attributes": True}


# ── CRUD schemas ──────────────────────────────────────────────────────────────

class UpsellIn(BaseModel):
    internal_name: str = Field(min_length=2, max_length=200)
    product_id: str
    image_url: str | None = None
    main_text: str = Field(min_length=2, max_length=500)
    secondary_text: str | None = None
    promotional_price: float | None = None
    trigger_type: UpsellTriggerType = "min_value"
    trigger_product_id: str | None = None
    trigger_category: str | None = None
    trigger_min_value: float | None = 0.0
    trigger_min_quantity: int | None = 1
    allowed_weekdays: str | None = "0123456"
    start_time: str | None = None
    end_time: str | None = None
    priority: int = Field(default=0, ge=0, le=9999)
    display_limit: int = Field(default=1, ge=1, le=100)
    active: bool = True


class UpsellOut(BaseModel):
    id: str
    internal_name: str
    product_id: str
    image_url: str | None
    main_text: str
    secondary_text: str | None
    promotional_price: float | None
    trigger_type: str
    trigger_product_id: str | None
    trigger_category: str | None
    trigger_min_value: float | None
    trigger_min_quantity: int | None
    allowed_weekdays: str | None
    start_time: str | None
    end_time: str | None
    priority: int
    display_limit: int
    active: bool
    created_at: datetime
    updated_at: datetime
    product: UpsellProductOut | None = None
    trigger_product: UpsellProductOut | None = None
    metrics: "UpsellMetricOut | None" = None

    model_config = {"from_attributes": True}


class UpsellMetricOut(BaseModel):
    id: str
    upsell_id: str
    views: int
    accepts: int
    rejects: int
    revenue: float
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Engine schemas ────────────────────────────────────────────────────────────

class UpsellCartItemIn(BaseModel):
    product_id: str
    category: str | None = None
    quantity: int = 1


class UpsellEligibleIn(BaseModel):
    cart_items: list[UpsellCartItemIn]
    cart_total: float
    session_id: str | None = None


# ── Event schema ──────────────────────────────────────────────────────────────

class UpsellEventIn(BaseModel):
    upsell_id: str
    event_type: UpsellEventType
    order_id: str | None = None
    session_id: str | None = None
    revenue: float = 0.0


# ── Metrics summary ───────────────────────────────────────────────────────────

class UpsellMetricsSummaryItem(BaseModel):
    upsell_id: str
    internal_name: str
    product_name: str
    views: int
    accepts: int
    rejects: int
    revenue: float
    conversion_rate: float


class UpsellMetricsSummary(BaseModel):
    total_views: int
    total_accepts: int
    total_rejects: int
    total_revenue: float
    items: list[UpsellMetricsSummaryItem]

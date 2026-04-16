from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from backend.models.order import OrderStatus


# ── Flavor slot (mirrors front-end PizzaFlavor) ──────────────────────────────
class FlavorIn(BaseModel):
    product_id: str
    name: str
    price: float
    icon: str


# ── Cart item sent from the front-end ────────────────────────────────────────
class CartItemIn(BaseModel):
    product_id: str
    quantity: int = Field(ge=1)
    selected_size: str
    flavor_division: int = Field(ge=1, le=3, default=1)
    flavors: list[FlavorIn]          # len must match flavor_division
    final_price: float               # pre-computed by front-end (validated server-side)
    add_ons: list[str] = []


# ── Guest delivery address (no customer account required) ────────────────────
class DeliveryAddressIn(BaseModel):
    name: str
    phone: str
    street: str
    city: str
    complement: Optional[str] = None


# ── Checkout payload ─────────────────────────────────────────────────────────
class CheckoutIn(BaseModel):
    items: list[CartItemIn]
    delivery: DeliveryAddressIn
    coupon_code: Optional[str] = None
    customer_id: Optional[str] = None    # if logged in
    payment_method: str = "pix"          # pix | credit_card | cash


# ── Read schemas ─────────────────────────────────────────────────────────────
class OrderItemFlavorOut(BaseModel):
    id: str
    product_id: str
    flavor_name: str
    flavor_price: float
    position: int

    model_config = {"from_attributes": True}


class OrderItemOut(BaseModel):
    id: str
    product_id: str
    quantity: int
    selected_size: str
    flavor_division: int
    unit_price: float
    total_price: float
    flavors: list[OrderItemFlavorOut] = []

    model_config = {"from_attributes": True}


class OrderOut(BaseModel):
    id: str
    customer_id: Optional[str]
    delivery_name: Optional[str]
    delivery_phone: Optional[str]
    delivery_street: Optional[str]
    delivery_city: Optional[str]
    delivery_complement: Optional[str]
    status: OrderStatus
    subtotal: float
    shipping_fee: float
    discount: float
    total: float
    estimated_time: int
    loyalty_points_earned: int
    coupon_id: Optional[str]
    items: list[OrderItemOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderStatusUpdate(BaseModel):
    status: OrderStatus

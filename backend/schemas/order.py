from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from backend.models.order import OrderStatus


class FlavorIn(BaseModel):
    product_id: str
    name: str
    price: float
    icon: str


class CartItemIn(BaseModel):
    product_id: str
    quantity: int = Field(ge=1)
    selected_size: str
    selected_size_id: Optional[str] = None  # ID of the ProductSize row for server-side price validation
    flavor_division: int = Field(ge=1, le=3, default=1)
    flavors: list[FlavorIn]
    final_price: float
    add_ons: list[str] = []
    # Pizza crust selection
    selected_crust_type_id: Optional[str] = None
    selected_crust_type_name: Optional[str] = None
    # Drink variant selection
    selected_drink_variant_id: Optional[str] = None
    selected_drink_variant_name: Optional[str] = None
    notes: Optional[str] = None


class DeliveryAddressIn(BaseModel):
    name: str
    phone: str
    street: str
    city: str
    neighborhood: Optional[str] = None
    zip_code: Optional[str] = None
    complement: Optional[str] = None
    is_pickup: bool = False
    is_scheduled: bool = False


class CheckoutIn(BaseModel):
    items: list[CartItemIn]
    delivery: DeliveryAddressIn
    coupon_code: Optional[str] = None
    customer_id: Optional[str] = None
    payment_method: str = "pix"
    campaign_id: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    session_id: Optional[str] = None
    landing_page: Optional[str] = None
    referrer: Optional[str] = None


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
    selected_size_id: Optional[str] = None
    flavor_division: int
    flavor_count: int = 1
    selected_crust_type_id: Optional[str] = None
    selected_crust_type: Optional[str] = None
    selected_drink_variant: Optional[str] = None
    notes: Optional[str] = None
    unit_price: float
    total_price: float
    standard_unit_price: Optional[float] = None
    applied_unit_price: Optional[float] = None
    promotion_id: Optional[str] = None
    promotion_name: Optional[str] = None
    promotion_discount: float = 0.0
    promotion_blocked: bool = False
    promotion_block_reason: Optional[str] = None
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
    campaign_id: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    session_id: Optional[str] = None
    landing_page: Optional[str] = None
    referrer: Optional[str] = None
    items: list[OrderItemOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OrderStatusUpdate(BaseModel):
    status: OrderStatus

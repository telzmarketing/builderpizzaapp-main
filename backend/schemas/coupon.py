from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from backend.models.coupon import CouponType


class CouponCreate(BaseModel):
    code: str
    description: Optional[str] = None
    icon: str = "🎟️"
    coupon_type: CouponType = CouponType.percentage
    discount_value: float = Field(ge=0)
    min_order_value: float = 0.0
    max_uses: Optional[int] = None
    max_uses_per_customer: Optional[int] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    free_shipping: bool = False
    gift_enabled: bool = False
    gift_product_id: Optional[str] = None
    gift_quantity: int = Field(default=1, ge=1)
    stackable: bool = False
    campaign_id: Optional[str] = None
    active: bool = True

    @field_validator("coupon_type", mode="before")
    @classmethod
    def normalize_coupon_type(cls, value):
        if value == "percent":
            return CouponType.percentage
        if value == "none":
            return CouponType.fixed
        return value


class CouponUpdate(BaseModel):
    code: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    coupon_type: Optional[CouponType] = None
    discount_value: Optional[float] = None
    min_order_value: Optional[float] = None
    max_uses: Optional[int] = None
    max_uses_per_customer: Optional[int] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    free_shipping: Optional[bool] = None
    gift_enabled: Optional[bool] = None
    gift_product_id: Optional[str] = None
    gift_quantity: Optional[int] = Field(default=None, ge=1)
    stackable: Optional[bool] = None
    campaign_id: Optional[str] = None
    active: Optional[bool] = None

    @field_validator("coupon_type", mode="before")
    @classmethod
    def normalize_coupon_type(cls, value):
        if value == "percent":
            return CouponType.percentage
        if value == "none":
            return CouponType.fixed
        return value


class CouponOut(BaseModel):
    id: str
    code: str
    description: Optional[str]
    icon: str
    coupon_type: CouponType
    discount_value: float
    min_order_value: float
    max_uses: Optional[int]
    max_uses_per_customer: Optional[int]
    used_count: int
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    expiry_date: Optional[datetime]
    free_shipping: bool = False
    gift_enabled: bool = False
    gift_product_id: Optional[str] = None
    gift_quantity: int = 1
    stackable: bool = False
    active: bool
    campaign_id: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class CouponApplyIn(BaseModel):
    code: str
    order_subtotal: float
    delivery_fee: float = 0.0
    customer_id: Optional[str] = None
    phone: Optional[str] = None


class CouponGiftOut(BaseModel):
    product_id: str
    name: str
    icon: Optional[str] = None
    quantity: int
    unit_price: float = 0.0
    original_price: float
    is_gift: bool = True
    gift_reason: str = "coupon"
    coupon_id: str
    coupon_code: str


class CouponApplyOut(BaseModel):
    valid: bool
    coupon_id: Optional[str] = None
    coupon_code: Optional[str] = None
    discount_amount: float = 0.0
    free_shipping: bool = False
    delivery_fee_original: float = 0.0
    delivery_fee_discount: float = 0.0
    delivery_fee_final: float = 0.0
    free_shipping_applied: bool = False
    gift: Optional[CouponGiftOut] = None
    message: str


class CouponUsageOut(BaseModel):
    id: str
    coupon_id: str
    customer_id: Optional[str]
    phone: Optional[str]
    order_id: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}

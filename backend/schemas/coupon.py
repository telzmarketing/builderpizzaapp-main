from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime
from backend.models.coupon import CouponType


class CouponCreate(BaseModel):
    code: str
    description: Optional[str] = None
    icon: str = "🎟️"
    coupon_type: CouponType = CouponType.percentage
    discount_value: float = Field(gt=0)
    min_order_value: float = 0.0
    max_uses: Optional[int] = None
    max_uses_per_customer: Optional[int] = None
    expiry_date: Optional[datetime] = None
    campaign_id: Optional[str] = None
    active: bool = True

    @field_validator("coupon_type", mode="before")
    @classmethod
    def normalize_coupon_type(cls, value):
        if value == "percent":
            return CouponType.percentage
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
    expiry_date: Optional[datetime] = None
    campaign_id: Optional[str] = None
    active: Optional[bool] = None

    @field_validator("coupon_type", mode="before")
    @classmethod
    def normalize_coupon_type(cls, value):
        if value == "percent":
            return CouponType.percentage
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
    expiry_date: Optional[datetime]
    active: bool
    campaign_id: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class CouponApplyIn(BaseModel):
    code: str
    order_subtotal: float
    customer_id: Optional[str] = None
    phone: Optional[str] = None


class CouponApplyOut(BaseModel):
    valid: bool
    coupon_id: Optional[str] = None
    discount_amount: float = 0.0
    message: str


class CouponUsageOut(BaseModel):
    id: str
    coupon_id: str
    customer_id: Optional[str]
    phone: Optional[str]
    order_id: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}

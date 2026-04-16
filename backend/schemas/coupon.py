from pydantic import BaseModel, Field
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
    expiry_date: Optional[datetime] = None
    active: bool = True


class CouponUpdate(BaseModel):
    description: Optional[str] = None
    icon: Optional[str] = None
    discount_value: Optional[float] = None
    min_order_value: Optional[float] = None
    max_uses: Optional[int] = None
    expiry_date: Optional[datetime] = None
    active: Optional[bool] = None


class CouponOut(BaseModel):
    id: str
    code: str
    description: Optional[str]
    icon: str
    coupon_type: CouponType
    discount_value: float
    min_order_value: float
    max_uses: Optional[int]
    used_count: int
    expiry_date: Optional[datetime]
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CouponApplyIn(BaseModel):
    code: str
    order_subtotal: float


class CouponApplyOut(BaseModel):
    valid: bool
    coupon_id: Optional[str] = None
    discount_amount: float = 0.0
    message: str

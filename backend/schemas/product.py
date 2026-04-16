from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from backend.models.product import PricingRule


class ProductBase(BaseModel):
    name: str
    description: str
    price: float = Field(gt=0)
    icon: str = "🍕"
    rating: float = Field(default=4.5, ge=1.0, le=5.0)
    active: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(default=None, gt=0)
    icon: Optional[str] = None
    rating: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    active: Optional[bool] = None


class ProductOut(ProductBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Multi-flavor config
class MultiFlavorsConfigUpdate(BaseModel):
    max_flavors: Optional[int] = Field(default=None, ge=2, le=3)
    pricing_rule: Optional[PricingRule] = None


class MultiFlavorsConfigOut(BaseModel):
    id: str
    max_flavors: int
    pricing_rule: PricingRule
    updated_at: datetime

    model_config = {"from_attributes": True}

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from backend.models.product import PricingRule


class ProductSizeCreate(BaseModel):
    label: str
    description: Optional[str] = None
    price: float = Field(gt=0)
    is_default: bool = False
    sort_order: int = 0
    active: bool = True


class ProductSizeUpdate(BaseModel):
    label: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(default=None, gt=0)
    is_default: Optional[bool] = None
    sort_order: Optional[int] = None
    active: Optional[bool] = None


class ProductSizeOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    product_id: str
    label: str
    description: Optional[str]
    price: float
    is_default: bool
    sort_order: int
    active: bool
    created_at: datetime


class ProductBase(BaseModel):
    name: str
    description: str
    price: float = Field(gt=0)
    icon: str = "🍕"
    category: Optional[str] = None
    rating: float = Field(default=4.5, ge=1.0, le=5.0)
    active: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(default=None, gt=0)
    icon: Optional[str] = None
    category: Optional[str] = None
    rating: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    active: Optional[bool] = None


class ProductOut(ProductBase):
    id: str
    created_at: datetime
    updated_at: datetime
    sizes: List[ProductSizeOut] = []

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

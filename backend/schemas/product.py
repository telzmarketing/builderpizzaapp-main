from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from backend.models.product import PricingRule


class ProductCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    active: bool = True
    sort_order: int = 0


class ProductCategoryUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    active: Optional[bool] = None
    sort_order: Optional[int] = None


class ProductCategoryOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    name: str
    active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime


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


# ── Crust Types ───────────────────────────────────────────────────────────────

class ProductCrustTypeCreate(BaseModel):
    name: str
    price_addition: float = Field(default=0.0, ge=0)
    active: bool = True
    sort_order: int = 0


class ProductCrustTypeUpdate(BaseModel):
    name: Optional[str] = None
    price_addition: Optional[float] = Field(default=None, ge=0)
    active: Optional[bool] = None
    sort_order: Optional[int] = None


class ProductCrustTypeOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    product_id: str
    name: str
    price_addition: float
    active: bool
    sort_order: int
    created_at: datetime


# ── Drink Variants ────────────────────────────────────────────────────────────

class ProductDrinkVariantCreate(BaseModel):
    name: str
    price_addition: float = Field(default=0.0, ge=0)
    active: bool = True
    sort_order: int = 0


class ProductDrinkVariantUpdate(BaseModel):
    name: Optional[str] = None
    price_addition: Optional[float] = Field(default=None, ge=0)
    active: Optional[bool] = None
    sort_order: Optional[int] = None


class ProductDrinkVariantOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    product_id: str
    name: str
    price_addition: float
    active: bool
    sort_order: int
    created_at: datetime


# ── Product ───────────────────────────────────────────────────────────────────

class ProductBase(BaseModel):
    name: str
    description: str
    price: float = Field(gt=0)
    icon: str = "🍕"
    category: Optional[str] = None
    product_type: Optional[str] = None  # "pizza" | "drink" | "other"
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
    product_type: Optional[str] = None
    rating: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    active: Optional[bool] = None


class ProductOut(ProductBase):
    id: str
    created_at: datetime
    updated_at: datetime
    sizes: List[ProductSizeOut] = []
    crust_types: List[ProductCrustTypeOut] = []
    drink_variants: List[ProductDrinkVariantOut] = []
    standard_price: Optional[float] = None
    current_price: Optional[float] = None
    promotion_applied: bool = False
    promotion_id: Optional[str] = None
    promotion_name: Optional[str] = None
    promotion_discount: float = 0.0

    model_config = {"from_attributes": True}


class ProductPromotionCombinationBase(BaseModel):
    product_size_id: Optional[str] = None
    product_crust_type_id: Optional[str] = None
    active: bool = True
    promotional_value: Optional[float] = Field(default=None, ge=0)


class ProductPromotionCombinationCreate(ProductPromotionCombinationBase):
    pass


class ProductPromotionCombinationOut(ProductPromotionCombinationBase):
    model_config = {"from_attributes": True}

    id: str
    promotion_id: str
    created_at: datetime
    updated_at: datetime


class ProductPromotionBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    active: bool = True
    valid_weekdays: List[int] = Field(default_factory=list)
    start_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    discount_type: str = Field(default="fixed_price", pattern=r"^(fixed_price|amount_off|percent_off)$")
    default_value: Optional[float] = Field(default=None, ge=0)
    timezone: str = "America/Sao_Paulo"


class ProductPromotionCreate(ProductPromotionBase):
    combinations: List[ProductPromotionCombinationCreate] = Field(default_factory=list)


class ProductPromotionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    active: Optional[bool] = None
    valid_weekdays: Optional[List[int]] = None
    start_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    discount_type: Optional[str] = Field(default=None, pattern=r"^(fixed_price|amount_off|percent_off)$")
    default_value: Optional[float] = Field(default=None, ge=0)
    timezone: Optional[str] = None
    combinations: Optional[List[ProductPromotionCombinationCreate]] = None


class ProductPromotionOut(ProductPromotionBase):
    model_config = {"from_attributes": True}

    id: str
    product_id: str
    combinations: List[ProductPromotionCombinationOut] = []
    created_at: datetime
    updated_at: datetime


class ProductPriceQuoteOut(BaseModel):
    standard_price: float
    final_price: float
    promotion_applied: bool
    promotion_id: Optional[str] = None
    promotion_name: Optional[str] = None
    discount_amount: float = 0.0
    discount_type: Optional[str] = None
    promotion_blocked: bool = False
    promotion_block_reason: Optional[str] = None


# ── Multi-flavor config ───────────────────────────────────────────────────────

class MultiFlavorsConfigUpdate(BaseModel):
    max_flavors: Optional[int] = Field(default=None, ge=2, le=3)
    pricing_rule: Optional[PricingRule] = None


class MultiFlavorsConfigOut(BaseModel):
    id: str
    max_flavors: int
    pricing_rule: PricingRule
    updated_at: datetime

    model_config = {"from_attributes": True}

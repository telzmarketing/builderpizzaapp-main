from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime
from backend.models.product import PricingRule


class ProductCategoryCreate(BaseModel):
    parent_id: Optional[str] = None
    name: str = Field(min_length=1, max_length=100)
    active: bool = True
    sort_order: int = 0


class ProductCategoryUpdate(BaseModel):
    parent_id: Optional[str] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    active: Optional[bool] = None
    sort_order: Optional[int] = None


class ProductCategoryOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    parent_id: Optional[str] = None
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
    price: Optional[float] = Field(default=None, ge=0)
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
    price: float = Field(ge=0)
    icon: str = "🍕"
    category: Optional[str] = None
    subcategory: Optional[str] = None
    product_type: Optional[str] = None  # "pizza" | "drink" | "other" | "brinde"
    rating: float = Field(default=4.5, ge=1.0, le=5.0)
    active: bool = True
    best_seller_badge_mode: str = "off"  # "off" | "manual" | "auto"


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(default=None, ge=0)
    icon: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    product_type: Optional[str] = None
    rating: Optional[float] = Field(default=None, ge=1.0, le=5.0)
    active: Optional[bool] = None
    best_seller_badge_mode: Optional[str] = None


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
    promotion_free_shipping: bool = False
    promotion_gift_enabled: bool = False
    promotion_gift_product_id: Optional[str] = None
    promotion_gift_quantity: int = 1
    promotion_gift_name: Optional[str] = None
    promotion_gift_icon: Optional[str] = None
    promotion_blocks_other_coupons: bool = False
    show_best_seller_badge: bool = False

    model_config = {"from_attributes": True}


class BestSellerConfigOut(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    period_days: int
    top_count: int
    updated_at: datetime


class BestSellerConfigUpdate(BaseModel):
    period_days: Optional[int] = Field(default=None, ge=0)
    top_count: Optional[int] = Field(default=None, ge=1, le=20)


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
    free_shipping: bool = False
    gift_enabled: bool = False
    gift_product_id: Optional[str] = None
    gift_quantity: int = Field(default=1, ge=1)
    blocks_other_coupons: bool = False
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
    free_shipping: Optional[bool] = None
    gift_enabled: Optional[bool] = None
    gift_product_id: Optional[str] = None
    gift_quantity: Optional[int] = Field(default=None, ge=1)
    blocks_other_coupons: Optional[bool] = None
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
    free_shipping: bool = False
    gift_enabled: bool = False
    gift_product_id: Optional[str] = None
    gift_quantity: int = 1
    gift_name: Optional[str] = None
    gift_icon: Optional[str] = None
    blocks_other_coupons: bool = False
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

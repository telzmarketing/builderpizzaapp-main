from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from backend.models.campaign import CampaignStatus, CampaignType, CpDiscountType, KitType


# ── Campaign ──────────────────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    name: str
    description: Optional[str] = None
    status: CampaignStatus = CampaignStatus.draft
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    banner: Optional[str] = None
    slug: str
    campaign_type: CampaignType = CampaignType.products_promo
    display_title: Optional[str] = None
    display_subtitle: Optional[str] = None
    display_order: int = 0
    published: bool = False
    active_days: Optional[str] = None
    card_bg_color: Optional[str] = None
    media_type: Optional[str] = "image"
    video_url: Optional[str] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[CampaignStatus] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    banner: Optional[str] = None
    slug: Optional[str] = None
    campaign_type: Optional[CampaignType] = None
    display_title: Optional[str] = None
    display_subtitle: Optional[str] = None
    display_order: Optional[int] = None
    published: Optional[bool] = None
    active_days: Optional[str] = None
    card_bg_color: Optional[str] = None
    media_type: Optional[str] = None
    video_url: Optional[str] = None


class CampaignOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    status: CampaignStatus
    start_at: Optional[datetime]
    end_at: Optional[datetime]
    banner: Optional[str]
    slug: str
    campaign_type: CampaignType
    display_title: Optional[str]
    display_subtitle: Optional[str]
    display_order: int
    published: bool
    active_days: Optional[str]
    card_bg_color: Optional[str]
    media_type: Optional[str]
    video_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── CampaignProduct ───────────────────────────────────────────────────────────

class CampaignProductCreate(BaseModel):
    product_id: Optional[str] = None
    kit_id: Optional[str] = None
    promotional_price: Optional[float] = None
    discount_type: Optional[CpDiscountType] = None
    discount_value: Optional[float] = None
    active: bool = True


class CampaignProductUpdate(BaseModel):
    promotional_price: Optional[float] = None
    discount_type: Optional[CpDiscountType] = None
    discount_value: Optional[float] = None
    active: Optional[bool] = None


class CampaignProductOut(BaseModel):
    id: str
    campaign_id: str
    product_id: Optional[str]
    kit_id: Optional[str]
    promotional_price: Optional[float]
    discount_type: Optional[CpDiscountType]
    discount_value: Optional[float]
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── PromotionalKit ────────────────────────────────────────────────────────────

class KitItemCreate(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, default=1)


class KitItemOut(BaseModel):
    id: str
    kit_id: str
    product_id: str
    quantity: int

    model_config = {"from_attributes": True}


class PromotionalKitCreate(BaseModel):
    name: str
    description: Optional[str] = None
    icon: str = "🎁"
    kit_type: KitType = KitType.kit
    price_original: float = 0.0
    price_promotional: float = 0.0
    discount_type: Optional[CpDiscountType] = None
    discount_value: Optional[float] = None
    valid_until: Optional[datetime] = None
    active: bool = True


class PromotionalKitUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    kit_type: Optional[KitType] = None
    price_original: Optional[float] = None
    price_promotional: Optional[float] = None
    discount_type: Optional[CpDiscountType] = None
    discount_value: Optional[float] = None
    valid_until: Optional[datetime] = None
    active: Optional[bool] = None


class PromotionalKitOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    icon: str
    kit_type: KitType
    price_original: float
    price_promotional: float
    discount_type: Optional[CpDiscountType]
    discount_value: Optional[float]
    valid_until: Optional[datetime]
    active: bool
    created_at: datetime
    updated_at: datetime
    items: list[KitItemOut] = []

    model_config = {"from_attributes": True}

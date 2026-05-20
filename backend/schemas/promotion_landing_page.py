from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

PromotionLandingMediaSlot = Literal["image_url", "image_url_2", "video_url"]
DEFAULT_MEDIA_ORDER: list[PromotionLandingMediaSlot] = ["image_url", "image_url_2", "video_url"]


class PromotionLandingPageBase(BaseModel):
    product_id: str
    promotion_id: str
    title: str = Field(min_length=1, max_length=220)
    subtitle: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = None
    cta_text: str = Field(default="Quero essa pizza", min_length=1, max_length=80)
    image_url: Optional[str] = None
    image_url_2: Optional[str] = None
    video_url: Optional[str] = None
    media_order: list[PromotionLandingMediaSlot] = Field(default_factory=lambda: DEFAULT_MEDIA_ORDER.copy())
    image_position: str = Field(default="center", pattern=r"^(center|top|bottom|left|right)$")
    content_alignment: str = Field(default="center", pattern=r"^(left|center|right)$")
    overlay_style: str = Field(default="dark-gradient", pattern=r"^(dark-gradient|dark|light|brand)$")
    badge_text: Optional[str] = Field(default=None, max_length=80)
    free_shipping_label: str = Field(default="Frete gratis na promocao", min_length=1, max_length=160)
    gift_label_prefix: str = Field(default="Brinde", min_length=1, max_length=80)
    gift_fallback_label: str = Field(default="Brinde incluido", min_length=1, max_length=160)
    active_offer_label: str = Field(default="Oferta ativa agora", min_length=1, max_length=160)
    slug: Optional[str] = Field(default=None, max_length=160)
    status: str = Field(default="draft", pattern=r"^(draft|published)$")
    is_active: bool = True


class PromotionLandingPageCreate(PromotionLandingPageBase):
    pass


class PromotionLandingPageUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=220)
    subtitle: Optional[str] = Field(default=None, max_length=500)
    description: Optional[str] = None
    cta_text: Optional[str] = Field(default=None, min_length=1, max_length=80)
    image_url: Optional[str] = None
    image_url_2: Optional[str] = None
    video_url: Optional[str] = None
    media_order: Optional[list[PromotionLandingMediaSlot]] = None
    image_position: Optional[str] = Field(default=None, pattern=r"^(center|top|bottom|left|right)$")
    content_alignment: Optional[str] = Field(default=None, pattern=r"^(left|center|right)$")
    overlay_style: Optional[str] = Field(default=None, pattern=r"^(dark-gradient|dark|light|brand)$")
    badge_text: Optional[str] = Field(default=None, max_length=80)
    free_shipping_label: Optional[str] = Field(default=None, min_length=1, max_length=160)
    gift_label_prefix: Optional[str] = Field(default=None, min_length=1, max_length=80)
    gift_fallback_label: Optional[str] = Field(default=None, min_length=1, max_length=160)
    active_offer_label: Optional[str] = Field(default=None, min_length=1, max_length=160)
    slug: Optional[str] = Field(default=None, max_length=160)
    status: Optional[str] = Field(default=None, pattern=r"^(draft|published)$")
    is_active: Optional[bool] = None


class PromotionLandingPageOut(PromotionLandingPageBase):
    model_config = {"from_attributes": True}

    id: str
    slug: str
    status: str
    is_active: bool
    public_url: str = ""
    product_name: Optional[str] = None
    promotion_name: Optional[str] = None
    promotion_active_now: bool = False
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None


class PromotionLandingDecisionOut(BaseModel):
    product_id: str
    promotion_id: Optional[str] = None
    landing_page_id: Optional[str] = None
    slug: Optional[str] = None
    url: Optional[str] = None
    should_redirect: bool = False

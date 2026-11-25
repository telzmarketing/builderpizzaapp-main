from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from backend.models.strategic_campaign import StrategicCampaignStatus


class StrategicCommercialConfig(BaseModel):
    sales_mode: Literal["immediate", "preorder"] = "immediate"
    allow_when_store_closed: bool = False
    require_scheduled_order: bool = False
    min_lead_minutes: int = Field(default=0, ge=0, le=43200)
    max_lead_days: int | None = Field(default=None, ge=1, le=365)
    allowed_payment_methods: list[Literal["pix", "credit_card", "debit_card", "pay_on_delivery"]] = Field(default_factory=list)


class StrategicMarketingConfig(BaseModel):
    planned_budget: float | None = Field(default=None, ge=0)
    traffic_campaign_id: str | None = Field(default=None, max_length=120)
    attribution_window_days: int = Field(default=30, ge=1, le=90)


class StrategicCampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    commercial_name: str | None = Field(default=None, max_length=200)
    slug: str = Field(min_length=1, max_length=180)
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    visual_config: dict[str, Any] = Field(default_factory=dict)
    commercial_config: StrategicCommercialConfig = Field(default_factory=StrategicCommercialConfig)
    marketing_config: StrategicMarketingConfig = Field(default_factory=StrategicMarketingConfig)


class StrategicCampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    commercial_name: str | None = Field(default=None, max_length=200)
    slug: str | None = Field(default=None, min_length=1, max_length=180)
    description: str | None = None
    status: StrategicCampaignStatus | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    visual_config: dict[str, Any] | None = None
    commercial_config: StrategicCommercialConfig | None = None
    marketing_config: StrategicMarketingConfig | None = None


class StrategicOfferCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    product_id: str | None = None
    kit_id: str | None = None
    price_original: Decimal = Field(ge=0, decimal_places=2)
    price_promotional: Decimal = Field(ge=0, decimal_places=2)
    display_order: int = Field(default=0, ge=0)
    quantity_limit: int | None = Field(default=None, ge=0)
    max_per_customer: int | None = Field(default=None, ge=1)
    sales_starts_at: datetime | None = None
    sales_ends_at: datetime | None = None
    show_when_sold_out: bool = True
    button_text: str | None = Field(default=None, max_length=120)
    image_desktop_url: str | None = None
    image_mobile_url: str | None = None
    badge_text: str | None = Field(default=None, max_length=80)
    highlighted: bool = False
    config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_reference_and_price(self):
        if bool(self.product_id) == bool(self.kit_id):
            raise ValueError("Informe exatamente um produto ou kit para a oferta.")
        if self.price_promotional > self.price_original:
            raise ValueError("O preço promocional não pode superar o preço original.")
        if self.sales_starts_at and self.sales_ends_at and self.sales_ends_at <= self.sales_starts_at:
            raise ValueError("O encerramento da oferta deve ser posterior ao início.")
        return self


class StrategicOfferUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    price_original: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    price_promotional: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    active: bool | None = None
    display_order: int | None = Field(default=None, ge=0)
    quantity_limit: int | None = Field(default=None, ge=0)
    max_per_customer: int | None = Field(default=None, ge=1)
    sales_starts_at: datetime | None = None
    sales_ends_at: datetime | None = None
    show_when_sold_out: bool | None = None
    button_text: str | None = Field(default=None, max_length=120)
    image_desktop_url: str | None = None
    image_mobile_url: str | None = None
    badge_text: str | None = Field(default=None, max_length=80)
    highlighted: bool | None = None
    config: dict[str, Any] | None = None


class StrategicOfferOut(BaseModel):
    id: str
    campaign_id: str
    code: str
    title: str
    description: str | None
    product_id: str | None
    kit_id: str | None
    price_original: Decimal
    price_promotional: Decimal
    active: bool
    display_order: int
    quantity_limit: int | None
    max_per_customer: int | None
    sales_starts_at: datetime | None
    sales_ends_at: datetime | None
    show_when_sold_out: bool
    button_text: str | None
    image_desktop_url: str | None
    image_mobile_url: str | None
    badge_text: str | None
    highlighted: bool
    config: dict[str, Any]

    model_config = {"from_attributes": True}


class StrategicCampaignOut(BaseModel):
    id: str
    name: str
    commercial_name: str | None
    slug: str
    description: str | None
    status: StrategicCampaignStatus
    starts_at: datetime | None
    ends_at: datetime | None
    visual_config: dict[str, Any]
    commercial_config: StrategicCommercialConfig = Field(default_factory=StrategicCommercialConfig)
    marketing_config: StrategicMarketingConfig = Field(default_factory=StrategicMarketingConfig)
    published_version: int | None
    offers: list[StrategicOfferOut] = []

    model_config = {"from_attributes": True}


class StrategicCampaignVersionOut(BaseModel):
    id: str
    campaign_id: str
    version: int
    snapshot: dict[str, Any]
    published_at: datetime

    model_config = {"from_attributes": True}

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class TrafficCampaignBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    platform: str = "manual"
    status: str = "draft"
    daily_budget: Optional[float] = Field(default=None, ge=0)
    total_budget: Optional[float] = Field(default=None, ge=0)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    product_id: Optional[str] = None
    coupon_id: Optional[str] = None
    destination_url: Optional[str] = None
    notes: Optional[str] = None


class TrafficCampaignCreate(TrafficCampaignBase):
    pass


class TrafficCampaignUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    platform: Optional[str] = None
    status: Optional[str] = None
    daily_budget: Optional[float] = Field(default=None, ge=0)
    total_budget: Optional[float] = Field(default=None, ge=0)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    product_id: Optional[str] = None
    coupon_id: Optional[str] = None
    destination_url: Optional[str] = None
    notes: Optional[str] = None


class TrafficCampaignOut(TrafficCampaignBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CampaignLinkCreate(BaseModel):
    campaign_id: str
    name: Optional[str] = None
    destination_url: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = "cpc"
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None


class CampaignLinkOut(BaseModel):
    id: str
    campaign_id: str
    name: Optional[str]
    destination_url: str
    final_url: str
    utm_source: Optional[str]
    utm_medium: Optional[str]
    utm_campaign: Optional[str]
    utm_content: Optional[str]
    utm_term: Optional[str]
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class TrackingEventIn(BaseModel):
    session_id: str
    event_type: str
    campaign_id: Optional[str] = None
    value: Optional[float] = None
    path: Optional[str] = None
    landing_page: Optional[str] = None
    referrer: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    metadata: Optional[dict] = None


class TrackingEventOut(BaseModel):
    id: str
    session_id: Optional[str]
    campaign_id: Optional[str]
    event_type: str
    value: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}


class AdIntegrationIn(BaseModel):
    platform: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    account_name: Optional[str] = None


class AdIntegrationOut(BaseModel):
    id: str
    platform: str
    status: str
    account_name: Optional[str]
    last_sync_at: Optional[datetime]
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CampaignSettingsIn(BaseModel):
    attribution_window_days: Optional[int] = Field(default=None, ge=1, le=90)
    attribution_model: Optional[str] = None
    default_margin: Optional[float] = Field(default=None, ge=0, le=1)
    target_roas: Optional[float] = Field(default=None, ge=0)
    tracking_enabled: Optional[bool] = None


class CampaignSettingsOut(BaseModel):
    id: str
    attribution_window_days: int
    attribution_model: str
    default_margin: float
    target_roas: float
    tracking_enabled: bool
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaidTrafficDashboardOut(BaseModel):
    spend: float
    revenue: float
    estimated_profit: float
    roas: float
    roi: float
    cpa: float
    average_ticket: float
    conversion_rate: float
    orders: int
    paid_orders: int
    visitors: int
    carts: int
    abandoned_carts: int
    by_campaign: list[dict]
    by_platform: list[dict]
    by_day: list[dict]


class SyncResultOut(BaseModel):
    status: str
    message: str

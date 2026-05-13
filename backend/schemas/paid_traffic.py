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
    # Comma-separated weekday numbers (0=Sun,1=Mon,...,6=Sat). None = all days.
    active_weekdays: Optional[str] = None
    # ID do pixel (ads_pixels.id) vinculado a esta campanha
    pixel_id: Optional[str] = None
    # Eventos do pixel a disparar, separados por vírgula
    pixel_events: Optional[str] = None


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
    active_weekdays: Optional[str] = None
    pixel_id: Optional[str] = None
    pixel_events: Optional[str] = None


class TrafficCampaignOut(TrafficCampaignBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CampaignCreativeCreate(BaseModel):
    media_url: str
    creative_type: str = "image"
    name: Optional[str] = None


class CampaignCreativeOut(BaseModel):
    id: str
    campaign_id: str
    name: Optional[str] = None
    media_url: str
    creative_type: str
    created_at: datetime

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


class TrackingSessionIn(BaseModel):
    session_id: str
    campaign_id: Optional[str] = None
    landing_page: Optional[str] = None
    referrer: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None


class TrackingSessionOut(BaseModel):
    id: str
    campaign_id: Optional[str]
    utm_source: Optional[str]
    utm_medium: Optional[str]
    utm_campaign: Optional[str]
    landing_page: Optional[str]
    referrer: Optional[str]
    first_seen_at: datetime
    last_seen_at: datetime

    model_config = {"from_attributes": True}


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


class PaidTrafficRealtimeEventOut(BaseModel):
    id: str
    visitor_id: str
    session_id: Optional[str] = None
    event_type: str
    page: Optional[str] = None
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    metadata: Optional[dict] = None
    city: Optional[str] = None
    device: Optional[str] = None
    browser: Optional[str] = None
    created_at: datetime


class PaidTrafficRealtimeVisitorOut(BaseModel):
    id: str
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    device: Optional[str] = None
    browser: Optional[str] = None
    operating_system: Optional[str] = None
    sessions: int
    pageviews: int
    orders: int
    current_page: Optional[str] = None
    current_event: Optional[str] = None
    current_event_at: Optional[datetime] = None
    last_seen: datetime
    is_online: bool
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_accuracy_m: Optional[float] = None


class PaidTrafficRealtimeBreakdownOut(BaseModel):
    name: str
    count: int


class PaidTrafficRealtimeOut(BaseModel):
    generated_at: datetime
    window_minutes: int
    online_visitors: int
    active_sessions: int
    total_events: int
    last_event_at: Optional[datetime] = None
    visitors: list[PaidTrafficRealtimeVisitorOut]
    events: list[PaidTrafficRealtimeEventOut]
    event_counts: list[PaidTrafficRealtimeBreakdownOut]
    devices: list[PaidTrafficRealtimeBreakdownOut]
    cities: list[PaidTrafficRealtimeBreakdownOut]


class SyncResultOut(BaseModel):
    status: str
    message: str

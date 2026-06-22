from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


MarketingIntelligencePeriod = Literal["today", "7d", "30d", "90d", "month", "previous_month"]
MarketingGoalMetricKey = Literal[
    "revenue",
    "paid_orders",
    "leads",
    "conversions",
    "roas",
    "roi",
    "cac",
    "cpa",
    "cpl",
    "average_ticket",
]
MarketingGoalStatus = Literal["active", "paused", "completed", "cancelled"]
MarketingPriority = Literal["low", "medium", "high"]
MarketingComparisonDirection = Literal["increase", "decrease"]
MarketingTimelineEventType = Literal[
    "campaign_created",
    "campaign_paused",
    "campaign_ended",
    "promotion_started",
    "promotion_ended",
    "coupon_created",
    "coupon_expired",
    "goal_reached",
    "goal_closed",
    "budget_changed",
    "creative_changed",
    "strategy_changed",
    "audience_changed",
    "ab_test",
    "landing_page_launched",
    "important_meeting",
    "strategic_note",
    "manual_event",
    "free_event",
]
MarketingTimelineImpact = Literal["low", "medium", "high"]
MarketingAttachmentType = Literal["url", "image", "document", "other"]


class MarketingIntelligenceQuery(BaseModel):
    period: MarketingIntelligencePeriod = "30d"
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class MarketingIntelligenceKpiOut(BaseModel):
    key: str
    label: str
    value: float
    unit: str = "number"
    helper: Optional[str] = None


class MarketingIntelligenceCampaignOut(BaseModel):
    id: str
    name: str
    source_type: str
    platform: Optional[str] = None
    status: Optional[str] = None
    spend: float = 0
    revenue: float = 0
    orders: int = 0
    visitors: int = 0
    clicks: int = 0
    leads: int = 0
    roas: float = 0
    roi: float = 0
    cpa: float = 0
    cpl: float = 0


class MarketingIntelligenceChannelOut(BaseModel):
    channel: str
    label: str
    spend: float = 0
    revenue: float = 0
    orders: int = 0
    visitors: int = 0
    clicks: int = 0
    leads: int = 0
    roas: float = 0
    conversion_rate: float = 0


class MarketingIntelligenceFunnelStepOut(BaseModel):
    key: str
    label: str
    value: int
    conversion_pct: float = 0
    previous_conversion_pct: float = 0


class MarketingIntelligenceProductOut(BaseModel):
    product_id: Optional[str]
    name: str
    category: Optional[str] = None
    views: int = 0
    carts: int = 0
    orders: int = 0
    quantity_sold: int = 0
    revenue: float = 0
    average_ticket: float = 0
    conversion_rate: float = 0


class MarketingIntelligencePromotionOut(BaseModel):
    id: str
    name: str
    promotion_type: str
    code: Optional[str] = None
    uses: int = 0
    orders: int = 0
    revenue: float = 0
    discount: float = 0
    average_ticket: float = 0


class MarketingIntelligenceDashboardOut(BaseModel):
    period: str
    date_from: str
    date_to: str
    generated_at: str
    kpis: list[MarketingIntelligenceKpiOut]
    campaigns: list[MarketingIntelligenceCampaignOut]
    channels: list[MarketingIntelligenceChannelOut]
    funnel: list[MarketingIntelligenceFunnelStepOut]
    products: list[MarketingIntelligenceProductOut]
    promotions: list[MarketingIntelligencePromotionOut]


class MarketingGoalBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    metric_key: MarketingGoalMetricKey
    target_value: float
    baseline_value: Optional[float] = None
    comparison_direction: MarketingComparisonDirection = "increase"
    period_start: date
    period_end: date
    status: MarketingGoalStatus = "active"
    priority: MarketingPriority = "medium"
    campaign_id: Optional[str] = None
    traffic_campaign_id: Optional[str] = None
    coupon_id: Optional[str] = None
    promotion_id: Optional[str] = None
    product_id: Optional[str] = None
    channel: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class MarketingGoalCreate(MarketingGoalBase):
    pass


class MarketingGoalUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    metric_key: Optional[MarketingGoalMetricKey] = None
    target_value: Optional[float] = None
    baseline_value: Optional[float] = None
    comparison_direction: Optional[MarketingComparisonDirection] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    status: Optional[MarketingGoalStatus] = None
    priority: Optional[MarketingPriority] = None
    campaign_id: Optional[str] = None
    traffic_campaign_id: Optional[str] = None
    coupon_id: Optional[str] = None
    promotion_id: Optional[str] = None
    product_id: Optional[str] = None
    channel: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = None
    metadata: Optional[dict] = None


class MarketingGoalStatusUpdate(BaseModel):
    status: MarketingGoalStatus


class MarketingGoalProgressOut(BaseModel):
    current_value: float = 0
    baseline_value: Optional[float] = None
    target_value: float
    progress_pct: float = 0
    remaining_value: Optional[float] = None
    reached: bool = False
    metric_label: str
    unit: str = "number"
    calculated_at: str


class MarketingGoalOut(MarketingGoalBase):
    id: str
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    progress: MarketingGoalProgressOut

    model_config = {"from_attributes": True}


class MarketingTimelineEventBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    event_type: MarketingTimelineEventType
    event_date: datetime
    impact_level: MarketingTimelineImpact = "medium"
    category: Optional[str] = Field(default=None, max_length=60)
    tags: list[str] = Field(default_factory=list)
    attachment_url: Optional[str] = None
    attachment_type: Optional[MarketingAttachmentType] = None
    goal_id: Optional[str] = None
    campaign_id: Optional[str] = None
    traffic_campaign_id: Optional[str] = None
    coupon_id: Optional[str] = None
    promotion_id: Optional[str] = None
    product_id: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class MarketingTimelineEventCreate(MarketingTimelineEventBase):
    pass


class MarketingTimelineEventUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    event_type: Optional[MarketingTimelineEventType] = None
    event_date: Optional[datetime] = None
    impact_level: Optional[MarketingTimelineImpact] = None
    category: Optional[str] = Field(default=None, max_length=60)
    tags: Optional[list[str]] = None
    attachment_url: Optional[str] = None
    attachment_type: Optional[MarketingAttachmentType] = None
    goal_id: Optional[str] = None
    campaign_id: Optional[str] = None
    traffic_campaign_id: Optional[str] = None
    coupon_id: Optional[str] = None
    promotion_id: Optional[str] = None
    product_id: Optional[str] = None
    metadata: Optional[dict] = None


class MarketingTimelineEventOut(MarketingTimelineEventBase):
    id: str
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MarketingPlanningOut(BaseModel):
    goals: list[MarketingGoalOut]
    timeline: list[MarketingTimelineEventOut]

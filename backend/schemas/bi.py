from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel


PeriodKey = Literal["today", "7d", "30d", "90d", "month", "previous_month"]
GranularityKey = Literal["day", "week", "month"]
InsightImpact = Literal["low", "medium", "high", "critical"]
InsightStatus = Literal["active", "resolved", "ignored", "postponed"]


class BIQuery(BaseModel):
    period: PeriodKey = "30d"
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class BIKpiOut(BaseModel):
    key: str
    label: str
    value: float
    unit: str = "number"
    helper: Optional[str] = None


class BITimeSeriesPointOut(BaseModel):
    label: str
    date: Optional[str] = None
    revenue: float = 0
    orders: int = 0
    average_ticket: float = 0


class BIProductOut(BaseModel):
    product_id: Optional[str]
    name: str
    category: Optional[str] = None
    total_orders: int = 0
    quantity_sold: int = 0
    total_revenue: float = 0
    share_pct: float = 0
    is_top_20_percent: bool = False


class BICustomerSegmentOut(BaseModel):
    key: str
    name: str
    description: str
    total_customers: int


class BITopCustomerOut(BaseModel):
    customer_id: str
    name: str
    total_orders: int = 0
    total_spent: float = 0
    avg_ticket: float = 0
    last_order_at: Optional[str] = None


class BIFunnelStepOut(BaseModel):
    key: str
    label: str
    value: int
    conversion_pct: float = 0


class BIInsightOut(BaseModel):
    id: str
    insight_type: str
    title: str
    description: str
    impact_level: InsightImpact
    recommendation: str
    actionable: bool = True
    status: str = "active"
    persisted: bool = False


class BIRecommendationOut(BaseModel):
    id: str
    insight_id: str
    title: str
    priority: InsightImpact
    action: str
    reason: str
    expected_impact: str
    target_module: str
    persisted: bool = False


class BIInsightStatusUpdate(BaseModel):
    status: InsightStatus


class BIOverviewOut(BaseModel):
    period: str
    date_from: str
    date_to: str
    generated_at: str
    kpis: list[BIKpiOut]
    sales: list[BITimeSeriesPointOut]
    products: list[BIProductOut]
    customer_segments: list[BICustomerSegmentOut]
    top_customers: list[BITopCustomerOut]
    funnel: list[BIFunnelStepOut]
    insights: list[BIInsightOut]
    recommendations: list[BIRecommendationOut]


class BISalesOut(BaseModel):
    period: str
    date_from: str
    date_to: str
    by_day: list[BITimeSeriesPointOut]
    by_hour: list[dict]


class BICustomersOut(BaseModel):
    period: str
    date_from: str
    date_to: str
    segments: list[BICustomerSegmentOut]
    top_customers: list[BITopCustomerOut]


class BIProductsOut(BaseModel):
    period: str
    date_from: str
    date_to: str
    products: list[BIProductOut]


class BIMarketingOut(BaseModel):
    period: str
    date_from: str
    date_to: str
    spend: float
    revenue: float
    roas: float
    events_by_type: list[dict]
    funnel: list[BIFunnelStepOut]


class BIOperationsOut(BaseModel):
    period: str
    date_from: str
    date_to: str
    delayed_deliveries: int
    avg_total_time_minutes: float
    avg_delivery_time_minutes: float
    orders_by_status: list[dict]


class BIRunAnalysisOut(BaseModel):
    status: str
    message: str
    insights: list[BIInsightOut]
    recommendations: list[BIRecommendationOut]

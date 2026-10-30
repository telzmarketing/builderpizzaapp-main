from __future__ import annotations

from datetime import date
from datetime import date as CalendarDate
from typing import Literal, Optional

from pydantic import BaseModel, Field


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


class BINeighborhoodOut(BaseModel):
    neighborhood: str
    city: Optional[str] = None
    visitors: int = 0
    sessions: int = 0
    pageviews: int = 0
    visitor_orders: int = 0
    orders: int = 0
    revenue: float = 0
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
    neighborhoods: list[BINeighborhoodOut] = []
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


class BIKdsAnalyticsOut(BaseModel):
    period: str
    date_from: str
    date_to: str
    generated_at: str
    orders: dict
    flow_minutes: dict
    production: dict
    definitions: list[str]


class BIRunAnalysisOut(BaseModel):
    status: str
    message: str
    insights: list[BIInsightOut]
    recommendations: list[BIRecommendationOut]


MobilePeriod = Literal["today", "7d", "30d", "90d", "month"]
MobileCompare = Literal["previous_month", "previous_period", "none"]
MobileMonthly = Literal["6m", "12m", "year", "previous_year"]


class BIMobileQuery(BaseModel):
    date: CalendarDate | None = None
    period: MobilePeriod = "today"
    compare: MobileCompare = "previous_month"
    partial: bool = True
    monthly: MobileMonthly = "6m"
    view: Literal["all", "orders", "attendance", "evolution", "general"] = "all"
    grouping: Literal["day", "week"] = "day"


class BIMobileTotals(BaseModel):
    orders: int = 0
    valid_orders: int = 0
    pizzas: int = 0
    revenue: float = 0
    average_ticket: float = 0
    cancelled_orders: int = 0
    cancelled_value: float = 0
    completed_orders: int = 0
    active_orders: int = 0
    gross_sales: float = 0
    discounts: float = 0
    forecast_revenue: float = 0
    daily_revenue: float = 0
    daily_orders: float = 0
    best_day: str | None = None
    status_counts: dict[str, int] = Field(default_factory=dict)


class BIMobileSalesPoint(BaseModel):
    label: str
    date: str
    previous_date: str | None = None
    revenue: float = 0
    orders: int = 0
    pizzas: int = 0
    previous_revenue: float | None = None
    previous_orders: int | None = None
    previous_pizzas: int | None = None
    comparison: dict = Field(default_factory=dict)


class BIMobileAnalyticsOut(BaseModel):
    period: dict
    totals: BIMobileTotals
    previous_totals: BIMobileTotals | None
    comparison: dict
    sales: list[BIMobileSalesPoint]
    monthly: list[dict]
    attendance: dict
    payments: list[dict]
    channels: list[dict]
    history: dict
    generated_at: str
    definitions: list[str]


class BIMobileAnalysisOut(BaseModel):
    generated_at: str
    engine: Literal["calculated", "ai_assisted"] = "calculated"
    ai_note: str = "Análise calculada a partir dos registros persistidos."
    period: dict
    summary: str
    facts: list[str]
    trends: list[str]
    attention: list[str]
    recommendations: list[str]

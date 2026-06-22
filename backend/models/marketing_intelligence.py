from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Index, String, Text

from backend.database import Base


class MarketingGoal(Base):
    __tablename__ = "marketing_goals"

    id = Column(String, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    metric_key = Column(String(40), nullable=False)
    target_value = Column(Float, nullable=False)
    baseline_value = Column(Float, nullable=True)
    comparison_direction = Column(String(20), nullable=False, default="increase")
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="active")
    priority = Column(String(20), nullable=False, default="medium")
    campaign_id = Column(String, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    traffic_campaign_id = Column(String, ForeignKey("traffic_campaigns.id", ondelete="SET NULL"), nullable=True)
    coupon_id = Column(String, ForeignKey("coupons.id", ondelete="SET NULL"), nullable=True)
    promotion_id = Column(String, ForeignKey("product_promotions.id", ondelete="SET NULL"), nullable=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    channel = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=False, default="{}")
    created_by = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_marketing_goals_status", "status"),
        Index("ix_marketing_goals_metric_key", "metric_key"),
        Index("ix_marketing_goals_period", "period_start", "period_end"),
        Index("ix_marketing_goals_campaign_id", "campaign_id"),
        Index("ix_marketing_goals_traffic_campaign_id", "traffic_campaign_id"),
        Index("ix_marketing_goals_coupon_id", "coupon_id"),
        Index("ix_marketing_goals_promotion_id", "promotion_id"),
        Index("ix_marketing_goals_product_id", "product_id"),
        Index("ix_marketing_goals_channel", "channel"),
    )


class MarketingTimelineEvent(Base):
    __tablename__ = "marketing_timeline_events"

    id = Column(String, primary_key=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    event_type = Column(String(60), nullable=False)
    event_date = Column(DateTime(timezone=True), nullable=False)
    impact_level = Column(String(20), nullable=False, default="medium")
    category = Column(String(60), nullable=True)
    tags = Column(Text, nullable=False, default="[]")
    attachment_url = Column(Text, nullable=True)
    attachment_type = Column(String(20), nullable=True)
    goal_id = Column(String, ForeignKey("marketing_goals.id", ondelete="SET NULL"), nullable=True)
    campaign_id = Column(String, ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True)
    traffic_campaign_id = Column(String, ForeignKey("traffic_campaigns.id", ondelete="SET NULL"), nullable=True)
    coupon_id = Column(String, ForeignKey("coupons.id", ondelete="SET NULL"), nullable=True)
    promotion_id = Column(String, ForeignKey("product_promotions.id", ondelete="SET NULL"), nullable=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    metadata_json = Column(Text, nullable=False, default="{}")
    created_by = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_marketing_timeline_events_date", "event_date"),
        Index("ix_marketing_timeline_events_type", "event_type"),
        Index("ix_marketing_timeline_events_category", "category"),
        Index("ix_marketing_timeline_events_impact", "impact_level"),
        Index("ix_marketing_timeline_events_goal_id", "goal_id"),
        Index("ix_marketing_timeline_events_campaign_id", "campaign_id"),
        Index("ix_marketing_timeline_events_traffic_campaign_id", "traffic_campaign_id"),
        Index("ix_marketing_timeline_events_coupon_id", "coupon_id"),
        Index("ix_marketing_timeline_events_promotion_id", "promotion_id"),
        Index("ix_marketing_timeline_events_product_id", "product_id"),
    )

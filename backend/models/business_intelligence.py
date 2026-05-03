from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint

from backend.database import Base


class BusinessInsight(Base):
    __tablename__ = "business_insights"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_business_insights_dedupe_key"),
    )

    id = Column(String, primary_key=True)
    dedupe_key = Column(String(300), nullable=False)
    insight_type = Column(String(40), nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=False)
    impact_level = Column(String(20), nullable=False, default="medium")
    recommendation = Column(Text, nullable=False)
    actionable = Column(Boolean, nullable=False, default=True)
    status = Column(String(20), nullable=False, default="active")
    period = Column(String(30), nullable=False, default="30d")
    date_from = Column(Date, nullable=True)
    date_to = Column(Date, nullable=True)
    source = Column(String(40), nullable=False, default="rules")
    metadata_json = Column(Text, nullable=False, default="{}")
    created_by = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class ProductPerformance(Base):
    __tablename__ = "product_performance"
    __table_args__ = (
        UniqueConstraint("metric_date", "product_id", name="uq_product_performance_date_product"),
    )

    id = Column(String, primary_key=True)
    metric_date = Column(Date, nullable=False)
    product_id = Column(String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name_snapshot = Column(String(200), nullable=False)
    category_snapshot = Column(String(100), nullable=True)
    total_orders = Column(Integer, nullable=False, default=0)
    quantity_sold = Column(Integer, nullable=False, default=0)
    total_revenue = Column(Float, nullable=False, default=0.0)
    margin_estimate = Column(Float, nullable=True)
    is_top_20_percent = Column(Boolean, nullable=False, default=False)
    last_updated = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

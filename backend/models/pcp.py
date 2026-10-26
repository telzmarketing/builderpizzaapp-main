"""Reviewable weekly production planning projections."""
from datetime import datetime, timezone
from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, JSON, String, UniqueConstraint
from backend.database import Base


class PcpWeeklyPlan(Base):
    __tablename__ = "pcp_weekly_plans"
    __table_args__ = (
        UniqueConstraint("tenant_id", "week_start", name="uq_pcp_weekly_plans_tenant_week"),
        Index("ix_pcp_weekly_plans_tenant_status", "tenant_id", "status"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    week_start = Column(Date, nullable=False)
    status = Column(String(20), nullable=False, default="draft", server_default="draft")
    source_window_start = Column(Date, nullable=False)
    source_window_end = Column(Date, nullable=False)
    suggestions_json = Column(JSON, nullable=False, default=list, server_default="[]")
    approved_by = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

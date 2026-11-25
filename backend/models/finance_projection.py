"""Persistent, tenant-scoped queue for finance projection failures."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from backend.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FinanceProjectionEvent(Base):
    """Durable retry record for a failed financial projection.

    The payload is intentionally stored as redacted JSON by
    ``FinanceProjectionQueue``.  This table is not the source of truth for a
    sale or payment; it only preserves enough event context to retry the
    projection safely.
    """

    __tablename__ = "finance_projection_events"

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    event_type = Column(String(120), nullable=False)
    event_version = Column(Integer, nullable=False, default=1)
    aggregate_type = Column(String(80), nullable=True)
    aggregate_id = Column(String(160), nullable=True)
    source_type = Column(String(80), nullable=True)
    source_id = Column(String(160), nullable=True)
    payload_json = Column(Text, nullable=False, default="{}")
    dedupe_key = Column(String(240), nullable=False)
    correlation_id = Column(String(160), nullable=True)
    causation_id = Column(String(160), nullable=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=5)
    available_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    locked_by = Column(String(160), nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "dedupe_key", name="uq_finance_projection_events_tenant_dedupe"),
        CheckConstraint(
            "status IN ('pending','processing','processed','failed','dead')",
            name="ck_finance_projection_events_status",
        ),
        CheckConstraint("attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts", name="ck_finance_projection_events_attempts"),
        Index("ix_finance_projection_events_claim", "tenant_id", "status", "available_at", "created_at"),
        Index("ix_finance_projection_events_aggregate", "tenant_id", "aggregate_type", "aggregate_id"),
    )

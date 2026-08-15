"""Operational control-plane records owned by Alembic.

The Master Central only stores redacted error metadata and worker liveness.
Provider payloads, credentials, request bodies and tracebacks never belong in
these tables.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text

from backend.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlatformErrorEvent(Base):
    __tablename__ = "platform_error_events"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info','warning','error','critical')",
            name="ck_platform_error_events_severity",
        ),
        CheckConstraint(
            "status IN ('open','acknowledged','resolved')",
            name="ck_platform_error_events_status",
        ),
        CheckConstraint(
            "occurrence_count > 0",
            name="ck_platform_error_events_occurrence_count",
        ),
        Index(
            "ix_platform_error_events_status_severity_seen",
            "status",
            "severity",
            "last_seen_at",
        ),
        Index(
            "ix_platform_error_events_tenant_seen",
            "tenant_id",
            "last_seen_at",
        ),
        Index("ix_platform_error_events_request_id", "request_id"),
        Index(
            "uq_platform_error_events_open_fingerprint",
            text("coalesce(tenant_id, '')"),
            "source",
            "fingerprint",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(
        String,
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
    )
    fingerprint = Column(String(64), nullable=False)
    source = Column(String(80), nullable=False)
    severity = Column(String(20), nullable=False, default="error")
    status = Column(String(20), nullable=False, default="open")
    error_code = Column(String(100), nullable=True)
    exception_type = Column(String(160), nullable=True)
    message = Column(Text, nullable=False)
    method = Column(String(12), nullable=True)
    path = Column(String(300), nullable=True)
    request_id = Column(String(100), nullable=True)
    correlation_id = Column(String(100), nullable=True)
    occurrence_count = Column(Integer, nullable=False, default=1)
    first_seen_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_seen_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    sample_context_json = Column(Text, nullable=False, default="{}")
    acknowledged_by = Column(
        String,
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledgement_note = Column(Text, nullable=True)
    resolved_by = Column(
        String,
        ForeignKey("admin_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class PlatformWorkerHeartbeat(Base):
    __tablename__ = "platform_worker_heartbeats"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running','idle','degraded','stopped')",
            name="ck_platform_worker_heartbeats_status",
        ),
        UniqueConstraint(
            "worker_key",
            "instance_key",
            name="uq_platform_worker_heartbeats_worker_instance",
        ),
        Index(
            "ix_platform_worker_heartbeats_queue_seen",
            "queue_key",
            "last_heartbeat_at",
        ),
        Index(
            "ix_platform_worker_heartbeats_tenant_seen",
            "tenant_id",
            "last_heartbeat_at",
        ),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(
        String,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
    )
    worker_key = Column(String(100), nullable=False)
    instance_key = Column(String(120), nullable=False)
    queue_key = Column(String(80), nullable=False)
    status = Column(String(20), nullable=False, default="running")
    version = Column(String(80), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

"""Tenant-scoped configuration and queue for the ERP print center."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from backend.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


_JSON = JSON().with_variant(JSONB(), "postgresql")


class PrintStation(Base):
    __tablename__ = "print_stations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_print_stations_tenant_code"),
        Index("ix_print_stations_tenant_active", "tenant_id", "active"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    code = Column(String(80), nullable=False)
    name = Column(String(160), nullable=False)
    hostname = Column(String(255), nullable=True)
    connected = Column(Boolean, nullable=False, default=False, server_default="false")
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class PrintPrinter(Base):
    __tablename__ = "print_printers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "station_id", "code", name="uq_print_printers_station_code"),
        Index("ix_print_printers_tenant_active", "tenant_id", "active"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    station_id = Column(String(36), ForeignKey("print_stations.id", ondelete="RESTRICT"), nullable=False)
    code = Column(String(80), nullable=False)
    name = Column(String(160), nullable=False)
    connection_type = Column(String(20), nullable=False, default="windows", server_default="windows")
    driver_name = Column(String(160), nullable=True)
    status = Column(String(20), nullable=False, default="unknown", server_default="unknown")
    printer_type = Column(String(20), nullable=False, default="standard", server_default="standard")
    capabilities = Column(_JSON, nullable=False, default=dict, server_default="{}")
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class PrintRoutingRule(Base):
    __tablename__ = "print_routing_rules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sector", "document_type", "printer_id", name="uq_print_routing_rule"),
        Index("ix_print_routing_rules_tenant_sector", "tenant_id", "sector"),
        CheckConstraint("copies > 0 AND copies <= 20", name="ck_print_routing_rule_copies"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    sector = Column(String(40), nullable=False)
    document_type = Column(String(60), nullable=False)
    printer_id = Column(String(36), ForeignKey("print_printers.id", ondelete="RESTRICT"), nullable=False)
    copies = Column(Integer, nullable=False, default=1, server_default="1")
    priority = Column(Integer, nullable=False, default=0, server_default="0")
    enabled = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class PrintJob(Base):
    __tablename__ = "print_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_print_jobs_tenant_idempotency"),
        UniqueConstraint("tenant_id", "external_job_id", name="uq_print_jobs_tenant_external_id"),
        Index("ix_print_jobs_tenant_status_priority", "tenant_id", "status", "priority", "created_at"),
        CheckConstraint("status IN ('pending','received','queued','processing','spooler_submitted','printed','error','cancelled','uncertain')", name="ck_print_jobs_status"),
        CheckConstraint("copies > 0 AND copies <= 20", name="ck_print_jobs_copies"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    station_id = Column(String(36), ForeignKey("print_stations.id", ondelete="RESTRICT"), nullable=True)
    printer_id = Column(String(36), ForeignKey("print_printers.id", ondelete="RESTRICT"), nullable=False)
    external_job_id = Column(String(120), nullable=False)
    idempotency_key = Column(String(200), nullable=False)
    sector = Column(String(40), nullable=False)
    document_type = Column(String(60), nullable=False)
    document_format = Column(String(20), nullable=False)
    payload_ref = Column(String(1000), nullable=False)
    payload_metadata = Column(_JSON, nullable=False, default=dict, server_default="{}")
    copies = Column(Integer, nullable=False, default=1, server_default="1")
    priority = Column(Integer, nullable=False, default=0, server_default="0")
    status = Column(String(30), nullable=False, default="pending", server_default="pending")
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    last_error = Column(Text, nullable=True)
    created_by_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class PrintJobEvent(Base):
    __tablename__ = "print_job_events"
    __table_args__ = (Index("ix_print_job_events_tenant_job_created", "tenant_id", "job_id", "created_at"),)

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    job_id = Column(String(36), ForeignKey("print_jobs.id", ondelete="CASCADE"), nullable=False)
    from_status = Column(String(30), nullable=True)
    to_status = Column(String(30), nullable=False)
    message = Column(String(500), nullable=True)
    actor_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

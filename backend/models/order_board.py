"""Tenant-scoped, read-only order board configuration and device credentials."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String

from backend.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrderBoardSetting(Base):
    __tablename__ = "order_board_settings"
    __table_args__ = (
        CheckConstraint("production_sla_minutes BETWEEN 1 AND 240", name="ck_order_board_settings_production_sla"),
        CheckConstraint("dispatch_sla_minutes BETWEEN 1 AND 120", name="ck_order_board_settings_dispatch_sla"),
        CheckConstraint("completed_window_seconds BETWEEN 30 AND 900", name="ck_order_board_settings_completed_window"),
        CheckConstraint("polling_interval_seconds BETWEEN 3 AND 60", name="ck_order_board_settings_polling_interval"),
        CheckConstraint("max_orders BETWEEN 10 AND 200", name="ck_order_board_settings_max_orders"),
    )

    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    production_sla_minutes = Column(Integer, nullable=False, default=20)
    dispatch_sla_minutes = Column(Integer, nullable=False, default=5)
    completed_window_seconds = Column(Integer, nullable=False, default=120)
    polling_interval_seconds = Column(Integer, nullable=False, default=5)
    sound_enabled = Column(Boolean, nullable=False, default=False)
    max_orders = Column(Integer, nullable=False, default=50)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class OrderBoardDevice(Base):
    __tablename__ = "order_board_devices"
    __table_args__ = (
        CheckConstraint("status IN ('active','revoked')", name="ck_order_board_devices_status"),
        Index("ix_order_board_devices_tenant_status", "tenant_id", "status"),
        Index("uq_order_board_devices_token_hash", "token_hash", unique=True),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(120), nullable=False)
    token_hash = Column(String(64), nullable=True)
    status = Column(String(20), nullable=False, default="active")
    activated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)


class OrderBoardActivation(Base):
    __tablename__ = "order_board_activations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','claimed','expired','cancelled')",
            name="ck_order_board_activations_status",
        ),
        Index("uq_order_board_activations_code_prefix", "code_prefix", unique=True),
        Index("ix_order_board_activations_status_expires", "status", "expires_at"),
        Index("uq_order_board_activations_claim_hash", "claim_token_hash", unique=True),
    )

    id = Column(String, primary_key=True)
    code_prefix = Column(String(4), nullable=False)
    code_salt = Column(String(32), nullable=False)
    code_hash = Column(String(64), nullable=False)
    claim_token_hash = Column(String(64), nullable=False)
    failed_attempts = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="pending")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True)
    device_id = Column(String, ForeignKey("order_board_devices.id", ondelete="SET NULL"), nullable=True)
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

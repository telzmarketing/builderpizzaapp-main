from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.database import Base


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class WhatsAppGatewayInstance(Base):
    __tablename__ = "whatsapp_gateway_instances"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    company_id = Column(String(80), nullable=False, default="default", index=True)
    name = Column(String(180), nullable=False)
    phone_number = Column(String(40), nullable=True, index=True)
    provider = Column(String(40), nullable=False, default="baileys", index=True)
    status = Column(String(40), nullable=False, default="created", index=True)
    session_key = Column(String(255), nullable=True)
    qr_code = Column(Text, nullable=True)
    connected_at = Column(DateTime(timezone=True), nullable=True)
    disconnected_at = Column(DateTime(timezone=True), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), default=_now_utc, index=True)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    logs = relationship("WhatsAppGatewayLog", back_populates="instance", cascade="all, delete-orphan")


class WhatsAppGatewayLog(Base):
    __tablename__ = "whatsapp_gateway_logs"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    company_id = Column(String(80), nullable=False, default="default", index=True)
    instance_id = Column(
        String,
        ForeignKey("whatsapp_gateway_instances.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = Column(String(80), nullable=False, index=True)
    status = Column(String(40), nullable=False, default="info", index=True)
    message = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), default=_now_utc, index=True)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

    instance = relationship("WhatsAppGatewayInstance", back_populates="logs")


class WhatsAppGatewayUpdateLog(Base):
    __tablename__ = "whatsapp_gateway_update_logs"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    company_id = Column(String(80), nullable=False, default="default", index=True)
    package_name = Column(String(160), nullable=False, default="@whiskeysockets/baileys")
    current_version = Column(String(80), nullable=True)
    available_version = Column(String(80), nullable=True)
    update_type = Column(String(30), nullable=True)
    risk_level = Column(String(30), nullable=True)
    environment = Column(String(40), nullable=False, default="production")
    action = Column(String(80), nullable=False, default="check")
    status = Column(String(40), nullable=False, default="pending", index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    rollback_version = Column(String(80), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc, index=True)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)


class WhatsAppGatewaySchedulerSettings(Base):
    __tablename__ = "whatsapp_gateway_scheduler_settings"

    id = Column(String, primary_key=True, default="default")
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    company_id = Column(String(80), nullable=False, default="default", index=True)
    auto_health_check_enabled = Column(Boolean, nullable=False, default=True)
    morning_check_time = Column(String(5), nullable=False, default="06:00")
    evening_check_time = Column(String(5), nullable=False, default="18:00")
    auto_update_check_enabled = Column(Boolean, nullable=False, default=True)
    auto_update_staging_enabled = Column(Boolean, nullable=False, default=False)
    auto_update_production_enabled = Column(Boolean, nullable=False, default=False)
    notify_admin_enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_now_utc)
    updated_at = Column(DateTime(timezone=True), default=_now_utc, onupdate=_now_utc)

"""Tenant-scoped persistence for the Production Vision backend slice."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, String, Text

from backend.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProductionVisionCamera(Base):
    __tablename__ = "production_vision_cameras"
    __table_args__ = (
        Index("uq_production_vision_cameras_tenant_identifier", "tenant_id", "identifier", unique=True),
        Index("ix_production_vision_cameras_tenant_station", "tenant_id", "station_id"),
        CheckConstraint("status IN ('active','inactive')", name="ck_production_vision_camera_status"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    name = Column(String(120), nullable=False)
    identifier = Column(String(80), nullable=False)
    manufacturer = Column(String(120))
    model = Column(String(120))
    ip_address = Column(String(120))
    port = Column(Integer)
    protocol = Column(String(20), nullable=False, default="rtsp", server_default="rtsp")
    connection_url = Column(Text)
    username = Column(String(120))
    credentials_encrypted = Column(Text)
    station_id = Column(String(20), nullable=False)
    resolution = Column(String(40))
    orientation = Column(String(40))
    installation_height_cm = Column(Integer)
    status = Column(String(12), nullable=False, default="inactive", server_default="inactive")
    last_connected_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ProductionVisionSession(Base):
    __tablename__ = "production_vision_sessions"
    __table_args__ = (
        Index("uq_production_vision_sessions_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_production_vision_sessions_idempotency", "tenant_id", "idempotency_key", unique=True),
        Index("ix_production_vision_sessions_tenant_status", "tenant_id", "status", "started_at"),
        ForeignKeyConstraint(["tenant_id", "production_unit_id"], ["production_units.tenant_id", "production_units.id"], ondelete="RESTRICT"),
        CheckConstraint("status IN ('active','complete','partial')", name="ck_production_vision_session_status"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    production_unit_id = Column(String, nullable=False)
    stage = Column(String(40), nullable=False)
    operator_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"))
    status = Column(String(12), nullable=False, default="active", server_default="active")
    idempotency_key = Column(String(200), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at = Column(DateTime(timezone=True))
    expected_photo_count = Column(Integer, nullable=False, default=5, server_default="5")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ProductionVisionPhoto(Base):
    __tablename__ = "production_vision_photos"
    __table_args__ = (
        Index("uq_production_vision_photos_idempotency", "tenant_id", "session_id", "idempotency_key", unique=True),
        Index("ix_production_vision_photos_session_captured", "tenant_id", "session_id", "captured_at"),
        ForeignKeyConstraint(["tenant_id", "session_id"], ["production_vision_sessions.tenant_id", "production_vision_sessions.id"], ondelete="RESTRICT"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    session_id = Column(String, nullable=False)
    idempotency_key = Column(String(200), nullable=False)
    captured_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    original_storage_key = Column(Text, nullable=False)
    processed_storage_key = Column(Text)
    content_type = Column(String(120))
    width = Column(Integer)
    height = Column(Integer)
    byte_size = Column(Integer)
    is_final = Column(Boolean, nullable=False, default=False, server_default="false")
    metadata_json = Column(JSON, nullable=False, default=dict, server_default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

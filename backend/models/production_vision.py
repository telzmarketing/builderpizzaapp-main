"""Tenant-scoped persistence for Production Vision."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, String, Text, text

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
    manufacturer = Column(String(120)); model = Column(String(120)); ip_address = Column(String(120)); port = Column(Integer)
    protocol = Column(String(20), nullable=False, default="rtsp", server_default="rtsp")
    connection_url = Column(Text); username = Column(String(120)); credentials_encrypted = Column(Text)
    station_id = Column(String(20), nullable=False); resolution = Column(String(40)); orientation = Column(String(40)); installation_height_cm = Column(Integer)
    status = Column(String(12), nullable=False, default="inactive", server_default="inactive")
    last_connected_at = Column(DateTime(timezone=True)); created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow); updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ProductionVisionZone(Base):
    __tablename__ = "production_vision_zones"
    __table_args__ = (
        Index("uq_production_vision_zones_tenant_identifier", "tenant_id", "identifier", unique=True),
        Index("ix_production_vision_zones_tenant_station", "tenant_id", "station_id"),
        CheckConstraint("status IN ('active','inactive')", name="ck_production_vision_zone_status"),
    )
    id = Column(String(36), primary_key=True); tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    name = Column(String(120), nullable=False); identifier = Column(String(80), nullable=False); station_id = Column(String(20), nullable=False)
    camera_id = Column(String(36), ForeignKey("production_vision_cameras.id", ondelete="SET NULL")); status = Column(String(12), nullable=False, default="active", server_default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow); updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ProductionVisionSettings(Base):
    __tablename__ = "production_vision_settings"
    __table_args__ = (Index("uq_production_vision_settings_tenant", "tenant_id", unique=True),)
    id = Column(String(36), primary_key=True); tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    photos_per_session = Column(Integer, nullable=False, default=5, server_default="5"); max_width_px = Column(Integer, nullable=False, default=1280, server_default="1280")
    image_format = Column(String(10), nullable=False, default="webp", server_default="webp"); image_quality = Column(Integer, nullable=False, default=80, server_default="80"); retention_days = Column(Integer, nullable=False, default=7, server_default="7")
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class ProductionVisionSession(Base):
    __tablename__ = "production_vision_sessions"
    __table_args__ = (
        Index("uq_production_vision_sessions_tenant_id_id", "tenant_id", "id", unique=True), Index("uq_production_vision_sessions_idempotency", "tenant_id", "idempotency_key", unique=True), Index("ix_production_vision_sessions_tenant_status", "tenant_id", "status", "started_at"),
        ForeignKeyConstraint(["tenant_id", "production_unit_id"], ["production_units.tenant_id", "production_units.id"], ondelete="RESTRICT"), ForeignKeyConstraint(["tenant_id", "production_attempt_id"], ["production_attempts.tenant_id", "production_attempts.id"], ondelete="SET NULL"), CheckConstraint("status IN ('active','complete','partial')", name="ck_production_vision_session_status"),
    )
    id = Column(String(36), primary_key=True); tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False); production_unit_id = Column(String, nullable=False); production_attempt_id = Column(String, nullable=True)
    stage = Column(String(40), nullable=False); station_id = Column(String(20)); camera_id = Column(String(36), ForeignKey("production_vision_cameras.id", ondelete="SET NULL")); zone_id = Column(String(36), ForeignKey("production_vision_zones.id", ondelete="SET NULL")); operator_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"))
    status = Column(String(12), nullable=False, default="active", server_default="active"); idempotency_key = Column(String(200)); started_at = Column(DateTime(timezone=True), nullable=False, default=utcnow); completed_at = Column(DateTime(timezone=True)); expected_photo_count = Column(Integer, nullable=False, default=5, server_default="5"); created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ProductionVisionZoneOccupancy(Base):
    __tablename__ = "production_vision_zone_occupancies"
    __table_args__ = (
        Index("uq_production_vision_zone_occupancy_idempotency", "tenant_id", "idempotency_key", unique=True), Index("uq_production_vision_zone_active", "tenant_id", "zone_id", unique=True, postgresql_where=text("released_at IS NULL")),
        ForeignKeyConstraint(["tenant_id", "zone_id"], ["production_vision_zones.tenant_id", "production_vision_zones.id"], ondelete="RESTRICT"), ForeignKeyConstraint(["tenant_id", "session_id"], ["production_vision_sessions.tenant_id", "production_vision_sessions.id"], ondelete="RESTRICT"),
    )
    id = Column(String(36), primary_key=True); tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False); zone_id = Column(String(36), nullable=False); session_id = Column(String(36), nullable=False); idempotency_key = Column(String(200), nullable=False); occupied_at = Column(DateTime(timezone=True), nullable=False, default=utcnow); released_at = Column(DateTime(timezone=True))


class ProductionVisionPhoto(Base):
    __tablename__ = "production_vision_photos"
    __table_args__ = (Index("uq_production_vision_photos_idempotency", "tenant_id", "session_id", "idempotency_key", unique=True), Index("ix_production_vision_photos_session_captured", "tenant_id", "session_id", "captured_at"), ForeignKeyConstraint(["tenant_id", "session_id"], ["production_vision_sessions.tenant_id", "production_vision_sessions.id"], ondelete="RESTRICT"))
    id = Column(String(36), primary_key=True); tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False); session_id = Column(String(36), nullable=False); idempotency_key = Column(String(200), nullable=False); captured_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    original_storage_key = Column(Text, nullable=False); processed_storage_key = Column(Text); content_type = Column(String(120)); width = Column(Integer); height = Column(Integer); byte_size = Column(Integer); sha256 = Column(String(64)); processing_status = Column(String(20), nullable=False, default="pending", server_default="pending"); is_final = Column(Boolean, nullable=False, default=False, server_default="false"); metadata_json = Column(JSON, nullable=False, default=dict, server_default="{}"); created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ProductionVisionHistoryEvent(Base):
    __tablename__ = "production_vision_history_events"
    __table_args__ = (Index("ix_production_vision_history_session_created", "tenant_id", "session_id", "created_at"), Index("ix_production_vision_history_photo_created", "tenant_id", "photo_id", "created_at"))
    id = Column(String(36), primary_key=True); tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False); session_id = Column(String(36)); photo_id = Column(String(36)); event_type = Column(String(60), nullable=False); payload_json = Column(JSON, nullable=False, default=dict, server_default="{}"); created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class ProductionVisionIncident(Base):
    __tablename__ = "production_vision_incidents"
    __table_args__ = (Index("ix_production_vision_incidents_tenant_status", "tenant_id", "status", "created_at"), CheckConstraint("status IN ('open','resolved')", name="ck_production_vision_incident_status"))
    id = Column(String(36), primary_key=True); tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False); session_id = Column(String(36), ForeignKey("production_vision_sessions.id", ondelete="SET NULL")); photo_id = Column(String(36), ForeignKey("production_vision_photos.id", ondelete="SET NULL")); zone_id = Column(String(36), ForeignKey("production_vision_zones.id", ondelete="SET NULL")); code = Column(String(80), nullable=False); message = Column(Text, nullable=False); status = Column(String(12), nullable=False, default="open", server_default="open"); details_json = Column(JSON, nullable=False, default=dict, server_default="{}"); created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow); resolved_at = Column(DateTime(timezone=True))


class ProductionVisionEvidenceHold(Base):
    __tablename__ = "production_vision_evidence_holds"
    __table_args__ = (Index("uq_production_vision_holds_tenant_key", "tenant_id", "hold_key", unique=True), Index("ix_production_vision_holds_tenant_active", "tenant_id", "released_at"))
    id = Column(String(36), primary_key=True); tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False); hold_key = Column(String(160), nullable=False); session_id = Column(String(36), ForeignKey("production_vision_sessions.id", ondelete="RESTRICT")); photo_id = Column(String(36), ForeignKey("production_vision_photos.id", ondelete="RESTRICT")); reason = Column(Text, nullable=False); created_by = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL")); created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow); released_at = Column(DateTime(timezone=True))

"""Persistent ownership and access policy for uploaded media."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text

from backend.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TenantUploadAsset(Base):
    """An upload is owned by exactly one tenant once namespace enforcement is enabled."""

    __tablename__ = "tenant_upload_assets"
    __table_args__ = (
        CheckConstraint("visibility IN ('public', 'private')", name="ck_tenant_upload_assets_visibility"),
        Index("uq_tenant_upload_assets_storage_key", "storage_key", unique=True),
        Index("ix_tenant_upload_assets_tenant_visibility", "tenant_id", "visibility"),
    )

    id = Column(String(32), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False, index=True)
    storage_key = Column(String(700), nullable=False)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(120), nullable=False)
    byte_size = Column(Integer, nullable=False)
    visibility = Column(String(10), nullable=False, default="public")
    uploaded_by_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class TenantUploadLegacyReference(Base):
    """Audit queue for old un-namespaced media; never grants ownership implicitly."""

    __tablename__ = "tenant_upload_legacy_references"
    __table_args__ = (
        Index("uq_tenant_upload_legacy_reference", "source_table", "source_id", "source_column", unique=True),
        Index("ix_tenant_upload_legacy_references_tenant", "tenant_id"),
    )

    id = Column(String(32), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=True)
    source_table = Column(String(100), nullable=False)
    source_id = Column(String(120), nullable=False)
    source_column = Column(String(100), nullable=False)
    legacy_url = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

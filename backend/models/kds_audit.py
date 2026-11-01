"""Tenant-scoped delivery audit records for the final KDS handoff."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from backend.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DeliveryAudit(Base):
    __tablename__ = "delivery_audits"
    __table_args__ = (
        UniqueConstraint("tenant_id", "order_id", name="uq_delivery_audits_tenant_order"),
        CheckConstraint("status IN ('in_progress','completed','divergent')", name="ck_delivery_audits_status"),
        Index("ix_delivery_audits_tenant_status", "tenant_id", "status", "created_at"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(String, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    delivery_id = Column(String, ForeignKey("deliveries.id", ondelete="RESTRICT"), nullable=False)
    status = Column(String(20), nullable=False, default="in_progress", server_default="in_progress")
    started_by_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    handoff_by_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    handoff_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class DeliveryAuditItemConfirmation(Base):
    __tablename__ = "delivery_audit_item_confirmations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "audit_id", "order_item_id", name="uq_delivery_audit_items_item"),
        Index("ix_delivery_audit_items_tenant_audit", "tenant_id", "audit_id"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    audit_id = Column(String, ForeignKey("delivery_audits.id", ondelete="CASCADE"), nullable=False)
    order_item_id = Column(String, ForeignKey("order_items.id", ondelete="RESTRICT"), nullable=False)
    expected_quantity = Column(Integer, nullable=False)
    confirmed_quantity = Column(Integer, nullable=False, default=0, server_default="0")
    confirmed = Column(Boolean, nullable=False, default=False, server_default="false")
    actor_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class DeliveryAuditVolume(Base):
    __tablename__ = "delivery_audit_volumes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "audit_id", "sequence", name="uq_delivery_audit_volumes_sequence"),
        Index("ix_delivery_audit_volumes_tenant_audit", "tenant_id", "audit_id"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    audit_id = Column(String, ForeignKey("delivery_audits.id", ondelete="CASCADE"), nullable=False)
    order_item_id = Column(String, ForeignKey("order_items.id", ondelete="RESTRICT"), nullable=False)
    label_volume_id = Column(String, ForeignKey("label_volumes.id", ondelete="SET NULL"), nullable=True)
    sequence = Column(Integer, nullable=False)
    confirmed = Column(Boolean, nullable=False, default=False, server_default="false")
    actor_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class DeliveryAuditEvidence(Base):
    __tablename__ = "delivery_audit_evidence"
    __table_args__ = (
        UniqueConstraint("tenant_id", "audit_id", "asset_id", name="uq_delivery_audit_evidence_asset"),
        Index("ix_delivery_audit_evidence_tenant_audit", "tenant_id", "audit_id", "created_at"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    audit_id = Column(String, ForeignKey("delivery_audits.id", ondelete="CASCADE"), nullable=False)
    asset_id = Column(String, ForeignKey("tenant_upload_assets.id", ondelete="RESTRICT"), nullable=False)
    evidence_type = Column(String(40), nullable=False, default="handoff", server_default="handoff")
    captured_at = Column(DateTime(timezone=True), nullable=True)
    actor_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

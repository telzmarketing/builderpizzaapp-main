"""Membership between a global admin identity and a tenant."""
from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from backend.database import Base


class TenantMembership(Base):
    __tablename__ = "tenant_memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_tenant_memberships_tenant_user"),
        CheckConstraint("role IN ('owner', 'admin', 'manager', 'operator', 'viewer')", name="ck_tenant_memberships_role"),
        CheckConstraint("status IN ('active', 'invited', 'suspended', 'revoked')", name="ck_tenant_memberships_status"),
        Index("ix_tenant_memberships_user_status", "user_id", "status"),
        Index("ix_tenant_memberships_tenant_status", "tenant_id", "status"),
        Index("uq_tenant_memberships_default_active_user", "user_id", unique=True, postgresql_where=text("is_default = true AND status = 'active'")),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, default="active")
    is_default = Column(Boolean, nullable=False, default=False)
    invited_by = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    joined_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

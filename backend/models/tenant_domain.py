"""Public hostname bindings for tenant storefront experiences."""
from datetime import datetime, timezone
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, text
from backend.database import Base


class TenantDomain(Base):
    __tablename__ = "tenant_domains"
    __table_args__ = (
        CheckConstraint("kind IN ('subdomain', 'custom')", name="ck_tenant_domains_kind"),
        CheckConstraint("status IN ('pending', 'verified', 'active')", name="ck_tenant_domains_status"),
        Index("uq_tenant_domains_hostname_lower", text("lower(hostname)"), unique=True),
        Index("ix_tenant_domains_tenant_status", "tenant_id", "status"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    hostname = Column(String(253), nullable=False)
    kind = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    verification_token_hash = Column(String(64), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

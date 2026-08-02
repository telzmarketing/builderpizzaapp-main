"""Public hostname bindings for tenant storefront experiences."""
from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, String, Text, text
from backend.database import Base


class TenantDomain(Base):
    __tablename__ = "tenant_domains"
    __table_args__ = (
        CheckConstraint("kind IN ('subdomain', 'custom')", name="ck_tenant_domains_kind"),
        CheckConstraint(
            "status IN ('pending', 'awaiting_dns', 'verifying', 'verified', 'active', "
            "'dns_error', 'ssl_error', 'suspended', 'removed')",
            name="ck_tenant_domains_status",
        ),
        Index("uq_tenant_domains_hostname_lower", text("lower(hostname)"), unique=True),
        Index("ix_tenant_domains_tenant_status", "tenant_id", "status"),
        Index(
            "uq_tenant_domains_primary_active",
            "tenant_id",
            unique=True,
            postgresql_where=text("is_primary = true AND status = 'active'"),
        ),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    hostname = Column(String(253), nullable=False)
    kind = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    is_primary = Column(Boolean, nullable=False, default=False)
    verification_token_hash = Column(String(64), nullable=False)
    expected_txt_record = Column(String(500), nullable=True)
    expected_cname = Column(String(500), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    suspended_at = Column(DateTime(timezone=True), nullable=True)
    removed_at = Column(DateTime(timezone=True), nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    ssl_status = Column(String(30), nullable=False, default="pending")
    ssl_issued_at = Column(DateTime(timezone=True), nullable=True)
    ssl_expires_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

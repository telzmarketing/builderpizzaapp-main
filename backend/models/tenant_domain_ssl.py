"""Persistent certificate requests; privileged work is performed outside the API."""
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, UniqueConstraint, text

from backend.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class TenantDomainCertificateJob(Base):
    __tablename__ = "tenant_domain_certificate_jobs"
    __table_args__ = (
        ForeignKeyConstraint(["domain_id", "tenant_id"], ["tenant_domains.id", "tenant_domains.tenant_id"], ondelete="RESTRICT", name="fk_domain_ssl_job_owner"),
        CheckConstraint("status IN ('queued','running','succeeded','failed','cancelled')", name="ck_domain_ssl_job_status"),
        CheckConstraint("attempts >= 0", name="ck_domain_ssl_job_attempts"),
        UniqueConstraint("domain_id", "idempotency_key_hash", name="uq_domain_ssl_job_request"),
        Index("uq_domain_ssl_job_open", "domain_id", unique=True, postgresql_where=text("status IN ('queued','running')"), sqlite_where=text("status IN ('queued','running')")),
        Index("ix_domain_ssl_job_queue", "status", "created_at"),
        Index("ix_domain_ssl_job_tenant_created", "tenant_id", "created_at"),
    )
    id = Column(String, primary_key=True)
    domain_id = Column(String, nullable=False)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    hostname = Column(String(253), nullable=False)
    email = Column(String(254), nullable=False)
    requested_by = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    terms_accepted_at = Column(DateTime(timezone=True), nullable=False)
    idempotency_key_hash = Column(String(64), nullable=False)
    request_hash = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="queued")
    attempts = Column(Integer, nullable=False, default=0)
    lease_token_hash = Column(String(64), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error_code = Column(String(50), nullable=True)
    certificate_fingerprint = Column(String(64), nullable=True)
    certificate_issued_at = Column(DateTime(timezone=True), nullable=True)
    certificate_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

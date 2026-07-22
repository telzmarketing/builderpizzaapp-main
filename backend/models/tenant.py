"""Core tenant model for the multi-company foundation."""
from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Index, String, text
from backend.database import Base


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'suspended', 'disabled')", name="ck_tenants_status"),
        Index("uq_tenants_slug_lower", text("lower(slug)"), unique=True),
        Index("uq_tenants_single_legacy", "is_legacy", unique=True, postgresql_where=text("is_legacy = true AND deleted_at IS NULL")),
    )

    id = Column(String, primary_key=True)
    slug = Column(String(100), nullable=False)
    name = Column(String(200), nullable=False)
    legal_name = Column(String(250), nullable=True)
    status = Column(String(20), nullable=False, default="active", index=True)
    timezone = Column(String(80), nullable=False, default="America/Sao_Paulo")
    locale = Column(String(20), nullable=False, default="pt-BR")
    is_legacy = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime(timezone=True), nullable=True)

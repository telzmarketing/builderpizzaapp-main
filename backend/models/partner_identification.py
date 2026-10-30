"""Tenant-scoped names and logos used to identify order origins."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, String

from backend.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PartnerIdentificationConfig(Base):
    __tablename__ = "partner_identification_configs"
    __table_args__ = (
        CheckConstraint(
            "partner_code IN ('own','partner_99','ifood','keeta')",
            name="ck_partner_identification_configs_partner_code",
        ),
        Index(
            "uq_partner_identification_configs_tenant_partner",
            "tenant_id", "partner_code", unique=True,
        ),
        Index("ix_partner_identification_configs_tenant", "tenant_id"),
    )

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    partner_code = Column(String(20), nullable=False)
    display_name = Column(String(120), nullable=False)
    logo_url = Column(String(500), nullable=True)
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

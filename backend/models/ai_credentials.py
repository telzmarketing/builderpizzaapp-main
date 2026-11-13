from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint

from backend.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class TenantAICredential(Base):
    """The single tenant-scoped AI credential shared by AI modules.

    Module behavior remains in each module's settings table. This table stores
    only the active provider credential, so Gestor, Atendimento and Print
    Pedido resolve the same secret instead of maintaining separate copies.
    """

    __tablename__ = "tenant_ai_credentials"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_tenant_ai_credentials_tenant"),
        Index("ix_tenant_ai_credentials_tenant", "tenant_id"),
    )

    id = Column(String(36), primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(20), nullable=False)
    api_key = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import relationship

from backend.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MarketplaceSettlement(Base):
    """Tenant-scoped expected/received settlement for an already delivered app order."""

    __tablename__ = "marketplace_settlements"
    __table_args__ = (
        CheckConstraint("provider IN ('partner_99','ifood','keeta')", name="ck_marketplace_settlements_provider"),
        CheckConstraint("status IN ('expected','partially_received','received','divergent','cancelled','quarantined')", name="ck_marketplace_settlements_status"),
        Index("uq_marketplace_settlements_tenant_provider_order", "tenant_id", "provider", "order_id", unique=True),
        Index("uq_marketplace_settlements_tenant_idempotency", "tenant_id", "idempotency_key", unique=True),
        Index("ix_marketplace_settlements_tenant_status", "tenant_id", "status"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    order_id = Column(String, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False)
    provider = Column(String(20), nullable=False)
    status = Column(String(24), nullable=False, default="expected", server_default="expected")
    gross_amount = Column(Numeric(20, 2), nullable=False, default=0)
    store_discount_amount = Column(Numeric(20, 2), nullable=False, default=0)
    marketplace_discount_amount = Column(Numeric(20, 2), nullable=False, default=0)
    delivery_fee = Column(Numeric(20, 2), nullable=False, default=0)
    service_fee = Column(Numeric(20, 2), nullable=False, default=0)
    commission_amount = Column(Numeric(20, 2), nullable=False, default=0)
    tax_amount = Column(Numeric(20, 2), nullable=False, default=0)
    expected_net_amount = Column(Numeric(20, 2), nullable=False, default=0)
    received_net_amount = Column(Numeric(20, 2), nullable=False, default=0)
    variance_amount = Column(Numeric(20, 2), nullable=False, default=0)
    external_settlement_reference = Column(String(180), nullable=True)
    expected_settlement_at = Column(DateTime(timezone=True), nullable=True)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    idempotency_key = Column(String(160), nullable=False)
    notes = Column(String(1000), nullable=True)
    created_by_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, server_default="now()")
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow, server_default="now()")

    order = relationship("Order")

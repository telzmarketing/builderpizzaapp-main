"""Tenant-scoped purchase requisitions and immutable transition history."""
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from backend.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class PurchaseRequisition(Base):
    __tablename__ = "purchase_requisitions"
    __table_args__ = (
        Index("uq_purchase_requisitions_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_purchase_requisitions_tenant_code", "tenant_id", "code", unique=True),
        Index("ix_purchase_requisitions_tenant_status", "tenant_id", "status"),
        Index("ix_purchase_requisitions_tenant_requester", "tenant_id", "requested_by_admin_id"),
        ForeignKeyConstraint(["requested_by_admin_id"], ["admin_users.id"], name="fk_purchase_requisitions_requester", ondelete="RESTRICT"),
        CheckConstraint("status IN ('draft','submitted','approved','sourcing','ordered','partially_fulfilled','fulfilled','rejected','cancelled')", name="ck_purchase_requisitions_status"),
        CheckConstraint("priority IN ('normal','urgent','emergency')", name="ck_purchase_requisitions_priority"),
        CheckConstraint("version > 0", name="ck_purchase_requisitions_version"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    code = Column(String(40), nullable=False)
    status = Column(String(30), nullable=False, default="draft", server_default="draft")
    priority = Column(String(20), nullable=False, default="normal", server_default="normal")
    requested_by_admin_id = Column(String, nullable=False)
    needed_by = Column(Date, nullable=True)
    reason = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    items = relationship("PurchaseRequisitionItem", cascade="all, delete-orphan", back_populates="requisition", order_by="PurchaseRequisitionItem.position")
    events = relationship("PurchaseRequisitionEvent", cascade="all, delete-orphan", back_populates="requisition", order_by="PurchaseRequisitionEvent.sequence")


class PurchaseRequisitionItem(Base):
    __tablename__ = "purchase_requisition_items"
    __table_args__ = (
        Index("uq_purchase_requisition_items_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_purchase_requisition_items_position", "tenant_id", "requisition_id", "position", unique=True),
        ForeignKeyConstraint(["tenant_id", "requisition_id"], ["purchase_requisitions.tenant_id", "purchase_requisitions.id"], name="fk_purchase_requisition_items_requisition", ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "item_id"], ["inventory_items.tenant_id", "inventory_items.id"], name="fk_purchase_requisition_items_item", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "unit_id"], ["inventory_units.tenant_id", "inventory_units.id"], name="fk_purchase_requisition_items_unit", ondelete="RESTRICT"),
        CheckConstraint("quantity > 0 AND CAST(quantity AS VARCHAR) <> 'NaN'", name="ck_purchase_requisition_items_quantity"),
        CheckConstraint("position >= 0", name="ck_purchase_requisition_items_position"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    requisition_id = Column(String(36), nullable=False)
    item_id = Column(String, nullable=False)
    unit_id = Column(String, nullable=False)
    quantity = Column(Numeric(20, 6), nullable=False)
    notes = Column(Text, nullable=True)
    position = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    requisition = relationship("PurchaseRequisition", back_populates="items")


class PurchaseRequisitionEvent(Base):
    __tablename__ = "purchase_requisition_events"
    __table_args__ = (
        Index("uq_purchase_requisition_events_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_purchase_requisition_events_sequence", "tenant_id", "requisition_id", "sequence", unique=True),
        ForeignKeyConstraint(["tenant_id", "requisition_id"], ["purchase_requisitions.tenant_id", "purchase_requisitions.id"], name="fk_purchase_requisition_events_requisition", ondelete="RESTRICT"),
        ForeignKeyConstraint(["actor_admin_id"], ["admin_users.id"], name="fk_purchase_requisition_events_actor", ondelete="SET NULL"),
        CheckConstraint("sequence > 0", name="ck_purchase_requisition_events_sequence"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    requisition_id = Column(String(36), nullable=False)
    sequence = Column(Integer, nullable=False)
    from_status = Column(String(30), nullable=True)
    to_status = Column(String(30), nullable=False)
    action = Column(String(40), nullable=False)
    actor_admin_id = Column(String, nullable=True)
    reason = Column(String(500), nullable=True)
    snapshot = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=dict, server_default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    requisition = relationship("PurchaseRequisition", back_populates="events")

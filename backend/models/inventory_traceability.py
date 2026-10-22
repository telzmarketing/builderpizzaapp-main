"""Tenant-owned lot opening and genealogy evidence."""
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, ForeignKeyConstraint, Index, Numeric, String, Text, CheckConstraint
from backend.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class InventoryLotOpening(Base):
    __tablename__ = "inventory_lot_openings"
    __table_args__ = (
        Index("uq_inventory_lot_openings_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_inventory_lot_openings_tenant_lot_key", "tenant_id", "lot_id", "idempotency_key", unique=True),
        Index("ix_inventory_lot_openings_tenant_lot", "tenant_id", "lot_id", "opened_at"),
        ForeignKeyConstraint(["tenant_id", "lot_id"], ["inventory_lots.tenant_id", "inventory_lots.id"], name="fk_inventory_lot_opening_lot", ondelete="RESTRICT"),
        CheckConstraint("length(trim(rule_code)) > 0", name="ck_inventory_lot_opening_rule"),
        CheckConstraint("resulting_expires_at IS NULL OR resulting_expires_at >= opened_at", name="ck_inventory_lot_opening_dates"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    lot_id = Column(String, nullable=False)
    opened_at = Column(DateTime(timezone=True), nullable=False)
    rule_code = Column(String(80), nullable=False)
    resulting_expires_at = Column(DateTime(timezone=True), nullable=True)
    idempotency_key = Column(String(200), nullable=False)
    actor_id = Column(String, ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

class InventoryLotGenealogy(Base):
    __tablename__ = "inventory_lot_genealogy"
    __table_args__ = (
        Index("uq_inventory_lot_genealogy_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_inventory_lot_genealogy_tenant_operation_source", "tenant_id", "operation_id", "source_lot_id", "target_lot_id", unique=True),
        Index("ix_inventory_lot_genealogy_source", "tenant_id", "source_lot_id", "created_at"),
        Index("ix_inventory_lot_genealogy_target", "tenant_id", "target_lot_id", "created_at"),
        ForeignKeyConstraint(["tenant_id", "source_lot_id"], ["inventory_lots.tenant_id", "inventory_lots.id"], name="fk_inventory_genealogy_source", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "target_lot_id"], ["inventory_lots.tenant_id", "inventory_lots.id"], name="fk_inventory_genealogy_target", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "operation_id"], ["inventory_operations.tenant_id", "inventory_operations.id"], name="fk_inventory_genealogy_operation", ondelete="RESTRICT"),
        CheckConstraint("source_lot_id <> target_lot_id", name="ck_inventory_genealogy_distinct_lots"),
        CheckConstraint("quantity > 0", name="ck_inventory_genealogy_quantity"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    source_lot_id = Column(String, nullable=False)
    target_lot_id = Column(String, nullable=False)
    operation_id = Column(String, nullable=False)
    quantity = Column(Numeric(20, 6), nullable=False)
    unit_id = Column(String, nullable=False)
    relation_type = Column(String(40), nullable=False, default="transformation", server_default="transformation")
    actor_id = Column(String, ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

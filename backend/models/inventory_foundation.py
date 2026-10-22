"""Tenant-owned stock foundation. Movements remain the physical balance authority."""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey,
    ForeignKeyConstraint, Index, Integer, JSON, Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB

from backend.database import Base


def utcnow():
    return datetime.now(timezone.utc)


OPERATION_KINDS = (
    "manual_in", "manual_out", "transfer", "loss", "adjustment_in", "adjustment_out",
    "order_sale", "order_sale_reversal", "order_sale_loss", "reservation", "reservation_release",
    "receipt", "preparation", "production_attempt", "compensation", "unit_definition", "packaging_definition",
    "lot_definition", "lot_state", "recipe_publication", "recipe_archive",
)


class InventoryOperation(Base):
    __tablename__ = "inventory_operations"
    __table_args__ = (
        Index("uq_inventory_operations_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_inventory_operation_business", "tenant_id", "kind", "business_key", unique=True),
        Index("uq_inventory_operation_request", "tenant_id", "idempotency_scope", "idempotency_key", unique=True),
        Index("ix_inventory_operations_tenant_created", "tenant_id", "created_at"),
        CheckConstraint("kind IN (" + ",".join(repr(value) for value in OPERATION_KINDS) + ")", name="ck_inventory_operation_kind"),
        CheckConstraint("status IN ('pending','committed')", name="ck_inventory_operation_status"),
        CheckConstraint("version > 0", name="ck_inventory_operation_version"),
        CheckConstraint("length(business_key) > 0 AND length(idempotency_key) > 0 AND length(idempotency_scope) > 0", name="ck_inventory_operation_identity"),
        CheckConstraint("length(request_hash) = 64", name="ck_inventory_operation_request_hash"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    kind = Column(String(40), nullable=False)
    business_key = Column(String(200), nullable=False)
    idempotency_scope = Column(String(200), nullable=False)
    idempotency_key = Column(String(200), nullable=False)
    request_hash = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="pending", server_default="pending")
    result_json = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    actor_id = Column(String, nullable=False)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    committed_at = Column(DateTime(timezone=True), nullable=True)


class InventoryItemPackaging(Base):
    __tablename__ = "inventory_item_packagings"
    __table_args__ = (
        Index("uq_inventory_packagings_tenant_id_id", "tenant_id", "id", unique=True),
        Index("ix_inventory_packagings_tenant_item", "tenant_id", "item_id", "supplier_id"),
        ForeignKeyConstraint(["tenant_id", "item_id"], ["inventory_items.tenant_id", "inventory_items.id"], name="fk_inventory_packaging_item", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "supplier_id"], ["inventory_suppliers.tenant_id", "inventory_suppliers.id"], name="fk_inventory_packaging_supplier", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "commercial_unit_id"], ["inventory_units.tenant_id", "inventory_units.id"], name="fk_inventory_packaging_commercial_unit", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "base_unit_id"], ["inventory_units.tenant_id", "inventory_units.id"], name="fk_inventory_packaging_base_unit", ondelete="RESTRICT"),
        CheckConstraint("(variable_weight AND factor IS NULL) OR (NOT variable_weight AND factor IS NOT NULL AND factor > 0)", name="ck_inventory_packaging_factor"),
        CheckConstraint("version > 0", name="ck_inventory_packaging_version"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    item_id = Column(String, nullable=False)
    supplier_id = Column(String, nullable=True)
    name = Column(String(180), nullable=False)
    commercial_unit_id = Column(String, nullable=False)
    base_unit_id = Column(String, nullable=False)
    factor = Column(Numeric(24, 12), nullable=True)
    variable_weight = Column(Boolean, nullable=False, default=False, server_default="false")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    actor_id = Column(String, ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class InventoryLot(Base):
    __tablename__ = "inventory_lots"
    __table_args__ = (
        Index("uq_inventory_lots_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_inventory_lots_tenant_id_item", "tenant_id", "id", "item_id", unique=True),
        Index("ix_inventory_lots_fefo", "tenant_id", "item_id", "status", "effective_expires_at", "received_at", "id"),
        ForeignKeyConstraint(["tenant_id", "item_id"], ["inventory_items.tenant_id", "inventory_items.id"], name="fk_inventory_lot_item", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "location_id"], ["inventory_locations.tenant_id", "inventory_locations.id"], name="fk_inventory_lot_location", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "supplier_id"], ["inventory_suppliers.tenant_id", "inventory_suppliers.id"], name="fk_inventory_lot_supplier", ondelete="RESTRICT"),
        CheckConstraint("status IN ('available','blocked','quarantine','consumed','discarded')", name="ck_inventory_lot_status"),
        CheckConstraint("version > 0 AND length(trim(lot_code)) > 0", name="ck_inventory_lot_identity"),
        CheckConstraint("manufactured_on IS NULL OR expires_on IS NULL OR manufactured_on <= expires_on", name="ck_inventory_lot_dates"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    item_id = Column(String, nullable=False)
    location_id = Column(String, nullable=False)
    supplier_id = Column(String, nullable=True)
    lot_code = Column(String(120), nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    manufactured_on = Column(Date, nullable=True)
    expires_on = Column(Date, nullable=True)
    effective_expires_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(20), nullable=False, default="available", server_default="available")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    notes = Column(Text, nullable=True)
    actor_id = Column(String, ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"
    __table_args__ = (
        Index("uq_inventory_reservations_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_inventory_reservation_business", "tenant_id", "business_key", unique=True),
        Index("ix_inventory_reservations_active", "tenant_id", "item_id", "status", "expires_at"),
        ForeignKeyConstraint(["tenant_id", "item_id"], ["inventory_items.tenant_id", "inventory_items.id"], name="fk_inventory_reservation_item", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "lot_id", "item_id"], ["inventory_lots.tenant_id", "inventory_lots.id", "inventory_lots.item_id"], name="fk_inventory_reservation_lot_item", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "operation_id"], ["inventory_operations.tenant_id", "inventory_operations.id"], name="fk_inventory_reservation_operation", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "location_id"], ["inventory_locations.tenant_id", "inventory_locations.id"], name="fk_inventory_reservation_location", ondelete="RESTRICT"),
        CheckConstraint("quantity > 0 AND version > 0", name="ck_inventory_reservation_quantity"),
        CheckConstraint("status IN ('active','consumed','released','expired')", name="ck_inventory_reservation_status"),
        CheckConstraint("length(business_key) > 0 AND length(source_type) > 0 AND length(source_id) > 0", name="ck_inventory_reservation_identity"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    business_key = Column(String(200), nullable=False)
    item_id = Column(String, nullable=False)
    location_id = Column(String, nullable=False)
    lot_id = Column(String, nullable=True)
    operation_id = Column(String, nullable=True)
    source_type = Column(String(40), nullable=False)
    source_id = Column(String(200), nullable=False)
    quantity = Column(Numeric(20, 6), nullable=False)
    status = Column(String(20), nullable=False, default="active", server_default="active")
    expires_at = Column(DateTime(timezone=True), nullable=True)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    actor_id = Column(String, ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


for _model, _columns in (
    (InventoryItemPackaging, ("factor",)),
    (InventoryReservation, ("quantity",)),
):
    for _column in _columns:
        _model.__table__.append_constraint(CheckConstraint(
            f"CAST({_column} AS VARCHAR) <> 'NaN'",
            name=f"ck_{_model.__tablename__}_{_column}_finite",
        ))

"""Tenant-scoped preparation planning and execution records."""
from datetime import datetime, timezone
from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship
from backend.database import Base

def utcnow(): return datetime.now(timezone.utc)

class InventoryOperationRecipe(Base):
    __tablename__ = "inventory_operation_recipes"
    __table_args__ = (
        Index("uq_inventory_operation_recipes_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_inventory_operation_recipes_tenant_name_version", "tenant_id", "name", "version_number", unique=True),
        ForeignKeyConstraint(["tenant_id", "output_item_id"], ["inventory_items.tenant_id", "inventory_items.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "output_unit_id"], ["inventory_units.tenant_id", "inventory_units.id"], ondelete="RESTRICT"),
        CheckConstraint("yield_quantity > 0", name="ck_operation_recipe_yield"),
        CheckConstraint("version_number > 0", name="ck_operation_recipe_version"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    name = Column(String(180), nullable=False)
    output_item_id = Column(String, nullable=False)
    output_unit_id = Column(String, nullable=False)
    yield_quantity = Column(Numeric(20, 6), nullable=False)
    version_number = Column(Integer, nullable=False, default=1, server_default="1")
    instructions = Column(Text)
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by = Column(String, ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    items = relationship("InventoryOperationRecipeItem", cascade="all, delete-orphan", back_populates="recipe", order_by="InventoryOperationRecipeItem.position")

class InventoryOperationRecipeItem(Base):
    __tablename__ = "inventory_operation_recipe_items"
    __table_args__ = (
        Index("uq_inventory_operation_recipe_items_tenant_id_id", "tenant_id", "id", unique=True),
        ForeignKeyConstraint(["tenant_id", "recipe_id"], ["inventory_operation_recipes.tenant_id", "inventory_operation_recipes.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["tenant_id", "item_id"], ["inventory_items.tenant_id", "inventory_items.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "unit_id"], ["inventory_units.tenant_id", "inventory_units.id"], ondelete="RESTRICT"),
        CheckConstraint("quantity > 0", name="ck_operation_recipe_item_quantity"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    recipe_id = Column(String, nullable=False)
    item_id = Column(String, nullable=False)
    unit_id = Column(String, nullable=False)
    quantity = Column(Numeric(20, 6), nullable=False)
    position = Column(Integer, nullable=False, default=0, server_default="0")
    recipe = relationship("InventoryOperationRecipe", back_populates="items")

class PreparationOrder(Base):
    __tablename__ = "preparation_orders"
    __table_args__ = (
        Index("uq_preparation_orders_tenant_id_id", "tenant_id", "id", unique=True),
        Index("ix_preparation_orders_queue", "tenant_id", "status", "scheduled_for"),
        ForeignKeyConstraint(["tenant_id", "recipe_id"], ["inventory_operation_recipes.tenant_id", "inventory_operation_recipes.id"], ondelete="RESTRICT"),
        CheckConstraint("target_quantity > 0", name="ck_preparation_order_target"),
        CheckConstraint("status IN ('draft','approved','scheduled','waiting','in_progress','paused','partially_completed','blocked','completed','cancelled')", name="ck_preparation_order_status"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    recipe_id = Column(String, nullable=False)
    target_quantity = Column(Numeric(20, 6), nullable=False)
    produced_quantity = Column(Numeric(20, 6), nullable=False, default=0, server_default="0")
    lost_quantity = Column(Numeric(20, 6), nullable=False, default=0, server_default="0")
    discarded_quantity = Column(Numeric(20, 6), nullable=False, default=0, server_default="0")
    status = Column(String(30), nullable=False, default="draft", server_default="draft")
    scheduled_for = Column(DateTime(timezone=True))
    version = Column(Integer, nullable=False, default=1, server_default="1")
    idempotency_key = Column(String(200), nullable=False)
    actor_id = Column(String, ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    recipe = relationship("InventoryOperationRecipe")
    executions = relationship("PreparationExecution", back_populates="order", cascade="all, delete-orphan")

class PreparationExecution(Base):
    __tablename__ = "preparation_executions"
    __table_args__ = (
        Index("uq_preparation_executions_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_preparation_executions_tenant_order_key", "tenant_id", "order_id", "idempotency_key", unique=True),
        ForeignKeyConstraint(["tenant_id", "order_id"], ["preparation_orders.tenant_id", "preparation_orders.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "operation_id"], ["inventory_operations.tenant_id", "inventory_operations.id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "output_lot_id"], ["inventory_lots.tenant_id", "inventory_lots.id"], ondelete="RESTRICT"),
        CheckConstraint("produced_quantity >= 0 AND lost_quantity >= 0 AND discarded_quantity >= 0 AND (produced_quantity + lost_quantity + discarded_quantity) > 0", name="ck_preparation_execution_quantities"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    order_id = Column(String, nullable=False)
    produced_quantity = Column(Numeric(20, 6), nullable=False, default=0)
    lost_quantity = Column(Numeric(20, 6), nullable=False, default=0)
    discarded_quantity = Column(Numeric(20, 6), nullable=False, default=0)
    operation_id = Column(String, nullable=True)
    output_lot_id = Column(String, nullable=True)
    output_lot_code = Column(String(120), nullable=True)
    expires_on = Column(Date, nullable=True)
    portion_grams = Column(Numeric(20, 6), nullable=True)
    prepared_at = Column(DateTime(timezone=True), nullable=True)
    idempotency_key = Column(String(200), nullable=False)
    actor_id = Column(String, ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    order = relationship("PreparationOrder", back_populates="executions")

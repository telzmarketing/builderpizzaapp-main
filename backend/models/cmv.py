from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from backend.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class OrderCmvSnapshot(Base):
    __tablename__ = "order_cmv_snapshots"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    order_id = Column(String, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    source = Column(String(40), nullable=False, default="order_created")
    status = Column(String(40), nullable=False, default="complete")
    sale_total = Column(Float, nullable=False, default=0.0)
    cost_total = Column(Float, nullable=False, default=0.0)
    cmv_percent = Column(Float, nullable=True)
    missing_recipe = Column(Boolean, nullable=False, default=False)
    missing_cost = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    order = relationship("Order")
    items = relationship("OrderItemCmvSnapshot", cascade="all, delete-orphan", back_populates="snapshot")


class OrderItemCmvSnapshot(Base):
    __tablename__ = "order_item_cmv_snapshots"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    snapshot_id = Column(String, ForeignKey("order_cmv_snapshots.id", ondelete="CASCADE"), nullable=False, index=True)
    order_item_id = Column(String, ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True)
    product_name = Column(String(220), nullable=False)
    quantity = Column(Float, nullable=False, default=1.0)
    sale_total = Column(Float, nullable=False, default=0.0)
    cost_total = Column(Float, nullable=False, default=0.0)
    cmv_percent = Column(Float, nullable=True)
    missing_recipe = Column(Boolean, nullable=False, default=False)
    missing_cost = Column(Boolean, nullable=False, default=False)
    recipe_version_ids = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    snapshot = relationship("OrderCmvSnapshot", back_populates="items")
    order_item = relationship("OrderItem")
    product = relationship("Product")
    ingredients = relationship("OrderItemCmvIngredientSnapshot", cascade="all, delete-orphan", back_populates="item_snapshot")


class OrderItemCmvIngredientSnapshot(Base):
    __tablename__ = "order_item_cmv_ingredient_snapshots"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    item_snapshot_id = Column(String, ForeignKey("order_item_cmv_snapshots.id", ondelete="CASCADE"), nullable=False, index=True)
    inventory_item_id = Column(String, ForeignKey("inventory_items.id", ondelete="SET NULL"), nullable=True, index=True)
    inventory_item_name = Column(String(180), nullable=False)
    unit_symbol = Column(String(20), nullable=True)
    quantity = Column(Float, nullable=False, default=0.0)
    unit_cost = Column(Float, nullable=False, default=0.0)
    total_cost = Column(Float, nullable=False, default=0.0)
    cost_source = Column(String(60), nullable=False, default="missing")
    missing_cost = Column(Boolean, nullable=False, default=False)

    item_snapshot = relationship("OrderItemCmvSnapshot", back_populates="ingredients")
    inventory_item = relationship("InventoryItem")

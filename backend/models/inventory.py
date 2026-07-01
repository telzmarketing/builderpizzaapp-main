from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class InventoryUnit(Base):
    __tablename__ = "inventory_units"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    name = Column(String(120), nullable=False)
    symbol = Column(String(20), nullable=False)
    unit_type = Column(String(30), nullable=False, default="unit")
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class InventoryCategory(Base):
    __tablename__ = "inventory_categories"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    name = Column(String(140), nullable=False)
    description = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class InventoryLocation(Base):
    __tablename__ = "inventory_locations"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    name = Column(String(140), nullable=False)
    description = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class InventorySupplier(Base):
    __tablename__ = "inventory_suppliers"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    name = Column(String(180), nullable=False)
    document = Column(String(60), nullable=True)
    phone = Column(String(60), nullable=True)
    email = Column(String(180), nullable=True)
    notes = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    name = Column(String(180), nullable=False)
    sku = Column(String(80), nullable=True, index=True)
    item_type = Column(String(40), nullable=False, default="ingredient")
    category_id = Column(String, ForeignKey("inventory_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    unit_id = Column(String, ForeignKey("inventory_units.id", ondelete="SET NULL"), nullable=True, index=True)
    default_location_id = Column(String, ForeignKey("inventory_locations.id", ondelete="SET NULL"), nullable=True, index=True)
    min_stock = Column(Float, nullable=False, default=0.0)
    notes = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    category = relationship("InventoryCategory")
    unit = relationship("InventoryUnit")
    default_location = relationship("InventoryLocation")


class InventoryPurchase(Base):
    __tablename__ = "inventory_purchases"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    supplier_id = Column(String, ForeignKey("inventory_suppliers.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="draft")
    invoice_number = Column(String(80), nullable=True)
    expected_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    total_amount = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    supplier = relationship("InventorySupplier")
    items = relationship("InventoryPurchaseItem", cascade="all, delete-orphan", back_populates="purchase")


class InventoryPurchaseItem(Base):
    __tablename__ = "inventory_purchase_items"

    id = Column(String, primary_key=True)
    purchase_id = Column(String, ForeignKey("inventory_purchases.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(String, ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity = Column(Float, nullable=False, default=0.0)
    unit_cost = Column(Float, nullable=False, default=0.0)
    total_cost = Column(Float, nullable=False, default=0.0)

    purchase = relationship("InventoryPurchase", back_populates="items")
    item = relationship("InventoryItem")


class InventoryManualEntry(Base):
    __tablename__ = "inventory_manual_entries"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    item_id = Column(String, ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    location_id = Column(String, ForeignKey("inventory_locations.id", ondelete="SET NULL"), nullable=True, index=True)
    movement_type = Column(String(20), nullable=False, default="in")
    quantity = Column(Float, nullable=False, default=0.0)
    unit_cost = Column(Float, nullable=False, default=0.0)
    reason = Column(String(120), nullable=False, default="initial_stock")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    item = relationship("InventoryItem")
    location = relationship("InventoryLocation")


class InventoryStockMovement(Base):
    __tablename__ = "inventory_stock_movements"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    item_id = Column(String, ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    location_id = Column(String, ForeignKey("inventory_locations.id", ondelete="SET NULL"), nullable=True, index=True)
    source_type = Column(String(40), nullable=False, default="manual_entry", index=True)
    source_id = Column(String, nullable=True, index=True)
    movement_type = Column(String(20), nullable=False, default="in", index=True)
    quantity_delta = Column(Float, nullable=False, default=0.0)
    unit_cost = Column(Float, nullable=False, default=0.0)
    reason = Column(String(120), nullable=False, default="manual")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    item = relationship("InventoryItem")
    location = relationship("InventoryLocation")


class InventoryRecipeVersion(Base):
    __tablename__ = "inventory_recipe_versions"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    product_size_id = Column(String, ForeignKey("product_sizes.id", ondelete="SET NULL"), nullable=True, index=True)
    product_crust_type_id = Column(String, ForeignKey("product_crust_types.id", ondelete="SET NULL"), nullable=True, index=True)
    product_drink_variant_id = Column(String, ForeignKey("product_drink_variants.id", ondelete="SET NULL"), nullable=True, index=True)
    complement_key = Column(String(120), nullable=True, index=True)
    complement_name = Column(String(180), nullable=True)
    version_number = Column(Integer, nullable=False, default=1)
    active = Column(Boolean, nullable=False, default=True, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    product = relationship("Product")
    product_size = relationship("ProductSize")
    product_crust_type = relationship("ProductCrustType")
    product_drink_variant = relationship("ProductDrinkVariant")
    items = relationship("InventoryRecipeItem", cascade="all, delete-orphan", back_populates="recipe")


class InventoryRecipeItem(Base):
    __tablename__ = "inventory_recipe_items"

    id = Column(String, primary_key=True)
    recipe_id = Column(String, ForeignKey("inventory_recipe_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    inventory_item_id = Column(String, ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity = Column(Float, nullable=False, default=0.0)
    waste_percent = Column(Float, nullable=False, default=0.0)
    notes = Column(Text, nullable=True)

    recipe = relationship("InventoryRecipeVersion", back_populates="items")
    inventory_item = relationship("InventoryItem")

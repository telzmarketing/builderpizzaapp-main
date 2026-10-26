from datetime import date, datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

from backend.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class InventoryUnit(Base):
    __tablename__ = "inventory_units"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_inventory_units_tenant"), nullable=True)
    __table_args__ = (
        Index("uq_inventory_units_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_inventory_units_tenant_code", "tenant_id", "code", unique=True),
        CheckConstraint("version > 0", name="ck_inventory_unit_version"),
        CheckConstraint("dimension IS NULL OR dimension IN ('mass','volume','count')", name="ck_inventory_unit_dimension"),
        CheckConstraint("conversion_factor IS NULL OR conversion_factor > 0", name="ck_inventory_unit_factor"),
        CheckConstraint("(dimension IS NULL AND conversion_factor IS NULL) OR (dimension IS NOT NULL AND conversion_factor IS NOT NULL)", name="ck_inventory_unit_classification"),
    )
    name = Column(String(120), nullable=False)
    symbol = Column(String(20), nullable=False)
    unit_type = Column(String(30), nullable=False, default="unit")
    # Null retains an explicitly unclassified legacy unit; never infer from symbol.
    code = Column(String(30), nullable=True)
    dimension = Column(String(10), nullable=True)
    conversion_factor = Column(Numeric(24, 12), nullable=True)
    version = Column(Integer, nullable=False, default=1, server_default="1")
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class InventoryCategory(Base):
    __tablename__ = "inventory_categories"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_inventory_categories_tenant"), nullable=True)
    __table_args__ = (Index("uq_inventory_categories_tenant_id_id", "tenant_id", "id", unique=True),)
    name = Column(String(140), nullable=False)
    description = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class InventoryLocation(Base):
    __tablename__ = "inventory_locations"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_inventory_locations_tenant"), nullable=True)
    __table_args__ = (Index("uq_inventory_locations_tenant_id_id", "tenant_id", "id", unique=True),)
    name = Column(String(140), nullable=False)
    description = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class InventorySupplier(Base):
    __tablename__ = "inventory_suppliers"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_inventory_suppliers_tenant"), nullable=True)
    __table_args__ = (Index("uq_inventory_suppliers_tenant_id_id", "tenant_id", "id", unique=True),)
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
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_inventory_items_tenant"), nullable=True)
    __table_args__ = (Index("uq_inventory_items_tenant_id_id", "tenant_id", "id", unique=True),)
    name = Column(String(180), nullable=False)
    sku = Column(String(80), nullable=True, index=True)
    item_type = Column(String(40), nullable=False, default="ingredient")
    portionable = Column(Boolean, nullable=False, default=False, server_default="false")
    category_id = Column(String, ForeignKey("inventory_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    unit_id = Column(String, ForeignKey("inventory_units.id", ondelete="SET NULL"), nullable=True, index=True)
    default_location_id = Column(String, ForeignKey("inventory_locations.id", ondelete="SET NULL"), nullable=True, index=True)
    min_stock = Column(Numeric(20, 6), nullable=False, default=0)
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
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_inventory_purchases_tenant"), nullable=True)
    __table_args__ = (Index("uq_inventory_purchases_tenant_id_id", "tenant_id", "id", unique=True),)
    supplier_id = Column(String, ForeignKey("inventory_suppliers.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="draft")
    invoice_number = Column(String(80), nullable=True)
    expected_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    total_amount = Column(Numeric(20, 8), nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    supplier = relationship("InventorySupplier")
    items = relationship("InventoryPurchaseItem", cascade="all, delete-orphan", back_populates="purchase")


class InventoryPurchaseItem(Base):
    __tablename__ = "inventory_purchase_items"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_inventory_purchase_items_tenant"), nullable=True)
    __table_args__ = (Index("uq_inventory_purchase_items_tenant_id_id", "tenant_id", "id", unique=True),)
    purchase_id = Column(String, ForeignKey("inventory_purchases.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(String, ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    quantity = Column(Numeric(20, 6), nullable=False, default=0)
    unit_cost = Column(Numeric(20, 8), nullable=False, default=0)
    total_cost = Column(Numeric(20, 8), nullable=False, default=0)

    purchase = relationship("InventoryPurchase", back_populates="items")
    item = relationship("InventoryItem")


class InventoryManualEntry(Base):
    __tablename__ = "inventory_manual_entries"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_inventory_manual_entries_tenant"), nullable=True)
    __table_args__ = (Index("uq_inventory_manual_entries_tenant_id_id", "tenant_id", "id", unique=True),)
    item_id = Column(String, ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    location_id = Column(String, ForeignKey("inventory_locations.id", ondelete="SET NULL"), nullable=True, index=True)
    movement_type = Column(String(20), nullable=False, default="in")
    quantity = Column(Numeric(20, 6), nullable=False, default=0)
    unit_cost = Column(Numeric(20, 8), nullable=False, default=0)
    reason = Column(String(120), nullable=False, default="initial_stock")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    item = relationship("InventoryItem")
    location = relationship("InventoryLocation")


class InventoryStockMovement(Base):
    __tablename__ = "inventory_stock_movements"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_inventory_stock_movements_tenant"), nullable=True)
    __table_args__ = (
        Index("uq_inventory_stock_movements_tenant_id_id", "tenant_id", "id", unique=True),
        Index("uq_inventory_movement_operation_sequence", "tenant_id", "operation_id", "operation_sequence", unique=True),
        ForeignKeyConstraint(["tenant_id", "operation_id"], ["inventory_operations.tenant_id", "inventory_operations.id"], name="fk_inventory_movement_operation", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "item_id"], ["inventory_items.tenant_id", "inventory_items.id"], name="fk_inventory_movement_tenant_item", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "location_id"], ["inventory_locations.tenant_id", "inventory_locations.id"], name="fk_inventory_movement_tenant_location", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "lot_id", "item_id"], ["inventory_lots.tenant_id", "inventory_lots.id", "inventory_lots.item_id"], name="fk_inventory_movement_lot_item", ondelete="RESTRICT"),
        CheckConstraint("(operation_id IS NULL AND operation_sequence IS NULL) OR (operation_id IS NOT NULL AND operation_sequence IS NOT NULL AND operation_sequence > 0 AND tenant_id IS NOT NULL)", name="ck_inventory_movement_operation"),
        CheckConstraint("lot_id IS NULL OR (tenant_id IS NOT NULL AND operation_id IS NOT NULL)", name="ck_inventory_movement_lot_operation"),
    )
    item_id = Column(String, ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    location_id = Column(String, ForeignKey("inventory_locations.id", ondelete="SET NULL"), nullable=True, index=True)
    operation_id = Column(String, nullable=True)
    operation_sequence = Column(Integer, nullable=True)
    logical_line_id = Column(String, nullable=True)
    lot_id = Column(String, nullable=True, index=True)
    source_type = Column(String(40), nullable=False, default="manual_entry", index=True)
    source_id = Column(String, nullable=True, index=True)
    movement_type = Column(String(20), nullable=False, default="in", index=True)
    quantity_delta = Column(Numeric(20, 6), nullable=False, default=0)
    unit_cost = Column(Numeric(20, 8), nullable=False, default=0)
    reason = Column(String(120), nullable=False, default="manual")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    item = relationship("InventoryItem", foreign_keys=[item_id])
    location = relationship("InventoryLocation", foreign_keys=[location_id])


class InventoryRecipeVersion(Base):
    __tablename__ = "inventory_recipe_versions"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_inventory_recipe_versions_tenant"), nullable=True)
    __table_args__ = (
        Index("uq_inventory_recipe_versions_tenant_id_id", "tenant_id", "id", unique=True),
        CheckConstraint("jsonb_typeof(preparation_steps) = 'array'", name="ck_inventory_recipe_steps_array").ddl_if(dialect="postgresql"),
        CheckConstraint("component_role IN ('flavor','base','crust','addon','packaging')", name="ck_inventory_recipe_role"),
        CheckConstraint("reference_fraction > 0 AND reference_fraction <= 1", name="ck_inventory_recipe_fraction"),
    )
    product_id = Column(String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    product_size_id = Column(String, ForeignKey("product_sizes.id", ondelete="SET NULL"), nullable=True, index=True)
    product_crust_type_id = Column(String, ForeignKey("product_crust_types.id", ondelete="SET NULL"), nullable=True, index=True)
    product_drink_variant_id = Column(String, ForeignKey("product_drink_variants.id", ondelete="SET NULL"), nullable=True, index=True)
    complement_key = Column(String(120), nullable=True, index=True)
    complement_name = Column(String(180), nullable=True)
    version_number = Column(Integer, nullable=False, default=1)
    component_role = Column(String(20), nullable=False, default="flavor", server_default="flavor")
    reference_fraction = Column(Numeric(20, 12), nullable=False, default=1.0, server_default="1")
    instructions = Column(Text, nullable=True)
    preparation_steps = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list, server_default="[]")
    reference_image_url = Column(String(700), nullable=True)
    active = Column(Boolean, nullable=False, default=True, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    product = relationship("Product")
    product_size = relationship("ProductSize")
    product_crust_type = relationship("ProductCrustType")
    product_drink_variant = relationship("ProductDrinkVariant")
    items = relationship("InventoryRecipeItem", cascade="all, delete-orphan", back_populates="recipe", order_by="(InventoryRecipeItem.position, InventoryRecipeItem.id)")


class InventoryRecipeItem(Base):
    __tablename__ = "inventory_recipe_items"

    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", name="fk_inventory_recipe_items_tenant"), nullable=True)
    __table_args__ = (
        Index("uq_inventory_recipe_items_tenant_id_id", "tenant_id", "id", unique=True),
        ForeignKeyConstraint(["tenant_id", "unit_id"], ["inventory_units.tenant_id", "inventory_units.id"], name="fk_inventory_recipe_item_unit", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "entered_unit_id"], ["inventory_units.tenant_id", "inventory_units.id"], name="fk_inventory_recipe_item_entered_unit", ondelete="RESTRICT"),
        CheckConstraint("position >= 0", name="ck_inventory_recipe_item_position"),
        CheckConstraint("unit_id IS NULL OR tenant_id IS NOT NULL", name="ck_inventory_recipe_item_unit_owner"),
        CheckConstraint("NOT show_public OR (public_name IS NOT NULL AND length(trim(public_name)) > 0)", name="ck_inventory_recipe_item_public_name"),
        CheckConstraint("(entered_unit_id IS NULL AND entered_quantity IS NULL AND conversion_factor_snapshot IS NULL) OR (tenant_id IS NOT NULL AND unit_id IS NOT NULL AND entered_unit_id IS NOT NULL AND entered_quantity IS NOT NULL AND conversion_factor_snapshot IS NOT NULL AND entered_quantity > 0 AND conversion_factor_snapshot > 0 AND quantity > 0 AND quantity = round(entered_quantity * conversion_factor_snapshot, 6))", name="ck_inventory_recipe_item_conversion"),
    )
    recipe_id = Column(String, ForeignKey("inventory_recipe_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    inventory_item_id = Column(String, ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    # quantity is always the normalized base-unit amount for legacy consumers.
    unit_id = Column(String, nullable=True)
    entered_unit_id = Column(String, nullable=True)
    entered_quantity = Column(Numeric(20, 6), nullable=True)
    conversion_factor_snapshot = Column(Numeric(24, 12), nullable=True)
    position = Column(Integer, nullable=False, default=0, server_default="0")
    public_name = Column(String(180), nullable=True)
    show_public = Column(Boolean, nullable=False, default=False, server_default="false")
    allow_removal = Column(Boolean, nullable=False, default=False, server_default="false")
    quantity = Column(Numeric(20, 6), nullable=False, default=0)
    waste_percent = Column(Numeric(20, 12), nullable=False, default=0)
    notes = Column(Text, nullable=True)

    recipe = relationship("InventoryRecipeVersion", back_populates="items")
    inventory_item = relationship("InventoryItem")
    unit = relationship("InventoryUnit", foreign_keys=[tenant_id, unit_id], viewonly=True)
    entered_unit = relationship("InventoryUnit", foreign_keys=[tenant_id, entered_unit_id], viewonly=True)


# NUMERIC accepts PostgreSQL NaN; explicitly reject it for physical quantities.
for _model, _columns in (
    (InventoryItem, ("min_stock",)),
    (InventoryPurchase, ("total_amount",)),
    (InventoryPurchaseItem, ("quantity", "unit_cost", "total_cost")),
    (InventoryManualEntry, ("quantity", "unit_cost")),
    (InventoryStockMovement, ("quantity_delta", "unit_cost")),
    (InventoryRecipeVersion, ("reference_fraction",)),
    (InventoryRecipeItem, ("quantity", "waste_percent", "entered_quantity", "conversion_factor_snapshot")),
    (InventoryUnit, ("conversion_factor",)),
):
    for _column in _columns:
        _model.__table__.append_constraint(CheckConstraint(
            f"CAST({_column} AS VARCHAR) <> 'NaN'",
            name=f"ck_{_model.__tablename__}_{_column}_finite",
        ))


# Inventory is imported by main and Alembic; register foundation metadata there too.
from backend.models import inventory_foundation as _inventory_foundation  # noqa: E402,F401
from backend.models import inventory_receipts as _inventory_receipts  # noqa: E402,F401
from backend.models import preparation as _preparation  # noqa: E402,F401

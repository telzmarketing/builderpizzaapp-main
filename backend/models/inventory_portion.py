"""Tenant-scoped configuration for transforming a stock item into a portion."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, Numeric, String, Text, and_, text
from sqlalchemy.orm import foreign, relationship

from backend.database import Base
from backend.models.inventory import InventoryItem, InventoryUnit


def utcnow():
    return datetime.now(timezone.utc)


class InventoryPortionConfig(Base):
    __tablename__ = "inventory_portion_configs"
    __table_args__ = (
        Index("uq_inventory_portion_configs_tenant_id_id", "tenant_id", "id", unique=True),
        Index(
            "uq_inventory_portion_configs_equivalent",
            "tenant_id", "source_item_id", "usage", "portion_weight", "unit_id", "reference_fraction",
            text("coalesce(size, '')"),
            unique=True,
        ),
        ForeignKeyConstraint(
            ["tenant_id", "source_item_id"],
            ["inventory_items.tenant_id", "inventory_items.id"],
            name="fk_inventory_portion_config_source_item",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "output_item_id"],
            ["inventory_items.tenant_id", "inventory_items.id"],
            name="fk_inventory_portion_config_output_item",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "unit_id"],
            ["inventory_units.tenant_id", "inventory_units.id"],
            name="fk_inventory_portion_config_unit",
            ondelete="RESTRICT",
        ),
        CheckConstraint("usage IN ('mandatory', 'optional', 'direct')", name="ck_inventory_portion_config_usage"),
        CheckConstraint("portion_weight > 0", name="ck_inventory_portion_config_weight"),
        CheckConstraint("reference_fraction > 0 AND reference_fraction <= 1", name="ck_inventory_portion_config_reference"),
        CheckConstraint("min_stock >= 0 AND target_stock >= 0 AND target_stock >= min_stock", name="ck_inventory_portion_config_stock_levels"),
        CheckConstraint("shelf_life_days IS NULL OR shelf_life_days >= 0", name="ck_inventory_portion_config_shelf_life"),
        CheckConstraint("yield_percent > 0 AND yield_percent <= 100", name="ck_inventory_portion_config_yield"),
        CheckConstraint("loss_percent >= 0 AND loss_percent < 100", name="ck_inventory_portion_config_loss"),
        CheckConstraint("version > 0", name="ck_inventory_portion_config_version"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    source_item_id = Column(String, nullable=False)
    output_item_id = Column(String, nullable=False)
    usage = Column(String(12), nullable=False, default="mandatory", server_default="mandatory")
    portion_weight = Column(Numeric(20, 6), nullable=False)
    unit_id = Column(String, nullable=False)
    reference_fraction = Column(Numeric(20, 12), nullable=False, default=1, server_default="1")
    size = Column(String(80), nullable=True)
    min_stock = Column(Numeric(20, 6), nullable=False, default=0, server_default="0")
    target_stock = Column(Numeric(20, 6), nullable=False, default=0, server_default="0")
    shelf_life_days = Column(Integer, nullable=True)
    yield_percent = Column(Numeric(8, 4), nullable=False, default=100, server_default="100")
    loss_percent = Column(Numeric(8, 4), nullable=False, default=0, server_default="0")
    technical_instructions = Column(Text, nullable=True)
    handling_instructions = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True, server_default="true")
    version = Column(Integer, nullable=False, default=1, server_default="1")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    source_item = relationship(
        "InventoryItem",
        primaryjoin=lambda: and_(foreign(InventoryPortionConfig.tenant_id) == InventoryItem.tenant_id, foreign(InventoryPortionConfig.source_item_id) == InventoryItem.id),
        foreign_keys=lambda: [InventoryPortionConfig.tenant_id, InventoryPortionConfig.source_item_id],
        viewonly=True,
    )
    output_item = relationship(
        "InventoryItem",
        primaryjoin=lambda: and_(foreign(InventoryPortionConfig.tenant_id) == InventoryItem.tenant_id, foreign(InventoryPortionConfig.output_item_id) == InventoryItem.id),
        foreign_keys=lambda: [InventoryPortionConfig.tenant_id, InventoryPortionConfig.output_item_id],
        viewonly=True,
    )
    unit = relationship(
        "InventoryUnit",
        primaryjoin=lambda: and_(foreign(InventoryPortionConfig.tenant_id) == InventoryUnit.tenant_id, foreign(InventoryPortionConfig.unit_id) == InventoryUnit.id),
        foreign_keys=lambda: [InventoryPortionConfig.tenant_id, InventoryPortionConfig.unit_id],
        viewonly=True,
    )

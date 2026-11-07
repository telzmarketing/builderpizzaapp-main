"""Add tenant-scoped portion configuration and generated output item."""
from alembic import op
import sqlalchemy as sa


revision = "20261107_inventory_portion_configs"
down_revision = "20261106_inventory_item_skus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_portion_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("source_item_id", sa.String, nullable=False),
        sa.Column("output_item_id", sa.String, nullable=False),
        sa.Column("usage", sa.String(12), nullable=False, server_default="mandatory"),
        sa.Column("portion_weight", sa.Numeric(20, 6), nullable=False),
        sa.Column("unit_id", sa.String, nullable=False),
        sa.Column("reference_fraction", sa.Numeric(20, 12), nullable=False, server_default="1"),
        sa.Column("size", sa.String(80), nullable=True),
        sa.Column("min_stock", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("target_stock", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("shelf_life_days", sa.Integer, nullable=True),
        sa.Column("yield_percent", sa.Numeric(8, 4), nullable=False, server_default="100"),
        sa.Column("loss_percent", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["tenant_id", "source_item_id"], ["inventory_items.tenant_id", "inventory_items.id"], name="fk_inventory_portion_config_source_item", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "output_item_id"], ["inventory_items.tenant_id", "inventory_items.id"], name="fk_inventory_portion_config_output_item", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "unit_id"], ["inventory_units.tenant_id", "inventory_units.id"], name="fk_inventory_portion_config_unit", ondelete="RESTRICT"),
        sa.CheckConstraint("usage IN ('mandatory', 'optional', 'direct')", name="ck_inventory_portion_config_usage"),
        sa.CheckConstraint("portion_weight > 0", name="ck_inventory_portion_config_weight"),
        sa.CheckConstraint("reference_fraction > 0 AND reference_fraction <= 1", name="ck_inventory_portion_config_reference"),
        sa.CheckConstraint("min_stock >= 0 AND target_stock >= min_stock", name="ck_inventory_portion_config_stock_levels"),
        sa.CheckConstraint("shelf_life_days IS NULL OR shelf_life_days >= 0", name="ck_inventory_portion_config_shelf_life"),
        sa.CheckConstraint("yield_percent > 0 AND yield_percent <= 100", name="ck_inventory_portion_config_yield"),
        sa.CheckConstraint("loss_percent >= 0 AND loss_percent < 100", name="ck_inventory_portion_config_loss"),
        sa.CheckConstraint("version > 0", name="ck_inventory_portion_config_version"),
    )
    op.create_index("uq_inventory_portion_configs_tenant_id_id", "inventory_portion_configs", ["tenant_id", "id"], unique=True)
    op.create_index(
        "uq_inventory_portion_configs_equivalent", "inventory_portion_configs",
        ["tenant_id", "source_item_id", "usage", "portion_weight", "unit_id", "reference_fraction", sa.text("coalesce(size, '')")], unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_inventory_portion_configs_equivalent", table_name="inventory_portion_configs")
    op.drop_index("uq_inventory_portion_configs_tenant_id_id", table_name="inventory_portion_configs")
    op.drop_table("inventory_portion_configs")

"""Add explicit weight metadata to inventory units and items."""
from alembic import op
import sqlalchemy as sa

revision = "20261109_inventory_unit_item_weights"
down_revision = "20261108_inventory_recipe_supply_modes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inventory_units", sa.Column("has_weight", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("inventory_items", sa.Column("weight_quantity", sa.Numeric(20, 6), nullable=True))
    op.add_column("inventory_items", sa.Column("weight_unit_id", sa.String(), nullable=True))
    op.create_index("ix_inventory_items_weight_unit_id", "inventory_items", ["weight_unit_id"])
    op.create_foreign_key("fk_inventory_items_weight_unit", "inventory_items", "inventory_units", ["weight_unit_id"], ["id"], ondelete="SET NULL")
    op.create_check_constraint("ck_inventory_items_weight_quantity_positive", "inventory_items", "weight_quantity IS NULL OR weight_quantity > 0")
    op.create_check_constraint("ck_inventory_items_weight_pair", "inventory_items", "(weight_quantity IS NULL AND weight_unit_id IS NULL) OR (weight_quantity IS NOT NULL AND weight_unit_id IS NOT NULL)")


def downgrade() -> None:
    op.drop_constraint("ck_inventory_items_weight_pair", "inventory_items", type_="check")
    op.drop_constraint("ck_inventory_items_weight_quantity_positive", "inventory_items", type_="check")
    op.drop_constraint("fk_inventory_items_weight_unit", "inventory_items", type_="foreignkey")
    op.drop_index("ix_inventory_items_weight_unit_id", table_name="inventory_items")
    op.drop_column("inventory_items", "weight_unit_id")
    op.drop_column("inventory_items", "weight_quantity")
    op.drop_column("inventory_units", "has_weight")

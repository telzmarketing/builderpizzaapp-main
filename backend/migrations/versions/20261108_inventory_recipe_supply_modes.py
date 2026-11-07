"""Add immutable supply-source metadata to technical recipe lines."""

from alembic import op
import sqlalchemy as sa


revision = "20261108_inventory_recipe_supply_modes"
down_revision = "20261107_inventory_portion_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing recipe lines remain direct inventory consumption. The nullable
    # portion fields allow old rows to stay untouched while new publication
    # records an immutable configuration/version snapshot.
    op.add_column(
        "inventory_recipe_items",
        sa.Column("supply_mode", sa.String(12), nullable=False, server_default="direct"),
    )
    op.add_column("inventory_recipe_items", sa.Column("portion_config_id", sa.String, nullable=True))
    op.add_column("inventory_recipe_items", sa.Column("portion_config_version", sa.Integer, nullable=True))
    op.create_index(
        "ix_inventory_recipe_items_portion_config",
        "inventory_recipe_items",
        ["tenant_id", "portion_config_id"],
    )
    op.create_foreign_key(
        "fk_inventory_recipe_item_portion_config",
        "inventory_recipe_items",
        "inventory_portion_configs",
        ["tenant_id", "portion_config_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_inventory_recipe_item_supply_mode",
        "inventory_recipe_items",
        "supply_mode IN ('direct', 'portion')",
    )
    op.create_check_constraint(
        "ck_inventory_recipe_item_supply_source",
        "inventory_recipe_items",
        "(supply_mode = 'direct' AND portion_config_id IS NULL AND portion_config_version IS NULL) OR "
        "(supply_mode = 'portion' AND portion_config_id IS NOT NULL AND portion_config_version IS NOT NULL AND portion_config_version > 0)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_inventory_recipe_item_supply_source", "inventory_recipe_items", type_="check")
    op.drop_constraint("ck_inventory_recipe_item_supply_mode", "inventory_recipe_items", type_="check")
    op.drop_constraint("fk_inventory_recipe_item_portion_config", "inventory_recipe_items", type_="foreignkey")
    op.drop_index("ix_inventory_recipe_items_portion_config", table_name="inventory_recipe_items")
    op.drop_column("inventory_recipe_items", "portion_config_version")
    op.drop_column("inventory_recipe_items", "portion_config_id")
    op.drop_column("inventory_recipe_items", "supply_mode")

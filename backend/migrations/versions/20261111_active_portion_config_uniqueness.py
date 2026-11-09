"""Allow explicit replacement of inactive legacy portion configurations.

Existing rows, recipes, output items and movements are left untouched.
"""
from alembic import op
import sqlalchemy as sa


revision = "20261111_active_portion_config_uniqueness"
down_revision = "20261110_portioning_technical_sheet"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("uq_inventory_portion_configs_equivalent", table_name="inventory_portion_configs")
    op.create_index(
        "uq_inventory_portion_configs_equivalent",
        "inventory_portion_configs",
        ["tenant_id", "source_item_id", "usage", "portion_weight", "unit_id", "reference_fraction", sa.text("coalesce(size, '')")],
        unique=True,
        postgresql_where=sa.text("active = true"),
    )


def downgrade() -> None:
    raise RuntimeError("Forward-only: inactive historical configurations may have active replacements.")

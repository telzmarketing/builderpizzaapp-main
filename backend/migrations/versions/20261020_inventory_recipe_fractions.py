"""Explicit recipe portions and component roles, preserving legacy quantities."""
from alembic import op

revision = "20261020_inventory_recipe_fractions"
down_revision = "20261020_product_order_options"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE inventory_recipe_versions ADD COLUMN component_role VARCHAR(20) NOT NULL DEFAULT 'flavor'")
    op.execute("ALTER TABLE inventory_recipe_versions ADD COLUMN reference_fraction DOUBLE PRECISION NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE inventory_recipe_versions ADD CONSTRAINT ck_inventory_recipe_role CHECK (component_role IN ('flavor','base','crust','addon','packaging'))")
    op.execute("ALTER TABLE inventory_recipe_versions ADD CONSTRAINT ck_inventory_recipe_fraction CHECK (reference_fraction > 0 AND reference_fraction <= 1)")
    op.execute("CREATE UNIQUE INDEX uq_inventory_order_sale_loss ON inventory_stock_movements(tenant_id, source_type, source_id, item_id) WHERE source_type = 'order_sale_loss' AND source_id IS NOT NULL")


def downgrade():
    raise RuntimeError("Forward-only: preserve recipe references and production loss audit.")

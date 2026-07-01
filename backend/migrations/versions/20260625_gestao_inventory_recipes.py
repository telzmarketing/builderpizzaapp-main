"""gestao inventory recipes

Revision ID: 20260625_gestao_inventory_recipes
Revises: 20260625_gestao_inventory_base
"""
from __future__ import annotations

from alembic import op

revision = "20260625_gestao_inventory_recipes"
down_revision = "20260625_gestao_inventory_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory_recipe_versions (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            product_id VARCHAR NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            product_size_id VARCHAR REFERENCES product_sizes(id) ON DELETE SET NULL,
            product_crust_type_id VARCHAR REFERENCES product_crust_types(id) ON DELETE SET NULL,
            product_drink_variant_id VARCHAR REFERENCES product_drink_variants(id) ON DELETE SET NULL,
            complement_key VARCHAR(120),
            complement_name VARCHAR(180),
            version_number INTEGER NOT NULL DEFAULT 1,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_recipe_versions_tenant_id ON inventory_recipe_versions(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_recipe_versions_product_id ON inventory_recipe_versions(product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_recipe_versions_product_size_id ON inventory_recipe_versions(product_size_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_recipe_versions_product_crust_type_id ON inventory_recipe_versions(product_crust_type_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_recipe_versions_product_drink_variant_id ON inventory_recipe_versions(product_drink_variant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_recipe_versions_complement_key ON inventory_recipe_versions(complement_key)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_recipe_versions_active ON inventory_recipe_versions(active)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_recipe_versions_scope_active
        ON inventory_recipe_versions (
            tenant_id,
            product_id,
            COALESCE(product_size_id, ''),
            COALESCE(product_crust_type_id, ''),
            COALESCE(product_drink_variant_id, ''),
            COALESCE(complement_key, '')
        )
        WHERE active = TRUE
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory_recipe_items (
            id VARCHAR PRIMARY KEY,
            recipe_id VARCHAR NOT NULL REFERENCES inventory_recipe_versions(id) ON DELETE CASCADE,
            inventory_item_id VARCHAR NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
            quantity FLOAT NOT NULL DEFAULT 0,
            waste_percent FLOAT NOT NULL DEFAULT 0,
            notes TEXT
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_recipe_items_recipe_id ON inventory_recipe_items(recipe_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_recipe_items_inventory_item_id ON inventory_recipe_items(inventory_item_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS inventory_recipe_items")
    op.execute("DROP TABLE IF EXISTS inventory_recipe_versions")

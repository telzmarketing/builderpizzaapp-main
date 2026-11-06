"""Generate and enforce tenant-scoped SKUs for inventory items."""

from alembic import op


revision = "20261106_inventory_item_skus"
down_revision = "20261106_product_global_catalog_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Keep existing explicit values, deterministically fill legacy gaps, and
    # disambiguate old duplicates before adding the database invariant.
    op.execute(
        """
        UPDATE inventory_items
        SET sku = 'INS-' || upper(substr(md5(coalesce(tenant_id, '') || ':' || id), 1, 10))
        WHERE sku IS NULL OR trim(sku) = ''
        """
    )
    op.execute(
        """
        WITH duplicates AS (
            SELECT tenant_id, sku, id,
                   row_number() OVER (PARTITION BY tenant_id, sku ORDER BY id) AS position
            FROM inventory_items
            WHERE sku IS NOT NULL AND trim(sku) <> ''
        )
        UPDATE inventory_items item
        SET sku = left(item.sku, 72) || '-' || upper(substr(md5(coalesce(item.tenant_id, '') || ':' || item.id), 1, 7))
        FROM duplicates duplicate
        WHERE item.id = duplicate.id
          AND duplicate.position > 1
        """
    )
    op.create_index("uq_inventory_items_tenant_sku", "inventory_items", ["tenant_id", "sku"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_inventory_items_tenant_sku", table_name="inventory_items")

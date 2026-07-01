"""gestao cmv operational snapshots

Revision ID: 20260625_gestao_cmv_snapshots
Revises: 20260625_gestao_inventory_stock_ops
"""
from __future__ import annotations

from alembic import op

revision = "20260625_gestao_cmv_snapshots"
down_revision = "20260625_gestao_inventory_stock_ops"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS order_cmv_snapshots (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            order_id VARCHAR NOT NULL UNIQUE REFERENCES orders(id) ON DELETE CASCADE,
            source VARCHAR(40) NOT NULL DEFAULT 'order_created',
            status VARCHAR(40) NOT NULL DEFAULT 'complete',
            sale_total FLOAT NOT NULL DEFAULT 0,
            cost_total FLOAT NOT NULL DEFAULT 0,
            cmv_percent FLOAT,
            missing_recipe BOOLEAN NOT NULL DEFAULT FALSE,
            missing_cost BOOLEAN NOT NULL DEFAULT FALSE,
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_cmv_snapshots_tenant_id ON order_cmv_snapshots(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_cmv_snapshots_order_id ON order_cmv_snapshots(order_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS order_item_cmv_snapshots (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            snapshot_id VARCHAR NOT NULL REFERENCES order_cmv_snapshots(id) ON DELETE CASCADE,
            order_item_id VARCHAR NOT NULL REFERENCES order_items(id) ON DELETE CASCADE,
            product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL,
            product_name VARCHAR(220) NOT NULL,
            quantity FLOAT NOT NULL DEFAULT 1,
            sale_total FLOAT NOT NULL DEFAULT 0,
            cost_total FLOAT NOT NULL DEFAULT 0,
            cmv_percent FLOAT,
            missing_recipe BOOLEAN NOT NULL DEFAULT FALSE,
            missing_cost BOOLEAN NOT NULL DEFAULT FALSE,
            recipe_version_ids TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_item_cmv_snapshots_tenant_id ON order_item_cmv_snapshots(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_item_cmv_snapshots_snapshot_id ON order_item_cmv_snapshots(snapshot_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_item_cmv_snapshots_order_item_id ON order_item_cmv_snapshots(order_item_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_item_cmv_snapshots_product_id ON order_item_cmv_snapshots(product_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS order_item_cmv_ingredient_snapshots (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            item_snapshot_id VARCHAR NOT NULL REFERENCES order_item_cmv_snapshots(id) ON DELETE CASCADE,
            inventory_item_id VARCHAR REFERENCES inventory_items(id) ON DELETE SET NULL,
            inventory_item_name VARCHAR(180) NOT NULL,
            unit_symbol VARCHAR(20),
            quantity FLOAT NOT NULL DEFAULT 0,
            unit_cost FLOAT NOT NULL DEFAULT 0,
            total_cost FLOAT NOT NULL DEFAULT 0,
            cost_source VARCHAR(60) NOT NULL DEFAULT 'missing',
            missing_cost BOOLEAN NOT NULL DEFAULT FALSE
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_item_cmv_ingredient_snapshots_tenant_id ON order_item_cmv_ingredient_snapshots(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_item_cmv_ingredient_snapshots_item_snapshot_id ON order_item_cmv_ingredient_snapshots(item_snapshot_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_order_item_cmv_ingredient_snapshots_inventory_item_id ON order_item_cmv_ingredient_snapshots(inventory_item_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS order_item_cmv_ingredient_snapshots")
    op.execute("DROP TABLE IF EXISTS order_item_cmv_snapshots")
    op.execute("DROP TABLE IF EXISTS order_cmv_snapshots")

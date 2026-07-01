"""gestao inventory stock operations

Revision ID: 20260625_gestao_inventory_stock_ops
Revises: 20260625_gestao_inventory_recipes
"""
from __future__ import annotations

from alembic import op

revision = "20260625_gestao_inventory_stock_ops"
down_revision = "20260625_gestao_inventory_recipes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE inventory_manual_entries
        ADD COLUMN IF NOT EXISTS movement_type VARCHAR(20) NOT NULL DEFAULT 'in'
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inventory_stock_movements (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            item_id VARCHAR NOT NULL REFERENCES inventory_items(id) ON DELETE RESTRICT,
            location_id VARCHAR REFERENCES inventory_locations(id) ON DELETE SET NULL,
            source_type VARCHAR(40) NOT NULL DEFAULT 'manual_entry',
            source_id VARCHAR,
            movement_type VARCHAR(20) NOT NULL DEFAULT 'in',
            quantity_delta FLOAT NOT NULL DEFAULT 0,
            unit_cost FLOAT NOT NULL DEFAULT 0,
            reason VARCHAR(120) NOT NULL DEFAULT 'manual',
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_stock_movements_tenant_id ON inventory_stock_movements(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_stock_movements_item_id ON inventory_stock_movements(item_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_stock_movements_location_id ON inventory_stock_movements(location_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_stock_movements_source_type ON inventory_stock_movements(source_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_stock_movements_source_id ON inventory_stock_movements(source_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_inventory_stock_movements_movement_type ON inventory_stock_movements(movement_type)")
    op.execute(
        """
        INSERT INTO inventory_stock_movements (
            id,
            tenant_id,
            item_id,
            location_id,
            source_type,
            source_id,
            movement_type,
            quantity_delta,
            unit_cost,
            reason,
            notes,
            created_at
        )
        SELECT
            'inv-mov-backfill-' || id,
            tenant_id,
            item_id,
            location_id,
            'manual_entry',
            id,
            COALESCE(movement_type, 'in'),
            CASE WHEN COALESCE(movement_type, 'in') = 'out' THEN -ABS(quantity) ELSE ABS(quantity) END,
            unit_cost,
            reason,
            notes,
            created_at
        FROM inventory_manual_entries
        WHERE NOT EXISTS (
            SELECT 1
            FROM inventory_stock_movements
            WHERE inventory_stock_movements.source_type = 'manual_entry'
              AND inventory_stock_movements.source_id = inventory_manual_entries.id
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS inventory_stock_movements")
    op.execute("ALTER TABLE inventory_manual_entries DROP COLUMN IF EXISTS movement_type")

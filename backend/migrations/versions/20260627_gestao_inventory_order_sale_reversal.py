"""gestao inventory order sale reversal

Revision ID: 20260627_gestao_inventory_order_sale_reversal
Revises: 20260627_gestao_inventory_order_sale_deduction
"""
from __future__ import annotations

from alembic import op

revision = "20260627_gestao_inventory_order_sale_reversal"
down_revision = "20260627_gestao_inventory_order_sale_deduction"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_inventory_order_sale_reversal_movement
        ON inventory_stock_movements(tenant_id, source_type, source_id, item_id)
        WHERE source_type = 'order_sale_reversal' AND source_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_inventory_stock_movements_order_sale_reversal_lookup
        ON inventory_stock_movements(tenant_id, source_type, source_id)
        WHERE source_type = 'order_sale_reversal'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_inventory_stock_movements_order_sale_reversal_lookup")
    op.execute("DROP INDEX IF EXISTS uq_inventory_order_sale_reversal_movement")

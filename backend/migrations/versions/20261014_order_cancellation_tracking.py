"""Bring legacy order cancellation history into the Alembic upgrade path.

The standalone 0001_order_cancellation_tracking.sql was never part of the
revision graph. Existing databases may already contain its columns and data.
"""
from __future__ import annotations

from alembic import op


revision = "20261014_order_cancellation_tracking"
down_revision = "20261004_tenant_upload_ownership_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE orders "
        "ADD COLUMN IF NOT EXISTS cancelled_by VARCHAR(50), "
        "ADD COLUMN IF NOT EXISTS cancellation_reason TEXT, "
        "ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_orders_cancelled_by "
        "ON orders (cancelled_by) WHERE cancelled_by IS NOT NULL"
    )
    op.execute(
        "COMMENT ON COLUMN orders.cancelled_by IS 'Quem cancelou: customer | admin | system'"
    )
    op.execute(
        "COMMENT ON COLUMN orders.cancellation_reason IS 'Motivo legivel do cancelamento'"
    )
    op.execute(
        "COMMENT ON COLUMN orders.cancelled_at IS 'Timestamp do cancelamento'"
    )


def downgrade() -> None:
    raise RuntimeError(
        "Order cancellation tracking is forward-only; cancellation history must be preserved."
    )

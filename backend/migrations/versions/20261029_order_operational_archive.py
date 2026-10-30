"""Add forward-only operational order archiving."""
from __future__ import annotations

from alembic import op


revision = "20261029_order_operational_archive"
down_revision = "20261028_gestor_gateway_instance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE orders "
        "ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ, "
        "ADD COLUMN IF NOT EXISTS archived_by VARCHAR(100), "
        "ADD COLUMN IF NOT EXISTS archive_reason TEXT"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_orders_tenant_archived_at "
        "ON orders (tenant_id, archived_at)"
    )
    op.execute(
        "COMMENT ON COLUMN orders.archived_at IS 'Remocao operacional; nao representa exclusao fisica'"
    )
    op.execute(
        "COMMENT ON COLUMN orders.archived_by IS 'Administrador ou processo que arquivou o pedido'"
    )
    op.execute(
        "COMMENT ON COLUMN orders.archive_reason IS 'Motivo da remocao operacional'"
    )


def downgrade() -> None:
    raise RuntimeError(
        "Operational order archive is forward-only; historical order evidence must be preserved."
    )

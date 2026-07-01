"""gestao finance payment receivables

Revision ID: 20260630_gestao_finance_payment_receivables
Revises: 20260630_gestao_finance_settlements
"""
from __future__ import annotations

from alembic import op

revision = "20260630_gestao_finance_payment_receivables"
down_revision = "20260630_gestao_finance_settlements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_payment_receivable_origin
        ON finance_transactions(tenant_id, origin_type, origin_id)
        WHERE origin_type = 'payment_receivable' AND origin_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_finance_payment_receivable_origin")

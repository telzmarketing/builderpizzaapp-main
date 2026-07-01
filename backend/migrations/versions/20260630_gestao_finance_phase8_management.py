"""gestao finance phase8 management

Revision ID: 20260630_gestao_finance_phase8_management
Revises: 20260630_gestao_finance_payment_receivables
"""
from __future__ import annotations

from alembic import op

revision = "20260630_gestao_finance_phase8_management"
down_revision = "20260630_gestao_finance_payment_receivables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE finance_transactions ADD COLUMN IF NOT EXISTS cost_center VARCHAR(120)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_finance_transactions_cost_center ON finance_transactions(cost_center)")
    op.execute(
        """
        UPDATE gestao_module_settings
        SET settings_json = (
            COALESCE(settings_json::jsonb, '{}'::jsonb)
            || '{"auto_create_payables_from_purchases": false, "default_receivable_account_id": null, "default_payable_account_id": null}'::jsonb
        )::text
        WHERE module_key = 'finance'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_finance_transactions_cost_center")
    op.execute("ALTER TABLE finance_transactions DROP COLUMN IF EXISTS cost_center")

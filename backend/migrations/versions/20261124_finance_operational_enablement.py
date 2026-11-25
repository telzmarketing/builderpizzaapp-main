"""Enable tenant-scoped operational finance projections by default."""

from alembic import op


revision = "20261124_finance_operational_enablement"
down_revision = "20261124_purchase_receipt_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE gestao_module_settings
        SET enabled = TRUE,
            status = 'active',
            settings_json = (
                COALESCE(settings_json::jsonb, '{}'::jsonb)
                || '{"auto_create_receivables": true, "auto_create_payables_from_purchases": true}'::jsonb
            )::text
        WHERE module_key = 'finance'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE gestao_module_settings
        SET settings_json = jsonb_set(
                jsonb_set(COALESCE(settings_json::jsonb, '{}'::jsonb), '{auto_create_receivables}', 'false'::jsonb, TRUE),
                '{auto_create_payables_from_purchases}', 'false'::jsonb, TRUE
            )::text
        WHERE module_key = 'finance'
        """
    )

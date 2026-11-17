"""Enable automatic order receivables for the operational finance module."""

from alembic import op


revision = "20261116_finance_sales_receivables"
down_revision = "20261115_delivery_daily_allowances"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE gestao_module_settings
        SET enabled = TRUE,
            status = 'active',
            settings_json = jsonb_set(
                COALESCE(settings_json::jsonb, '{}'::jsonb),
                '{auto_create_receivables}',
                'true'::jsonb,
                TRUE
            )::text
        WHERE module_key = 'finance'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE gestao_module_settings
        SET settings_json = jsonb_set(
                COALESCE(settings_json::jsonb, '{}'::jsonb),
                '{auto_create_receivables}',
                'false'::jsonb,
                TRUE
            )::text
        WHERE module_key = 'finance'
        """
    )

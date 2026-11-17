"""Add an explicit public promotions entry-point setting to the home catalog."""

from alembic import op


revision = "20261117_home_promotions_link"
down_revision = "20261116_finance_sales_receivables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE IF EXISTS home_catalog_config "
        "ADD COLUMN IF NOT EXISTS show_promotions_link BOOLEAN NOT NULL DEFAULT TRUE"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE IF EXISTS home_catalog_config "
        "DROP COLUMN IF EXISTS show_promotions_link"
    )

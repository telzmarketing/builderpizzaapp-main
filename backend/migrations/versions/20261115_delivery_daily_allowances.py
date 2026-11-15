"""Add tenant-scoped motoboy daily allowances and per-driver overrides."""

from alembic import op


revision = "20261115_delivery_daily_allowances"
down_revision = "20261114_upsell_subcategory_triggers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE logistics_settings ADD COLUMN IF NOT EXISTS "
        "daily_allowance_amount FLOAT NOT NULL DEFAULT 50.0"
    )
    op.execute(
        "ALTER TABLE delivery_persons ADD COLUMN IF NOT EXISTS "
        "daily_allowance_amount FLOAT"
    )
    op.execute(
        "ALTER TABLE delivery_earnings ADD COLUMN IF NOT EXISTS "
        "earning_type VARCHAR(30) NOT NULL DEFAULT 'delivery'"
    )
    op.execute("ALTER TABLE delivery_earnings ALTER COLUMN delivery_id DROP NOT NULL")
    op.execute(
        "UPDATE logistics_settings SET daily_allowance_amount = 50.0 "
        "WHERE daily_allowance_amount IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_delivery_earnings_daily_allowance "
        "ON delivery_earnings (tenant_id, delivery_person_id, period_date, earning_type) "
        "WHERE earning_type = 'daily_allowance'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_delivery_earnings_daily_allowance")
    op.execute("DELETE FROM delivery_earnings WHERE earning_type = 'daily_allowance'")
    op.execute("ALTER TABLE delivery_earnings ALTER COLUMN delivery_id SET NOT NULL")
    op.execute("ALTER TABLE delivery_earnings DROP COLUMN IF EXISTS earning_type")
    op.execute("ALTER TABLE delivery_persons DROP COLUMN IF EXISTS daily_allowance_amount")
    op.execute("ALTER TABLE logistics_settings DROP COLUMN IF EXISTS daily_allowance_amount")

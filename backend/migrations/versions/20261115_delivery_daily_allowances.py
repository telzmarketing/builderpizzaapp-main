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
        "UPDATE logistics_settings SET daily_allowance_amount = 50.0 "
        "WHERE daily_allowance_amount IS NULL"
    )
    op.execute(
        "CREATE TABLE IF NOT EXISTS delivery_daily_allowances ("
        "id VARCHAR PRIMARY KEY, "
        "tenant_id VARCHAR NOT NULL REFERENCES tenants(id), "
        "delivery_person_id VARCHAR NOT NULL REFERENCES delivery_persons(id) ON DELETE CASCADE, "
        "amount FLOAT NOT NULL DEFAULT 0.0, "
        "status VARCHAR(20) NOT NULL DEFAULT 'pending', "
        "period_date DATE NOT NULL, "
        "paid_at TIMESTAMPTZ, paid_by VARCHAR(200), notes TEXT, "
        "created_at TIMESTAMPTZ DEFAULT NOW()"
        ")"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_delivery_daily_allowances_tenant_person_date "
        "ON delivery_daily_allowances (tenant_id, delivery_person_id, period_date)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_delivery_daily_allowances_tenant_person_date")
    op.execute("DROP TABLE IF EXISTS delivery_daily_allowances")
    op.execute("ALTER TABLE delivery_persons DROP COLUMN IF EXISTS daily_allowance_amount")
    op.execute("ALTER TABLE logistics_settings DROP COLUMN IF EXISTS daily_allowance_amount")

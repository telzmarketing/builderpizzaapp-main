"""store operation hours

Revision ID: 20260425_store_operation
Revises: 20260425_product_promotions
Create Date: 2026-04-25
"""
from __future__ import annotations

from alembic import op

revision = "20260425_store_operation"
down_revision = "20260425_product_promotions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS store_operation_settings (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            manual_mode VARCHAR(30) NOT NULL DEFAULT 'manual_open',
            closed_message TEXT NOT NULL DEFAULT 'Loja fechada no momento.',
            allow_scheduled_orders BOOLEAN NOT NULL DEFAULT FALSE,
            timezone VARCHAR(80) NOT NULL DEFAULT 'America/Sao_Paulo',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_operation_settings_tenant_id ON store_operation_settings(tenant_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS store_weekly_schedules (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            weekday INTEGER NOT NULL,
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_weekly_schedules_tenant_id ON store_weekly_schedules(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_weekly_schedules_weekday ON store_weekly_schedules(weekday)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS store_operation_intervals (
            id VARCHAR PRIMARY KEY,
            schedule_id VARCHAR NOT NULL REFERENCES store_weekly_schedules(id) ON DELETE CASCADE,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            open_time TIME NOT NULL,
            close_time TIME NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_operation_intervals_schedule_id ON store_operation_intervals(schedule_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_operation_intervals_tenant_id ON store_operation_intervals(tenant_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS store_operation_exceptions (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            date DATE NOT NULL,
            exception_type VARCHAR(30) NOT NULL,
            open_time TIME,
            close_time TIME,
            reason TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_operation_exceptions_tenant_id ON store_operation_exceptions(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_operation_exceptions_date ON store_operation_exceptions(date)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS store_operation_logs (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(80) NOT NULL DEFAULT 'default',
            admin_id VARCHAR,
            admin_email VARCHAR(200),
            action VARCHAR(80) NOT NULL,
            entity VARCHAR(80) NOT NULL,
            entity_id VARCHAR,
            old_value TEXT,
            new_value TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_store_operation_logs_tenant_id ON store_operation_logs(tenant_id)")

    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS is_scheduled BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE orders ADD COLUMN IF NOT EXISTS scheduled_for TIMESTAMPTZ")


def downgrade() -> None:
    op.drop_column("orders", "scheduled_for")
    op.drop_column("orders", "is_scheduled")
    op.drop_table("store_operation_logs")
    op.drop_table("store_operation_exceptions")
    op.drop_table("store_operation_intervals")
    op.drop_table("store_weekly_schedules")
    op.drop_table("store_operation_settings")

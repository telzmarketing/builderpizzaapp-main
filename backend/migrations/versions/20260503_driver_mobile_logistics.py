"""driver mobile logistics hardening

Revision ID: 20260503_driver_mobile_logistics
Revises: 20260503_business_intelligence
Create Date: 2026-05-03
"""
from __future__ import annotations

from alembic import op

revision = "20260503_driver_mobile_logistics"
down_revision = "20260503_business_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS deliveries ADD COLUMN IF NOT EXISTS problem_report TEXT")
    op.execute("ALTER TABLE IF EXISTS deliveries ADD COLUMN IF NOT EXISTS problem_reported_at TIMESTAMPTZ")
    op.execute("ALTER TABLE IF EXISTS delivery_events ADD COLUMN IF NOT EXISTS actor_type VARCHAR(40)")
    op.execute("ALTER TABLE IF EXISTS delivery_events ADD COLUMN IF NOT EXISTS actor_id VARCHAR")
    op.execute("ALTER TABLE IF EXISTS delivery_earnings ALTER COLUMN status SET DEFAULT 'pending'")

    op.execute("CREATE INDEX IF NOT EXISTS ix_deliveries_driver_status ON deliveries(delivery_person_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_deliveries_order_status ON deliveries(order_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_delivery_events_delivery_created ON delivery_events(delivery_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_delivery_earnings_driver_period ON delivery_earnings(delivery_person_id, period_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_delivery_earnings_status_period ON delivery_earnings(status, period_date)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_delivery_earnings_status_period")
    op.execute("DROP INDEX IF EXISTS ix_delivery_earnings_driver_period")
    op.execute("DROP INDEX IF EXISTS ix_delivery_events_delivery_created")
    op.execute("DROP INDEX IF EXISTS ix_deliveries_order_status")
    op.execute("DROP INDEX IF EXISTS ix_deliveries_driver_status")
    op.execute("ALTER TABLE IF EXISTS delivery_events DROP COLUMN IF EXISTS actor_id")
    op.execute("ALTER TABLE IF EXISTS delivery_events DROP COLUMN IF EXISTS actor_type")
    op.execute("ALTER TABLE IF EXISTS deliveries DROP COLUMN IF EXISTS problem_reported_at")
    op.execute("ALTER TABLE IF EXISTS deliveries DROP COLUMN IF EXISTS problem_report")

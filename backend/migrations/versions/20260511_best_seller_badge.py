"""best seller badge

Revision ID: 20260511_best_seller_badge
Revises: 20260511_visitor_location_status
Create Date: 2026-05-11
"""
from alembic import op

revision = "20260511_best_seller_badge"
down_revision = "20260511_visitor_location_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS best_seller_badge_mode VARCHAR(10) DEFAULT 'off'")
    op.execute("""
        CREATE TABLE IF NOT EXISTS best_seller_config (
            id VARCHAR PRIMARY KEY DEFAULT 'default',
            period_days INTEGER DEFAULT 30,
            top_count INTEGER DEFAULT 5,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    op.execute(
        "INSERT INTO best_seller_config (id, period_days, top_count) "
        "VALUES ('default', 30, 5) ON CONFLICT DO NOTHING"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS best_seller_badge_mode")
    op.execute("DROP TABLE IF EXISTS best_seller_config")

"""coupon trigger automation binding

Revision ID: 20260505_coupon_trigger_automation
Revises: 20260504_coupon_compound_benefits
Create Date: 2026-05-05
"""
from __future__ import annotations

from alembic import op

revision = "20260505_coupon_trigger_automation"
down_revision = "20260504_coupon_compound_benefits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE IF EXISTS coupons "
        "ADD COLUMN IF NOT EXISTS trigger_automation_id VARCHAR "
        "REFERENCES marketing_automations(id) ON DELETE SET NULL"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_coupons_trigger_automation_id ON coupons(trigger_automation_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_coupons_trigger_automation_id")
    op.execute("ALTER TABLE IF EXISTS coupons DROP COLUMN IF EXISTS trigger_automation_id")

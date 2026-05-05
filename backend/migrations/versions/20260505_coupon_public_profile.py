"""coupon public profile visibility

Revision ID: 20260505_coupon_public_profile
Revises: 20260505_coupon_trigger_automation
Create Date: 2026-05-05
"""

from alembic import op


revision = "20260505_coupon_public_profile"
down_revision = "20260505_coupon_trigger_automation"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE IF EXISTS coupons ADD COLUMN IF NOT EXISTS public_profile BOOLEAN DEFAULT FALSE")
    op.execute("CREATE INDEX IF NOT EXISTS ix_coupons_public_profile ON coupons(public_profile)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_coupons_public_profile")
    op.execute("ALTER TABLE IF EXISTS coupons DROP COLUMN IF EXISTS public_profile")

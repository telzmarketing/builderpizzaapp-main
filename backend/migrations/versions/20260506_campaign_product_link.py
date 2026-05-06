"""campaign direct product link for banner click

Revision ID: 20260506_campaign_product_link
Revises: 20260505_coupon_public_profile
Create Date: 2026-05-06
"""

from alembic import op

revision = "20260506_campaign_product_link"
down_revision = "20260505_coupon_public_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE campaigns
        ADD COLUMN IF NOT EXISTS product_id VARCHAR
        REFERENCES products(id) ON DELETE SET NULL
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_campaigns_product_id ON campaigns(product_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_campaigns_product_id")
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS product_id")

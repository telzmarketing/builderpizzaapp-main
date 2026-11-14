"""Add product, category, or kit destination to store campaign banners."""

from alembic import op


revision = "20261113_campaign_highlight_target"
down_revision = "20261113_payment_secret_encryption"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS highlight_type VARCHAR(20)")
    op.execute("ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS highlight_id VARCHAR")
    op.execute("UPDATE campaigns SET highlight_type = 'product', highlight_id = product_id WHERE highlight_type IS NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS highlight_id")
    op.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS highlight_type")

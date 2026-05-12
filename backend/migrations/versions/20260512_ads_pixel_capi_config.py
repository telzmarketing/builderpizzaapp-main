"""Add Meta Pixel CAPI and base code fields."""

from alembic import op


revision = "20260512_ads_pixel_capi_config"
down_revision = "20260512_exit_popup_delay"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE ads_pixels ADD COLUMN IF NOT EXISTS conversion_access_token TEXT")
    op.execute("ALTER TABLE ads_pixels ADD COLUMN IF NOT EXISTS base_code TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE ads_pixels DROP COLUMN IF EXISTS base_code")
    op.execute("ALTER TABLE ads_pixels DROP COLUMN IF EXISTS conversion_access_token")

"""Update ads pixel event defaults."""

from alembic import op


revision = "20260512_ads_pixel_event_defaults"
down_revision = "20260512_ads_pixel_capi_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE ads_pixels ALTER COLUMN events_tracked "
        "SET DEFAULT 'PageView,ViewContent,AddToCart,InitiateCheckout,Purchase,Lead'"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE ads_pixels ALTER COLUMN events_tracked "
        "SET DEFAULT 'PageView,Purchase,Lead'"
    )

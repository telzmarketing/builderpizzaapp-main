"""Add editable text labels to promotion landing pages.

Revision ID: 20260520_promotion_landing_text_labels
Revises: 20260520_salao_site_cms_overrides
Create Date: 2026-05-20
"""

from alembic import op


revision = "20260520_promotion_landing_text_labels"
down_revision = "20260520_salao_site_cms_overrides"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE promotion_landing_pages "
        "ADD COLUMN IF NOT EXISTS free_shipping_label VARCHAR(160) NOT NULL DEFAULT 'Frete gratis na promocao'"
    )
    op.execute(
        "ALTER TABLE promotion_landing_pages "
        "ADD COLUMN IF NOT EXISTS gift_label_prefix VARCHAR(80) NOT NULL DEFAULT 'Brinde'"
    )
    op.execute(
        "ALTER TABLE promotion_landing_pages "
        "ADD COLUMN IF NOT EXISTS gift_fallback_label VARCHAR(160) NOT NULL DEFAULT 'Brinde incluido'"
    )
    op.execute(
        "ALTER TABLE promotion_landing_pages "
        "ADD COLUMN IF NOT EXISTS active_offer_label VARCHAR(160) NOT NULL DEFAULT 'Oferta ativa agora'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE promotion_landing_pages DROP COLUMN IF EXISTS active_offer_label")
    op.execute("ALTER TABLE promotion_landing_pages DROP COLUMN IF EXISTS gift_fallback_label")
    op.execute("ALTER TABLE promotion_landing_pages DROP COLUMN IF EXISTS gift_label_prefix")
    op.execute("ALTER TABLE promotion_landing_pages DROP COLUMN IF EXISTS free_shipping_label")

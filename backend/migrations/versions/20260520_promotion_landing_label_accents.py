"""Fix default Portuguese labels in promotion landing pages.

Revision ID: 20260520_promotion_landing_label_accents
Revises: 20260520_promotion_landing_text_labels
Create Date: 2026-05-20
"""

from alembic import op


revision = "20260520_promotion_landing_label_accents"
down_revision = "20260520_promotion_landing_text_labels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE promotion_landing_pages "
        "ALTER COLUMN free_shipping_label SET DEFAULT 'Frete grátis na promoção'"
    )
    op.execute(
        "ALTER TABLE promotion_landing_pages "
        "ALTER COLUMN gift_fallback_label SET DEFAULT 'Brinde incluído'"
    )
    op.execute(
        "UPDATE promotion_landing_pages "
        "SET free_shipping_label = 'Frete grátis na promoção' "
        "WHERE free_shipping_label = 'Frete gratis na promocao'"
    )
    op.execute(
        "UPDATE promotion_landing_pages "
        "SET gift_fallback_label = 'Brinde incluído' "
        "WHERE gift_fallback_label = 'Brinde incluido'"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE promotion_landing_pages "
        "ALTER COLUMN free_shipping_label SET DEFAULT 'Frete gratis na promocao'"
    )
    op.execute(
        "ALTER TABLE promotion_landing_pages "
        "ALTER COLUMN gift_fallback_label SET DEFAULT 'Brinde incluido'"
    )

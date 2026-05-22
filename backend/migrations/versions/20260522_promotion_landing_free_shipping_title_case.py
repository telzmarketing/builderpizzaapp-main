"""Title-case promotion landing free shipping label.

Revision ID: 20260522_promotion_landing_free_shipping_title_case
Revises: 20260520_salao_blog_posts
Create Date: 2026-05-22
"""

from alembic import op


revision = "20260522_promotion_landing_free_shipping_title_case"
down_revision = "20260520_salao_blog_posts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE promotion_landing_pages "
        "ALTER COLUMN free_shipping_label SET DEFAULT 'Frete Grátis na Promoção'"
    )
    op.execute(
        "UPDATE promotion_landing_pages "
        "SET free_shipping_label = 'Frete Grátis na Promoção' "
        "WHERE free_shipping_label IN ('Frete grátis na promoção', 'Frete gratis na promocao')"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE promotion_landing_pages "
        "ALTER COLUMN free_shipping_label SET DEFAULT 'Frete grátis na promoção'"
    )

"""multi flavor category filters

Revision ID: 20260526_multi_flavor_category_filters
Revises: 20260522_promotion_landing_free_shipping_title_case
Create Date: 2026-05-26
"""
from __future__ import annotations

from alembic import op

revision = "20260526_multi_flavor_category_filters"
down_revision = "20260522_promotion_landing_free_shipping_title_case"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE multi_flavors_config "
        "ADD COLUMN IF NOT EXISTS flavor_category_filters JSONB NOT NULL DEFAULT '[]'::jsonb"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE multi_flavors_config DROP COLUMN IF EXISTS flavor_category_filters")

"""product categories table

Revision ID: 20260424_product_categories
Revises: 20260423_payment_brick
Create Date: 2026-04-24
"""
from __future__ import annotations

from alembic import op

revision = "20260424_product_categories"
down_revision = "20260423_payment_brick"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS product_categories (
            id VARCHAR PRIMARY KEY,
            name VARCHAR(100) NOT NULL UNIQUE,
            active BOOLEAN DEFAULT TRUE,
            sort_order INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )


def downgrade() -> None:
    op.drop_table("product_categories")

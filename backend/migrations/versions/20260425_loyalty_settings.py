"""loyalty settings

Revision ID: 20260425_loyalty_settings
Revises: 20260425_product_subcategories
Create Date: 2026-04-25
"""
from __future__ import annotations

from alembic import op

revision = "20260425_loyalty_settings"
down_revision = "20260425_product_subcategories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS loyalty_settings (
            id VARCHAR PRIMARY KEY,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            points_per_real FLOAT NOT NULL DEFAULT 1.0,
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        "INSERT INTO loyalty_settings (id, enabled, points_per_real) "
        "VALUES ('default', TRUE, 1.0) "
        "ON CONFLICT (id) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("loyalty_settings")

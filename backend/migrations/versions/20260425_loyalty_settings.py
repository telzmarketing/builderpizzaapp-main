"""loyalty settings

Revision ID: 20260425_loyalty_settings
Revises: 20260425_product_subcategories
Create Date: 2026-04-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260425_loyalty_settings"
down_revision = "20260425_product_subcategories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "loyalty_settings",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("points_per_real", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.text("NOW()")),
    )
    op.execute(
        "INSERT INTO loyalty_settings (id, enabled, points_per_real) "
        "VALUES ('default', TRUE, 1.0) "
        "ON CONFLICT (id) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("loyalty_settings")

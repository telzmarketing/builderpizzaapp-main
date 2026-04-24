"""standard pizza size descriptions

Revision ID: 20260424_pizza_size_descriptions
Revises: 20260424_paid_traffic
Create Date: 2026-04-24
"""
from __future__ import annotations

from alembic import op

revision = "20260424_pizza_size_descriptions"
down_revision = "20260424_paid_traffic"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE product_sizes
        SET label = 'Pizza Broto',
            description = '25cm - 4 pedaços'
        WHERE LOWER(label) IN ('brotinho', 'pizza broto')
        """
    )
    op.execute(
        """
        UPDATE product_sizes
        SET description = '35cm - 8 pedaços'
        WHERE LOWER(label) = 'pizza grande'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE product_sizes
        SET label = 'Brotinho',
            description = 'Individual'
        WHERE LOWER(label) = 'pizza broto'
          AND description = '25cm - 4 pedaços'
        """
    )
    op.execute(
        """
        UPDATE product_sizes
        SET description = 'Grande'
        WHERE LOWER(label) = 'pizza grande'
          AND description = '35cm - 8 pedaços'
        """
    )

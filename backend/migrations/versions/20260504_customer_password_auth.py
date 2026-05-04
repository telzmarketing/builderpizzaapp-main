"""customer password authentication

Revision ID: 20260504_customer_password_auth
Revises: 20260503_driver_mobile_logistics
Create Date: 2026-05-04
"""
from __future__ import annotations

from alembic import op

revision = "20260504_customer_password_auth"
down_revision = "20260503_driver_mobile_logistics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS customers ADD COLUMN IF NOT EXISTS password_hash TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS customers DROP COLUMN IF EXISTS password_hash")

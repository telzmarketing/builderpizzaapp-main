"""add non-sensitive card metadata

Revision ID: 20260703_asaas_card_metadata
Revises: 20260702_asaas_provider_customers
Create Date: 2026-07-03
"""
from __future__ import annotations

from alembic import op

revision = "20260703_asaas_card_metadata"
down_revision = "20260702_asaas_provider_customers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS card_brand VARCHAR(40)")
    op.execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS card_brand_logo VARCHAR(80)")


def downgrade() -> None:
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS card_brand_logo")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS card_brand")

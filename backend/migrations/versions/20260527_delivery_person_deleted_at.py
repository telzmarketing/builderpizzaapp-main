"""delivery person deleted at

Revision ID: 20260527_delivery_person_deleted_at
Revises: 20260526_multi_flavor_category_filters
Create Date: 2026-05-27
"""
from __future__ import annotations

from alembic import op

revision = "20260527_delivery_person_deleted_at"
down_revision = "20260526_multi_flavor_category_filters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE delivery_persons ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ")


def downgrade() -> None:
    op.execute("ALTER TABLE delivery_persons DROP COLUMN IF EXISTS deleted_at")

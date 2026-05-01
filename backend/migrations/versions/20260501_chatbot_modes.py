"""chatbot service modes

Revision ID: 20260501_chatbot_modes
Revises: 20260426_runtime_backfill
Create Date: 2026-05-01
"""
from __future__ import annotations

from alembic import op

revision = "20260501_chatbot_modes"
down_revision = "20260426_runtime_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE chatbot_settings ADD COLUMN IF NOT EXISTS ia_ativo BOOLEAN DEFAULT TRUE")
    op.execute("UPDATE chatbot_settings SET ia_ativo = TRUE WHERE ia_ativo IS NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE chatbot_settings DROP COLUMN IF EXISTS ia_ativo")

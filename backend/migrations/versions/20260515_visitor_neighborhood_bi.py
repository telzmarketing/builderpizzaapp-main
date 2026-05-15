"""visitor neighborhood analytics

Revision ID: 20260515_visitor_neighborhood_bi
Revises: 20260514_agente_whatsapp_ai_settings
Create Date: 2026-05-15
"""

from alembic import op


revision = "20260515_visitor_neighborhood_bi"
down_revision = "20260514_agente_whatsapp_ai_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE visitor_profiles ADD COLUMN IF NOT EXISTS neighborhood VARCHAR(120)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_visitor_profiles_neighborhood ON visitor_profiles(neighborhood)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_visitor_profiles_neighborhood")
    op.execute("ALTER TABLE visitor_profiles DROP COLUMN IF EXISTS neighborhood")

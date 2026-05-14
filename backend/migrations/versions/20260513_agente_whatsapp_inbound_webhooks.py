"""agente whatsapp inbound webhooks

Revision ID: 20260513_agente_whatsapp_inbound_webhooks
Revises: 20260513_agente_whatsapp_core
Create Date: 2026-05-13
"""
from __future__ import annotations

from alembic import op

revision = "20260513_agente_whatsapp_inbound_webhooks"
down_revision = "20260513_agente_whatsapp_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_agente_whatsapp_messages_provider_message_id
        ON agente_whatsapp_messages(provider_message_id)
        WHERE provider_message_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_agente_whatsapp_messages_provider_message_id")

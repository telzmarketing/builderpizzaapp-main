"""Add AGENTE WHATSAPP outbox queue."""
from alembic import op


revision = "20260513_agente_whatsapp_outbox"
down_revision = "20260513_agente_whatsapp_tools"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agente_whatsapp_outbox (
            id VARCHAR PRIMARY KEY,
            message_id VARCHAR NOT NULL UNIQUE REFERENCES agente_whatsapp_messages(id) ON DELETE CASCADE,
            session_id VARCHAR NOT NULL REFERENCES agente_whatsapp_sessions(id) ON DELETE CASCADE,
            customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL,
            phone VARCHAR(30) NOT NULL,
            provider VARCHAR(40) NOT NULL DEFAULT 'official',
            status VARCHAR(30) NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            idempotency_key VARCHAR(180) NOT NULL UNIQUE,
            payload_json TEXT NOT NULL DEFAULT '{}',
            provider_message_id VARCHAR(255),
            error TEXT,
            next_attempt_at TIMESTAMPTZ,
            locked_at TIMESTAMPTZ,
            sent_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_outbox_session_id ON agente_whatsapp_outbox(session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_outbox_customer_id ON agente_whatsapp_outbox(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_outbox_phone ON agente_whatsapp_outbox(phone)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_outbox_status_next_attempt "
        "ON agente_whatsapp_outbox(status, next_attempt_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_outbox_provider_message_id "
        "ON agente_whatsapp_outbox(provider_message_id)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_outbox_created_at ON agente_whatsapp_outbox(created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agente_whatsapp_outbox")

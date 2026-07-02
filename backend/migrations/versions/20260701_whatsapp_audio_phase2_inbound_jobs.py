"""whatsapp audio phase2 inbound jobs

Revision ID: 20260701_whatsapp_audio_phase2_inbound_jobs
Revises: 20260701_whatsapp_audio_phase1_deliveries
"""
from __future__ import annotations

from alembic import op

revision = "20260701_whatsapp_audio_phase2_inbound_jobs"
down_revision = "20260701_whatsapp_audio_phase1_deliveries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS processing_status VARCHAR(30) NOT NULL DEFAULT 'recorded'")
    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(220)")
    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_messages_processing_status ON agente_whatsapp_messages(processing_status)")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_agente_whatsapp_messages_idempotency_key
        ON agente_whatsapp_messages(idempotency_key)
        WHERE idempotency_key IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE agente_whatsapp_messages
        SET idempotency_key = (
            COALESCE(provider, 'unknown')
            || ':'
            || provider_message_id
        )
        WHERE provider_message_id IS NOT NULL
          AND idempotency_key IS NULL
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agente_whatsapp_processing_jobs (
            id VARCHAR PRIMARY KEY,
            message_id VARCHAR NOT NULL REFERENCES agente_whatsapp_messages(id) ON DELETE CASCADE,
            session_id VARCHAR NOT NULL REFERENCES agente_whatsapp_sessions(id) ON DELETE CASCADE,
            customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL,
            job_type VARCHAR(60) NOT NULL,
            status VARCHAR(30) NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            idempotency_key VARCHAR(220) NOT NULL UNIQUE,
            payload_json TEXT NOT NULL DEFAULT '{}',
            error TEXT,
            next_attempt_at TIMESTAMPTZ,
            locked_at TIMESTAMPTZ,
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_processing_jobs_message_id ON agente_whatsapp_processing_jobs(message_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_processing_jobs_session_id ON agente_whatsapp_processing_jobs(session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_processing_jobs_customer_id ON agente_whatsapp_processing_jobs(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_processing_jobs_job_type ON agente_whatsapp_processing_jobs(job_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_processing_jobs_status ON agente_whatsapp_processing_jobs(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_processing_jobs_next_attempt_at ON agente_whatsapp_processing_jobs(next_attempt_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_processing_jobs_created_at ON agente_whatsapp_processing_jobs(created_at DESC)")

    op.execute(
        """
        INSERT INTO agente_whatsapp_processing_jobs (
            id,
            message_id,
            session_id,
            customer_id,
            job_type,
            status,
            attempts,
            max_attempts,
            idempotency_key,
            payload_json,
            next_attempt_at,
            created_at,
            updated_at
        )
        SELECT
            'awpj-inbound-' || m.id,
            m.id,
            m.session_id,
            m.customer_id,
            'inbound_message',
            'pending',
            0,
            3,
            'inbound_message:' || m.id,
            json_build_object(
                'source', 'backfill',
                'message_type', m.message_type,
                'provider_message_id', m.provider_message_id
            )::text,
            NOW(),
            NOW(),
            NOW()
        FROM agente_whatsapp_messages m
        WHERE m.direction = 'inbound'
          AND NOT EXISTS (
              SELECT 1
              FROM agente_whatsapp_processing_jobs existing
              WHERE existing.idempotency_key = ('inbound_message:' || m.id)
          )
        """
    )
    op.execute(
        """
        UPDATE agente_whatsapp_messages
        SET processing_status = 'queued'
        WHERE direction = 'inbound'
          AND processing_status = 'recorded'
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agente_whatsapp_processing_jobs")
    op.execute("DROP INDEX IF EXISTS uq_agente_whatsapp_messages_idempotency_key")
    op.execute("DROP INDEX IF EXISTS ix_agente_whatsapp_messages_processing_status")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS processed_at")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS idempotency_key")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS processing_status")

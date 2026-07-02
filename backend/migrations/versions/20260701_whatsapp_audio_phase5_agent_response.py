"""whatsapp audio phase5 agent response

Revision ID: 20260701_whatsapp_audio_phase5_agent_response
Revises: 20260701_whatsapp_audio_phase3_audio_stt
"""
from __future__ import annotations

from alembic import op

revision = "20260701_whatsapp_audio_phase5_agent_response"
down_revision = "20260701_whatsapp_audio_phase3_audio_stt"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS response_to_message_id VARCHAR")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_messages_response_to_message_id ON agente_whatsapp_messages(response_to_message_id)")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_agente_whatsapp_messages_response_to'
                  AND table_name = 'agente_whatsapp_messages'
            ) THEN
                ALTER TABLE agente_whatsapp_messages
                ADD CONSTRAINT fk_agente_whatsapp_messages_response_to
                FOREIGN KEY (response_to_message_id)
                REFERENCES agente_whatsapp_messages(id)
                ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )
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
            'awpj-agent-response-' || m.id,
            m.id,
            m.session_id,
            m.customer_id,
            'agent_response',
            'pending',
            0,
            3,
            'agent_response:' || m.id,
            json_build_object(
                'source', 'phase5_backfill',
                'message_type', m.message_type,
                'transcription_status', m.transcription_status
            )::text,
            NOW(),
            NOW(),
            NOW()
        FROM agente_whatsapp_messages m
        WHERE m.direction = 'inbound'
          AND (
              m.message_type <> 'audio'
              OR m.transcription_status IN ('done', 'low_confidence')
          )
          AND NOT EXISTS (
              SELECT 1
              FROM agente_whatsapp_processing_jobs existing
              WHERE existing.idempotency_key = ('agent_response:' || m.id)
          )
          AND NOT EXISTS (
              SELECT 1
              FROM agente_whatsapp_messages response
              WHERE response.response_to_message_id = m.id
                AND response.direction = 'outbound'
          )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM agente_whatsapp_processing_jobs WHERE job_type = 'agent_response'")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_agente_whatsapp_messages_response_to'
                  AND table_name = 'agente_whatsapp_messages'
            ) THEN
                ALTER TABLE agente_whatsapp_messages
                DROP CONSTRAINT fk_agente_whatsapp_messages_response_to;
            END IF;
        END $$;
        """
    )
    op.execute("DROP INDEX IF EXISTS ix_agente_whatsapp_messages_response_to_message_id")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS response_to_message_id")

"""whatsapp audio phase3 audio stt

Revision ID: 20260701_whatsapp_audio_phase3_audio_stt
Revises: 20260701_whatsapp_audio_phase2_inbound_jobs
"""
from __future__ import annotations

from alembic import op

revision = "20260701_whatsapp_audio_phase3_audio_stt"
down_revision = "20260701_whatsapp_audio_phase2_inbound_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS media_storage_key TEXT")
    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS media_mime_type VARCHAR(120)")
    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS media_duration_ms INTEGER")
    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS media_size_bytes INTEGER")
    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS transcription_status VARCHAR(30) NOT NULL DEFAULT 'none'")
    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS transcription_text TEXT")
    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS transcription_language VARCHAR(20)")
    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS transcription_provider VARCHAR(40)")
    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS transcription_model VARCHAR(120)")
    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS transcription_error TEXT")
    op.execute("ALTER TABLE agente_whatsapp_messages ADD COLUMN IF NOT EXISTS transcription_quality_json TEXT NOT NULL DEFAULT '{}'")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_messages_transcription_status ON agente_whatsapp_messages(transcription_status)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agente_whatsapp_audio_artifacts (
            id VARCHAR PRIMARY KEY,
            message_id VARCHAR NOT NULL REFERENCES agente_whatsapp_messages(id) ON DELETE CASCADE,
            artifact_type VARCHAR(40) NOT NULL,
            storage_key TEXT,
            media_url TEXT,
            mime_type VARCHAR(120),
            size_bytes INTEGER,
            duration_ms INTEGER,
            provider VARCHAR(40),
            model VARCHAR(120),
            status VARCHAR(30) NOT NULL DEFAULT 'stored',
            payload_json TEXT NOT NULL DEFAULT '{}',
            error TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_audio_artifacts_message_id ON agente_whatsapp_audio_artifacts(message_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_audio_artifacts_artifact_type ON agente_whatsapp_audio_artifacts(artifact_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_audio_artifacts_status ON agente_whatsapp_audio_artifacts(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_audio_artifacts_created_at ON agente_whatsapp_audio_artifacts(created_at DESC)")

    op.execute(
        """
        UPDATE agente_whatsapp_messages
        SET transcription_status = 'pending'
        WHERE direction = 'inbound'
          AND message_type = 'audio'
          AND transcription_status = 'none'
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
            'awpj-audio-' || m.id,
            m.id,
            m.session_id,
            m.customer_id,
            'audio_transcription',
            'pending',
            0,
            3,
            'audio_transcription:' || m.id,
            json_build_object(
                'source', 'phase3_backfill',
                'message_type', m.message_type,
                'provider', m.provider,
                'provider_message_id', m.provider_message_id,
                'media_url', m.media_url
            )::text,
            NOW(),
            NOW(),
            NOW()
        FROM agente_whatsapp_messages m
        WHERE m.direction = 'inbound'
          AND m.message_type = 'audio'
          AND NOT EXISTS (
              SELECT 1
              FROM agente_whatsapp_processing_jobs existing
              WHERE existing.idempotency_key = ('audio_transcription:' || m.id)
          )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM agente_whatsapp_processing_jobs WHERE job_type = 'audio_transcription'")
    op.execute("DROP TABLE IF EXISTS agente_whatsapp_audio_artifacts")
    op.execute("DROP INDEX IF EXISTS ix_agente_whatsapp_messages_transcription_status")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS transcription_quality_json")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS transcription_error")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS transcription_model")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS transcription_provider")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS transcription_language")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS transcription_text")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS transcription_status")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS media_size_bytes")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS media_duration_ms")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS media_mime_type")
    op.execute("ALTER TABLE agente_whatsapp_messages DROP COLUMN IF EXISTS media_storage_key")

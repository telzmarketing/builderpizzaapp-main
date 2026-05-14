"""Add AGENTE WHATSAPP provider escalation state."""
from alembic import op


revision = "20260514_agente_whatsapp_provider_states"
down_revision = "20260513_agente_whatsapp_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agente_whatsapp_provider_states (
            id VARCHAR PRIMARY KEY,
            provider VARCHAR(40) NOT NULL UNIQUE,
            status VARCHAR(30) NOT NULL DEFAULT 'active',
            consecutive_failures INTEGER NOT NULL DEFAULT 0,
            failure_threshold INTEGER NOT NULL DEFAULT 5,
            last_failure_at TIMESTAMPTZ,
            last_success_at TIMESTAMPTZ,
            paused_at TIMESTAMPTZ,
            paused_until TIMESTAMPTZ,
            paused_reason TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_provider_states_provider "
        "ON agente_whatsapp_provider_states(provider)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_provider_states_status "
        "ON agente_whatsapp_provider_states(status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_provider_states_paused_until "
        "ON agente_whatsapp_provider_states(paused_until)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agente_whatsapp_provider_states")

"""Add AGENTE WHATSAPP internal alerts."""
from alembic import op


revision = "20260514_agente_whatsapp_internal_alerts"
down_revision = "20260514_agente_whatsapp_provider_states"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agente_whatsapp_internal_alerts (
            id VARCHAR PRIMARY KEY,
            alert_type VARCHAR(80) NOT NULL,
            level VARCHAR(30) NOT NULL DEFAULT 'warning',
            status VARCHAR(30) NOT NULL DEFAULT 'active',
            title VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            dedupe_key VARCHAR(220) NOT NULL UNIQUE,
            payload_json TEXT NOT NULL DEFAULT '{}',
            first_seen_at TIMESTAMPTZ DEFAULT NOW(),
            last_seen_at TIMESTAMPTZ DEFAULT NOW(),
            acknowledged_at TIMESTAMPTZ,
            resolved_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_internal_alerts_alert_type "
        "ON agente_whatsapp_internal_alerts(alert_type)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_internal_alerts_level "
        "ON agente_whatsapp_internal_alerts(level)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_internal_alerts_status "
        "ON agente_whatsapp_internal_alerts(status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_internal_alerts_last_seen_at "
        "ON agente_whatsapp_internal_alerts(last_seen_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agente_whatsapp_internal_alerts")

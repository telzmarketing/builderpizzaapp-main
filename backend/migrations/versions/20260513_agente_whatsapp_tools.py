"""agente whatsapp tool calling audit

Revision ID: 20260513_agente_whatsapp_tools
Revises: 20260513_agente_whatsapp_inbound_webhooks
Create Date: 2026-05-13
"""

from alembic import op


revision = "20260513_agente_whatsapp_tools"
down_revision = "20260513_agente_whatsapp_inbound_webhooks"
branch_labels = None
depends_on = None


SQL = [
    """
    CREATE TABLE IF NOT EXISTS agente_whatsapp_tool_calls (
        id VARCHAR PRIMARY KEY,
        session_id VARCHAR REFERENCES agente_whatsapp_sessions(id) ON DELETE SET NULL,
        customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL,
        tool_name VARCHAR(120) NOT NULL,
        status VARCHAR(30) NOT NULL DEFAULT 'success',
        arguments_json TEXT NOT NULL DEFAULT '{}',
        result_json TEXT NOT NULL DEFAULT '{}',
        error TEXT,
        latency_ms INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_tool_calls_session_id ON agente_whatsapp_tool_calls(session_id)",
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_tool_calls_customer_id ON agente_whatsapp_tool_calls(customer_id)",
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_tool_calls_tool_name ON agente_whatsapp_tool_calls(tool_name)",
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_tool_calls_created_at ON agente_whatsapp_tool_calls(created_at DESC)",
]


def upgrade() -> None:
    for statement in SQL:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agente_whatsapp_tool_calls")

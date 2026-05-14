"""agente whatsapp core

Revision ID: 20260513_agente_whatsapp_core
Revises: 20260513_customer_identity_channels
Create Date: 2026-05-13
"""
from __future__ import annotations

from alembic import op

revision = "20260513_agente_whatsapp_core"
down_revision = "20260513_customer_identity_channels"
branch_labels = None
depends_on = None


AGENTE_WHATSAPP_SQL = [
    """
    CREATE TABLE IF NOT EXISTS agente_whatsapp_sessions (
        id VARCHAR PRIMARY KEY,
        customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL,
        phone VARCHAR(30) NOT NULL,
        provider VARCHAR(40) NOT NULL DEFAULT 'official',
        provider_contact_id VARCHAR(255),
        status VARCHAR(30) NOT NULL DEFAULT 'open',
        origin VARCHAR(40) NOT NULL DEFAULT 'manual',
        current_intent VARCHAR(120),
        last_message_at TIMESTAMPTZ,
        assigned_admin_id VARCHAR REFERENCES admin_users(id) ON DELETE SET NULL,
        ai_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        automation_blocked BOOLEAN NOT NULL DEFAULT FALSE,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_sessions_phone ON agente_whatsapp_sessions(phone)",
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_sessions_status ON agente_whatsapp_sessions(status)",
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_sessions_customer_id ON agente_whatsapp_sessions(customer_id)",
    """
    CREATE TABLE IF NOT EXISTS agente_whatsapp_messages (
        id VARCHAR PRIMARY KEY,
        session_id VARCHAR NOT NULL REFERENCES agente_whatsapp_sessions(id) ON DELETE CASCADE,
        customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL,
        direction VARCHAR(20) NOT NULL,
        sender_type VARCHAR(20) NOT NULL,
        message_type VARCHAR(30) NOT NULL DEFAULT 'text',
        body TEXT,
        media_url TEXT,
        provider_message_id VARCHAR(255),
        provider_status VARCHAR(40),
        error TEXT,
        raw_payload_json TEXT NOT NULL DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        delivered_at TIMESTAMPTZ,
        read_at TIMESTAMPTZ
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_messages_session_id ON agente_whatsapp_messages(session_id)",
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_messages_customer_id ON agente_whatsapp_messages(customer_id)",
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_messages_provider_message_id ON agente_whatsapp_messages(provider_message_id)",
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_messages_created_at ON agente_whatsapp_messages(created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS agente_whatsapp_events (
        id VARCHAR PRIMARY KEY,
        session_id VARCHAR REFERENCES agente_whatsapp_sessions(id) ON DELETE CASCADE,
        customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL,
        order_id VARCHAR REFERENCES orders(id) ON DELETE SET NULL,
        event_type VARCHAR(100) NOT NULL,
        source VARCHAR(80) NOT NULL DEFAULT 'agente_whatsapp',
        payload_json TEXT NOT NULL DEFAULT '{}',
        processed_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_events_session_id ON agente_whatsapp_events(session_id)",
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_events_event_type ON agente_whatsapp_events(event_type)",
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_events_created_at ON agente_whatsapp_events(created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS agente_whatsapp_context (
        id VARCHAR PRIMARY KEY,
        session_id VARCHAR NOT NULL UNIQUE REFERENCES agente_whatsapp_sessions(id) ON DELETE CASCADE,
        customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL,
        short_context_json TEXT NOT NULL DEFAULT '{}',
        long_context_json TEXT NOT NULL DEFAULT '{}',
        preferences_json TEXT NOT NULL DEFAULT '{}',
        behavior_json TEXT NOT NULL DEFAULT '{}',
        last_intent VARCHAR(120),
        sentiment VARCHAR(40),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_context_customer_id ON agente_whatsapp_context(customer_id)",
    """
    CREATE TABLE IF NOT EXISTS agente_whatsapp_metrics (
        id VARCHAR PRIMARY KEY,
        date DATE NOT NULL,
        sessions_opened INTEGER NOT NULL DEFAULT 0,
        messages_inbound INTEGER NOT NULL DEFAULT 0,
        messages_outbound INTEGER NOT NULL DEFAULT 0,
        ai_responses INTEGER NOT NULL DEFAULT 0,
        human_takeovers INTEGER NOT NULL DEFAULT 0,
        orders_created INTEGER NOT NULL DEFAULT 0,
        revenue FLOAT NOT NULL DEFAULT 0,
        avg_response_time_seconds FLOAT NOT NULL DEFAULT 0,
        abandoned_sessions INTEGER NOT NULL DEFAULT 0,
        recovered_carts INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_metrics_date ON agente_whatsapp_metrics(date)",
    """
    CREATE TABLE IF NOT EXISTS agente_whatsapp_campaigns (
        id VARCHAR PRIMARY KEY,
        name VARCHAR(300) NOT NULL,
        status VARCHAR(40) NOT NULL DEFAULT 'draft',
        campaign_type VARCHAR(60) NOT NULL DEFAULT 'manual',
        audience_json TEXT NOT NULL DEFAULT '{}',
        template_id VARCHAR,
        scheduled_at TIMESTAMPTZ,
        sent_count INTEGER NOT NULL DEFAULT 0,
        delivered_count INTEGER NOT NULL DEFAULT 0,
        read_count INTEGER NOT NULL DEFAULT 0,
        replied_count INTEGER NOT NULL DEFAULT 0,
        conversion_count INTEGER NOT NULL DEFAULT 0,
        revenue FLOAT NOT NULL DEFAULT 0,
        created_by VARCHAR(200),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_campaigns_status ON agente_whatsapp_campaigns(status)",
    """
    CREATE TABLE IF NOT EXISTS agente_whatsapp_stories (
        id VARCHAR PRIMARY KEY,
        campaign_id VARCHAR REFERENCES agente_whatsapp_campaigns(id) ON DELETE SET NULL,
        title VARCHAR(300) NOT NULL,
        media_type VARCHAR(20) NOT NULL,
        media_url TEXT NOT NULL,
        caption TEXT,
        cta_text VARCHAR(120),
        cta_url TEXT,
        status VARCHAR(40) NOT NULL DEFAULT 'draft',
        scheduled_at TIMESTAMPTZ,
        published_at TIMESTAMPTZ,
        provider_story_id VARCHAR(255),
        metrics_json TEXT NOT NULL DEFAULT '{}',
        created_by VARCHAR(200),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_stories_status ON agente_whatsapp_stories(status)",
    "CREATE INDEX IF NOT EXISTS ix_agente_whatsapp_stories_campaign_id ON agente_whatsapp_stories(campaign_id)",
]


def upgrade() -> None:
    for statement in AGENTE_WHATSAPP_SQL:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agente_whatsapp_stories")
    op.execute("DROP TABLE IF EXISTS agente_whatsapp_campaigns")
    op.execute("DROP TABLE IF EXISTS agente_whatsapp_metrics")
    op.execute("DROP TABLE IF EXISTS agente_whatsapp_context")
    op.execute("DROP TABLE IF EXISTS agente_whatsapp_events")
    op.execute("DROP TABLE IF EXISTS agente_whatsapp_messages")
    op.execute("DROP TABLE IF EXISTS agente_whatsapp_sessions")

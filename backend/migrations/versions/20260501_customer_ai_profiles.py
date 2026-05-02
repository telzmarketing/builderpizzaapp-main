"""customer ai profiles and suggestions

Revision ID: 20260501_customer_ai_profiles
Revises: 20260501_crm_tags_segments
Create Date: 2026-05-01
"""
from __future__ import annotations

from alembic import op

revision = "20260501_customer_ai_profiles"
down_revision = "20260501_crm_tags_segments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_ai_profiles (
            id VARCHAR PRIMARY KEY,
            customer_id VARCHAR NOT NULL UNIQUE REFERENCES customers(id) ON DELETE CASCADE,
            profile_summary TEXT NOT NULL DEFAULT '',
            segment VARCHAR(80) NOT NULL DEFAULT 'lead',
            preferences_json TEXT NOT NULL DEFAULT '{}',
            behavior_json TEXT NOT NULL DEFAULT '{}',
            churn_risk VARCHAR(20) NOT NULL DEFAULT 'low',
            repurchase_probability FLOAT NOT NULL DEFAULT 0,
            average_ticket FLOAT NOT NULL DEFAULT 0,
            best_contact_day VARCHAR(20),
            best_contact_hour VARCHAR(20),
            next_best_action TEXT,
            recommended_offer TEXT,
            recommended_message TEXT,
            analysis_source VARCHAR(40) NOT NULL DEFAULT 'rules',
            model_version VARCHAR(40) NOT NULL DEFAULT 'rules_v1',
            generated_at TIMESTAMPTZ DEFAULT NOW(),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_ai_profiles_customer_id ON customer_ai_profiles(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_ai_profiles_segment ON customer_ai_profiles(segment)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_ai_profiles_churn_risk ON customer_ai_profiles(churn_risk)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_ai_suggestions (
            id VARCHAR PRIMARY KEY,
            customer_id VARCHAR NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            suggestion_type VARCHAR(20) NOT NULL,
            name VARCHAR(160) NOT NULL,
            slug VARCHAR(180) NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            confidence VARCHAR(20) NOT NULL DEFAULT 'medium',
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            target_id VARCHAR,
            source VARCHAR(40) NOT NULL DEFAULT 'rules',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            resolved_at TIMESTAMPTZ,
            CONSTRAINT uq_customer_ai_suggestion_status UNIQUE (customer_id, suggestion_type, slug, status)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_ai_suggestions_customer_id ON customer_ai_suggestions(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_ai_suggestions_status ON customer_ai_suggestions(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_ai_suggestions_type ON customer_ai_suggestions(suggestion_type)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS customer_ai_suggestions")
    op.execute("DROP TABLE IF EXISTS customer_ai_profiles")

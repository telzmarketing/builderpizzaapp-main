"""customer ai analysis jobs

Revision ID: 20260502_customer_ai_analysis_jobs
Revises: 20260501_customer_ai_profiles
Create Date: 2026-05-02
"""
from __future__ import annotations

from alembic import op

revision = "20260502_customer_ai_analysis_jobs"
down_revision = "20260501_customer_ai_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_ai_analysis_jobs (
            id VARCHAR PRIMARY KEY,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            total_customers INTEGER NOT NULL DEFAULT 0,
            processed_customers INTEGER NOT NULL DEFAULT 0,
            failed_customers INTEGER NOT NULL DEFAULT 0,
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            error_message TEXT,
            created_by VARCHAR(200),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_ai_analysis_jobs_status ON customer_ai_analysis_jobs(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_ai_analysis_jobs_created_at ON customer_ai_analysis_jobs(created_at DESC)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS customer_ai_analysis_jobs")

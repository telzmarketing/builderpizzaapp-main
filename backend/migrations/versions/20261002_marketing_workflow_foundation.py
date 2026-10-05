"""Create the legacy marketing workflow tables before tenant isolation.

Revision ID: 20261002_marketing_workflow_foundation
Revises: 20260930_tenant_runtime_uniqueness
"""
from alembic import op
import sqlalchemy as sa


revision = "20261002_marketing_workflow_foundation"
down_revision = "20260930_tenant_runtime_uniqueness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Make the bootstrap-created workflow schema available to Alembic.

    Earlier application startup created these tables imperatively, which meant
    a clean database reached the tenant migration without them.  ``IF NOT
    EXISTS`` preserves installations where that startup bootstrap already ran.
    Tenant ownership is deliberately added by the following migration.
    """
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS marketing_workflows (
            id VARCHAR PRIMARY KEY,
            name VARCHAR(300) NOT NULL,
            campaign_type VARCHAR(50) NOT NULL DEFAULT 'whatsapp',
            status VARCHAR(40) NOT NULL DEFAULT 'draft',
            audience_description TEXT,
            template_preview TEXT,
            scheduled_at TIMESTAMPTZ,
            budget FLOAT,
            created_by VARCHAR(200) NOT NULL DEFAULT 'Admin',
            approved_by VARCHAR(200),
            approved_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS marketing_workflow_comments (
            id VARCHAR PRIMARY KEY,
            workflow_id VARCHAR NOT NULL REFERENCES marketing_workflows(id) ON DELETE CASCADE,
            author VARCHAR(200) NOT NULL DEFAULT 'Admin',
            body TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_marketing_workflows_status "
        "ON marketing_workflows(status)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_marketing_workflow_comments_workflow_id "
        "ON marketing_workflow_comments(workflow_id)"
    ))


def downgrade() -> None:
    # Tables may predate this migration because the historical startup
    # bootstrap created them.  Dropping them would risk deleting business data.
    pass

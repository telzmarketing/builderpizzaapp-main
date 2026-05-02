"""crm tags and segments

Revision ID: 20260501_crm_tags_segments
Revises: 20260501_customer_crm_metrics
Create Date: 2026-05-01
"""
from __future__ import annotations

from alembic import op

revision = "20260501_crm_tags_segments"
down_revision = "20260501_customer_crm_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_tags (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(100) NOT NULL DEFAULT 'default',
            name VARCHAR(120) NOT NULL,
            slug VARCHAR(140) NOT NULL,
            description TEXT,
            color VARCHAR(20) NOT NULL DEFAULT '#f97316',
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            source VARCHAR(40) NOT NULL DEFAULT 'manual',
            created_by VARCHAR(200),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_customer_tags_tenant_slug UNIQUE (tenant_id, slug)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_tags_status ON customer_tags(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_tags_source ON customer_tags(source)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_tag_assignments (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(100) NOT NULL DEFAULT 'default',
            customer_id VARCHAR NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
            tag_id VARCHAR NOT NULL REFERENCES customer_tags(id) ON DELETE CASCADE,
            source VARCHAR(40) NOT NULL DEFAULT 'manual',
            created_by VARCHAR(200),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_customer_tag_assignment UNIQUE (tenant_id, customer_id, tag_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_tag_assignments_customer_id ON customer_tag_assignments(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_tag_assignments_tag_id ON customer_tag_assignments(tag_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_segments (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR(100) NOT NULL DEFAULT 'default',
            name VARCHAR(160) NOT NULL,
            slug VARCHAR(180) NOT NULL,
            description TEXT,
            rules_json TEXT NOT NULL DEFAULT '[]',
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            source VARCHAR(40) NOT NULL DEFAULT 'manual',
            created_by VARCHAR(200),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_customer_segments_tenant_slug UNIQUE (tenant_id, slug)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_segments_status ON customer_segments(status)")

    op.execute("ALTER TABLE customer_groups ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(100) NOT NULL DEFAULT 'default'")
    op.execute("ALTER TABLE customer_groups ADD COLUMN IF NOT EXISTS slug VARCHAR(220)")
    op.execute("ALTER TABLE customer_groups ADD COLUMN IF NOT EXISTS source VARCHAR(40) NOT NULL DEFAULT 'manual'")
    op.execute("ALTER TABLE customer_groups ADD COLUMN IF NOT EXISTS created_by VARCHAR(200)")
    op.execute(
        """
        UPDATE customer_groups
        SET slug = LOWER(REGEXP_REPLACE(REGEXP_REPLACE(name || '-' || LEFT(id, 8), '[^a-zA-Z0-9]+', '-', 'g'), '(^-|-$)', '', 'g'))
        WHERE slug IS NULL OR slug = ''
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_groups_tenant_slug ON customer_groups(tenant_id, slug) WHERE slug IS NOT NULL")

    op.execute("ALTER TABLE customer_group_members ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(100) NOT NULL DEFAULT 'default'")
    op.execute("ALTER TABLE customer_group_members ADD COLUMN IF NOT EXISTS source VARCHAR(40) NOT NULL DEFAULT 'manual'")
    op.execute("ALTER TABLE customer_group_members ADD COLUMN IF NOT EXISTS created_by VARCHAR(200)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_customer_groups_tenant_slug")
    op.execute("ALTER TABLE customer_group_members DROP COLUMN IF EXISTS created_by")
    op.execute("ALTER TABLE customer_group_members DROP COLUMN IF EXISTS source")
    op.execute("ALTER TABLE customer_group_members DROP COLUMN IF EXISTS tenant_id")
    op.execute("ALTER TABLE customer_groups DROP COLUMN IF EXISTS created_by")
    op.execute("ALTER TABLE customer_groups DROP COLUMN IF EXISTS source")
    op.execute("ALTER TABLE customer_groups DROP COLUMN IF EXISTS slug")
    op.execute("ALTER TABLE customer_groups DROP COLUMN IF EXISTS tenant_id")
    op.execute("DROP TABLE IF EXISTS customer_segments")
    op.execute("DROP TABLE IF EXISTS customer_tag_assignments")
    op.execute("DROP TABLE IF EXISTS customer_tags")

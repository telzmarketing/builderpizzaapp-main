"""business intelligence derived analytics

Revision ID: 20260503_business_intelligence
Revises: 20260502_marketing_automation_queue
Create Date: 2026-05-03
"""
from __future__ import annotations

from alembic import op

revision = "20260503_business_intelligence"
down_revision = "20260502_marketing_automation_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS business_insights (
            id VARCHAR PRIMARY KEY,
            dedupe_key VARCHAR(300) NOT NULL,
            insight_type VARCHAR(40) NOT NULL,
            title VARCHAR(300) NOT NULL,
            description TEXT NOT NULL,
            impact_level VARCHAR(20) NOT NULL DEFAULT 'medium',
            recommendation TEXT NOT NULL,
            actionable BOOLEAN NOT NULL DEFAULT TRUE,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            period VARCHAR(30) NOT NULL DEFAULT '30d',
            date_from DATE,
            date_to DATE,
            source VARCHAR(40) NOT NULL DEFAULT 'rules',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_by VARCHAR(200),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            resolved_at TIMESTAMPTZ,
            CONSTRAINT uq_business_insights_dedupe_key UNIQUE (dedupe_key)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_business_insights_period ON business_insights(period, date_from, date_to)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_business_insights_status_created ON business_insights(status, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_business_insights_type_impact ON business_insights(insight_type, impact_level)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS product_performance (
            id VARCHAR PRIMARY KEY,
            metric_date DATE NOT NULL,
            product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL,
            product_name_snapshot VARCHAR(200) NOT NULL,
            category_snapshot VARCHAR(100),
            total_orders INTEGER NOT NULL DEFAULT 0,
            quantity_sold INTEGER NOT NULL DEFAULT 0,
            total_revenue FLOAT NOT NULL DEFAULT 0,
            margin_estimate FLOAT,
            is_top_20_percent BOOLEAN NOT NULL DEFAULT FALSE,
            last_updated TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT uq_product_performance_date_product UNIQUE (metric_date, product_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_product_performance_metric_date ON product_performance(metric_date DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_product_performance_product ON product_performance(product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_product_performance_top20 ON product_performance(metric_date DESC, is_top_20_percent)")

    op.execute("ALTER TABLE customer_segments ADD COLUMN IF NOT EXISTS segment_type VARCHAR(40)")
    op.execute("ALTER TABLE customer_segments ADD COLUMN IF NOT EXISTS refresh_mode VARCHAR(30) NOT NULL DEFAULT 'manual'")
    op.execute("ALTER TABLE customer_segments ADD COLUMN IF NOT EXISTS last_computed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE customer_segments ADD COLUMN IF NOT EXISTS member_count INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE customer_segments ADD COLUMN IF NOT EXISTS definition_version INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE customer_segments ADD COLUMN IF NOT EXISTS metric_snapshot_json TEXT NOT NULL DEFAULT '{}'")
    op.execute("CREATE INDEX IF NOT EXISTS ix_customer_segments_type_status ON customer_segments(segment_type, status)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_customer_segments_type_status")
    op.execute("ALTER TABLE customer_segments DROP COLUMN IF EXISTS metric_snapshot_json")
    op.execute("ALTER TABLE customer_segments DROP COLUMN IF EXISTS definition_version")
    op.execute("ALTER TABLE customer_segments DROP COLUMN IF EXISTS member_count")
    op.execute("ALTER TABLE customer_segments DROP COLUMN IF EXISTS last_computed_at")
    op.execute("ALTER TABLE customer_segments DROP COLUMN IF EXISTS refresh_mode")
    op.execute("ALTER TABLE customer_segments DROP COLUMN IF EXISTS segment_type")
    op.execute("DROP TABLE IF EXISTS product_performance")
    op.execute("DROP TABLE IF EXISTS business_insights")

"""marketing intelligence goals and timeline

Revision ID: 20260613_marketing_intelligence_goals_timeline
Revises: 20260610_delivery_radius_and_payment_retry, 20260512_ads_pixel_event_defaults
"""
from __future__ import annotations

from alembic import op

revision = "20260613_marketing_intelligence_goals_timeline"
down_revision = ("20260610_delivery_radius_and_payment_retry", "20260512_ads_pixel_event_defaults")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS marketing_goals (
            id VARCHAR PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            metric_key VARCHAR(40) NOT NULL,
            target_value FLOAT NOT NULL,
            baseline_value FLOAT,
            comparison_direction VARCHAR(20) NOT NULL DEFAULT 'increase',
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            priority VARCHAR(20) NOT NULL DEFAULT 'medium',
            campaign_id VARCHAR REFERENCES campaigns(id) ON DELETE SET NULL,
            traffic_campaign_id VARCHAR REFERENCES traffic_campaigns(id) ON DELETE SET NULL,
            coupon_id VARCHAR REFERENCES coupons(id) ON DELETE SET NULL,
            promotion_id VARCHAR REFERENCES product_promotions(id) ON DELETE SET NULL,
            product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL,
            channel VARCHAR(100),
            notes TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_by VARCHAR REFERENCES admin_users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_goals_status ON marketing_goals(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_goals_metric_key ON marketing_goals(metric_key)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_goals_period ON marketing_goals(period_start, period_end)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_goals_campaign_id ON marketing_goals(campaign_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_goals_traffic_campaign_id ON marketing_goals(traffic_campaign_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_goals_coupon_id ON marketing_goals(coupon_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_goals_promotion_id ON marketing_goals(promotion_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_goals_product_id ON marketing_goals(product_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_goals_channel ON marketing_goals(channel)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS marketing_timeline_events (
            id VARCHAR PRIMARY KEY,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            event_type VARCHAR(60) NOT NULL,
            event_date TIMESTAMPTZ NOT NULL,
            impact_level VARCHAR(20) NOT NULL DEFAULT 'medium',
            category VARCHAR(60),
            tags TEXT NOT NULL DEFAULT '[]',
            attachment_url TEXT,
            attachment_type VARCHAR(20),
            goal_id VARCHAR REFERENCES marketing_goals(id) ON DELETE SET NULL,
            campaign_id VARCHAR REFERENCES campaigns(id) ON DELETE SET NULL,
            traffic_campaign_id VARCHAR REFERENCES traffic_campaigns(id) ON DELETE SET NULL,
            coupon_id VARCHAR REFERENCES coupons(id) ON DELETE SET NULL,
            promotion_id VARCHAR REFERENCES product_promotions(id) ON DELETE SET NULL,
            product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_by VARCHAR REFERENCES admin_users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_timeline_events_date ON marketing_timeline_events(event_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_timeline_events_type ON marketing_timeline_events(event_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_timeline_events_category ON marketing_timeline_events(category)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_timeline_events_impact ON marketing_timeline_events(impact_level)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_timeline_events_goal_id ON marketing_timeline_events(goal_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_timeline_events_campaign_id ON marketing_timeline_events(campaign_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_timeline_events_traffic_campaign_id ON marketing_timeline_events(traffic_campaign_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_timeline_events_coupon_id ON marketing_timeline_events(coupon_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_timeline_events_promotion_id ON marketing_timeline_events(promotion_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marketing_timeline_events_product_id ON marketing_timeline_events(product_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS marketing_timeline_events")
    op.execute("DROP TABLE IF EXISTS marketing_goals")

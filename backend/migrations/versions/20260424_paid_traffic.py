"""paid traffic tracking module

Revision ID: 20260424_paid_traffic
Revises: 20260424_product_categories
Create Date: 2026-04-24
"""

from alembic import op

revision = "20260424_paid_traffic"
down_revision = "20260424_product_categories"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE IF NOT EXISTS traffic_campaigns (
      id VARCHAR PRIMARY KEY,
      name VARCHAR(200) NOT NULL,
      platform VARCHAR(30) NOT NULL DEFAULT 'manual',
      status VARCHAR(30) NOT NULL DEFAULT 'draft',
      daily_budget FLOAT,
      total_budget FLOAT,
      start_date DATE,
      end_date DATE,
      product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL,
      coupon_id VARCHAR REFERENCES coupons(id) ON DELETE SET NULL,
      destination_url TEXT,
      notes TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW(),
      updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_traffic_campaigns_platform_status ON traffic_campaigns(platform, status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_traffic_campaigns_product_id ON traffic_campaigns(product_id)")

    op.execute("""
    CREATE TABLE IF NOT EXISTS campaign_links (
      id VARCHAR PRIMARY KEY,
      campaign_id VARCHAR NOT NULL REFERENCES traffic_campaigns(id) ON DELETE CASCADE,
      name VARCHAR(200),
      destination_url TEXT NOT NULL,
      final_url TEXT NOT NULL,
      utm_source VARCHAR(100),
      utm_medium VARCHAR(100),
      utm_campaign VARCHAR(200),
      utm_content VARCHAR(200),
      utm_term VARCHAR(200),
      active BOOLEAN DEFAULT TRUE,
      created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_campaign_links_campaign_id ON campaign_links(campaign_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_campaign_links_utm_campaign ON campaign_links(utm_campaign)")

    op.execute("""
    CREATE TABLE IF NOT EXISTS tracking_sessions (
      id VARCHAR PRIMARY KEY,
      campaign_id VARCHAR REFERENCES traffic_campaigns(id) ON DELETE SET NULL,
      utm_source VARCHAR(100),
      utm_medium VARCHAR(100),
      utm_campaign VARCHAR(200),
      utm_content VARCHAR(200),
      utm_term VARCHAR(200),
      landing_page TEXT,
      referrer TEXT,
      first_seen_at TIMESTAMPTZ DEFAULT NOW(),
      last_seen_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_tracking_sessions_campaign_id ON tracking_sessions(campaign_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tracking_sessions_utm_campaign ON tracking_sessions(utm_campaign)")

    op.execute("""
    CREATE TABLE IF NOT EXISTS tracking_events (
      id VARCHAR PRIMARY KEY,
      session_id VARCHAR REFERENCES tracking_sessions(id) ON DELETE SET NULL,
      campaign_id VARCHAR REFERENCES traffic_campaigns(id) ON DELETE SET NULL,
      event_type VARCHAR(60) NOT NULL,
      value FLOAT,
      path TEXT,
      utm_source VARCHAR(100),
      utm_medium VARCHAR(100),
      utm_campaign VARCHAR(200),
      utm_content VARCHAR(200),
      utm_term VARCHAR(200),
      raw_payload TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_tracking_events_session_id ON tracking_events(session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tracking_events_campaign_id ON tracking_events(campaign_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tracking_events_type_created ON tracking_events(event_type, created_at)")

    op.execute("""
    CREATE TABLE IF NOT EXISTS ad_platform_integrations (
      id VARCHAR PRIMARY KEY,
      platform VARCHAR(30) NOT NULL UNIQUE,
      status VARCHAR(30) NOT NULL DEFAULT 'disconnected',
      access_token_encrypted TEXT,
      refresh_token_encrypted TEXT,
      token_expires_at TIMESTAMPTZ,
      account_name VARCHAR(200),
      last_sync_at TIMESTAMPTZ,
      last_error TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW(),
      updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("""
    CREATE TABLE IF NOT EXISTS ad_accounts (
      id VARCHAR PRIMARY KEY,
      integration_id VARCHAR NOT NULL REFERENCES ad_platform_integrations(id) ON DELETE CASCADE,
      platform VARCHAR(30) NOT NULL,
      external_account_id VARCHAR(200) NOT NULL,
      name VARCHAR(200) NOT NULL,
      currency VARCHAR(10),
      active BOOLEAN DEFAULT TRUE,
      created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("""
    CREATE TABLE IF NOT EXISTS ad_campaigns_external (
      id VARCHAR PRIMARY KEY,
      traffic_campaign_id VARCHAR REFERENCES traffic_campaigns(id) ON DELETE SET NULL,
      ad_account_id VARCHAR REFERENCES ad_accounts(id) ON DELETE SET NULL,
      platform VARCHAR(30) NOT NULL,
      external_campaign_id VARCHAR(200) NOT NULL,
      name VARCHAR(300) NOT NULL,
      status VARCHAR(60),
      raw_payload TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW(),
      updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("""
    CREATE TABLE IF NOT EXISTS ad_daily_metrics (
      id VARCHAR PRIMARY KEY,
      traffic_campaign_id VARCHAR REFERENCES traffic_campaigns(id) ON DELETE SET NULL,
      platform VARCHAR(30) NOT NULL,
      metric_date DATE NOT NULL,
      spend FLOAT DEFAULT 0,
      impressions INTEGER DEFAULT 0,
      clicks INTEGER DEFAULT 0,
      conversions FLOAT DEFAULT 0,
      cpc FLOAT DEFAULT 0,
      ctr FLOAT DEFAULT 0,
      roas FLOAT,
      raw_payload TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ad_daily_metrics_campaign_date ON ad_daily_metrics(traffic_campaign_id, metric_date)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ad_daily_metrics_platform_date ON ad_daily_metrics(platform, metric_date)")
    op.execute("""
    CREATE TABLE IF NOT EXISTS campaign_settings (
      id VARCHAR PRIMARY KEY DEFAULT 'default',
      attribution_window_days INTEGER DEFAULT 7,
      attribution_model VARCHAR(30) DEFAULT 'last_click',
      default_margin FLOAT DEFAULT 0.3,
      target_roas FLOAT DEFAULT 2.0,
      tracking_enabled BOOLEAN DEFAULT TRUE,
      updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("INSERT INTO campaign_settings (id) VALUES ('default') ON CONFLICT DO NOTHING")
    op.execute("""
    CREATE TABLE IF NOT EXISTS ad_sync_logs (
      id VARCHAR PRIMARY KEY,
      platform VARCHAR(30) NOT NULL,
      status VARCHAR(30) NOT NULL,
      message TEXT,
      started_at TIMESTAMPTZ DEFAULT NOW(),
      finished_at TIMESTAMPTZ
    )
    """)

    for col in ["campaign_id VARCHAR REFERENCES traffic_campaigns(id) ON DELETE SET NULL", "utm_source VARCHAR(100)", "utm_medium VARCHAR(100)", "utm_campaign VARCHAR(200)", "utm_content VARCHAR(200)", "utm_term VARCHAR(200)", "session_id VARCHAR(120)", "landing_page TEXT", "referrer TEXT"]:
        op.execute(f"ALTER TABLE orders ADD COLUMN IF NOT EXISTS {col}")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_campaign_id ON orders(campaign_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_session_id ON orders(session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_orders_utm_campaign ON orders(utm_campaign)")


def downgrade():
    for col in ["campaign_id", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "session_id", "landing_page", "referrer"]:
        op.execute(f"ALTER TABLE orders DROP COLUMN IF EXISTS {col}")
    for table in [
        "ad_sync_logs", "campaign_settings", "ad_daily_metrics", "ad_campaigns_external",
        "ad_accounts", "ad_platform_integrations", "tracking_events", "tracking_sessions",
        "campaign_links", "traffic_campaigns",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

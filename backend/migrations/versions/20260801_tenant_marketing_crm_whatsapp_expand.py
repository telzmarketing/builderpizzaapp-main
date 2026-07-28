"""Expand tenant ownership for marketing, CRM, WhatsApp, traffic and BI.

Revision ID: 20260801_tenant_marketing_crm_whatsapp_expand
Revises: 20260731_tenant_operations_backfill
"""
from hashlib import sha1

from alembic import op
import sqlalchemy as sa


revision = "20260801_tenant_marketing_crm_whatsapp_expand"
down_revision = "20260731_tenant_operations_backfill"
branch_labels = None
depends_on = None


NEW_TENANT_COLUMNS = (
    # CRM models and route-local ORM.
    "customer_ai_profiles", "customer_ai_suggestions", "customer_ai_analysis_jobs",
    "crm_pipelines", "crm_stages", "crm_cards", "crm_tasks", "customer_groups",
    "customer_timeline", "crm_card_notes", "crm_card_history",
    # Marketing, automation, e-mail and WhatsApp marketing route-local ORM.
    "marketing_campaigns", "visitor_profiles", "visitor_sessions", "visitor_events",
    "tracking_links", "marketing_settings", "integration_connections",
    "marketing_automations", "automation_logs", "automation_templates", "exit_popup_config",
    "email_templates", "email_contact_lists", "email_contact_list_items", "email_messages",
    "email_campaigns", "email_config", "whatsapp_templates", "whatsapp_contact_lists",
    "whatsapp_contact_list_items", "whatsapp_messages", "whatsapp_campaigns", "whatsapp_config",
    # Paid traffic and Ads OAuth route-local ORM.
    "traffic_campaigns", "campaign_creatives", "campaign_links", "tracking_sessions",
    "tracking_events", "ad_platform_integrations", "ad_accounts", "ad_campaigns_external",
    "ad_daily_metrics", "campaign_settings", "ad_sync_logs", "ads_oauth_states",
    "ads_campaigns", "ads_utm_links", "ads_pixels",
    # BI and marketing intelligence.
    "business_insights", "product_performance", "marketing_goals", "marketing_timeline_events",
    # Chatbot and Agente WhatsApp.
    "chatbot_settings", "chatbot_faq", "chatbot_conversations", "chatbot_messages",
    "chatbot_automations", "chatbot_handoffs", "chatbot_knowledge_docs",
    "agente_whatsapp_sessions", "agente_whatsapp_ai_settings",
    "agente_whatsapp_channel_settings", "agente_whatsapp_messages",
    "agente_whatsapp_audio_artifacts", "agente_whatsapp_processing_jobs",
    "agente_whatsapp_outbox", "agente_whatsapp_provider_states",
    "agente_whatsapp_internal_alerts", "agente_whatsapp_events", "agente_whatsapp_context",
    "agente_whatsapp_tool_calls", "agente_whatsapp_metrics", "agente_whatsapp_campaigns",
    "agente_whatsapp_stories",
)

EXISTING_TENANT_COLUMNS = (
    "customer_tags", "customer_tag_assignments", "customer_segments",
    "whatsapp_campaign_deliveries", "whatsapp_gateway_instances", "whatsapp_gateway_logs",
    "whatsapp_gateway_update_logs", "whatsapp_gateway_scheduler_settings",
)

TABLES = NEW_TENANT_COLUMNS + EXISTING_TENANT_COLUMNS

# Existing global uniqueness remains during expand for dual compatibility. These
# indexes establish the final scoped keys without weakening the legacy contract.
SCOPED_UNIQUES = (
    ("uq_mt_customer_ai_profile_customer", "customer_ai_profiles", "tenant_id, customer_id", None),
    ("uq_mt_customer_ai_suggestion_status", "customer_ai_suggestions", "tenant_id, customer_id, suggestion_type, slug, status", None),
    ("uq_mt_visitor_profile_fingerprint", "visitor_profiles", "tenant_id, fingerprint", "fingerprint IS NOT NULL"),
    ("uq_mt_integration_connection_type", "integration_connections", "tenant_id, integration_type", None),
    ("uq_mt_ad_integration_platform", "ad_platform_integrations", "tenant_id, platform", None),
    ("uq_mt_business_insight_dedupe", "business_insights", "tenant_id, dedupe_key", None),
    ("uq_mt_product_performance_date_product", "product_performance", "tenant_id, metric_date, product_id", None),
    ("uq_mt_provider_state_provider", "agente_whatsapp_provider_states", "tenant_id, provider", None),
    ("uq_mt_internal_alert_dedupe", "agente_whatsapp_internal_alerts", "tenant_id, dedupe_key", None),
    ("uq_mt_whatsapp_outbox_message", "agente_whatsapp_outbox", "tenant_id, message_id", None),
    ("uq_mt_whatsapp_context_session", "agente_whatsapp_context", "tenant_id, session_id", None),
    ("uq_mt_chatbot_conversation_session", "chatbot_conversations", "tenant_id, session_id", None),
    ("uq_mt_gateway_instance_name", "whatsapp_gateway_instances", "tenant_id, name", None),
    ("uq_mt_gateway_scheduler_singleton", "whatsapp_gateway_scheduler_settings", "tenant_id", "tenant_id IS NOT NULL"),
    ("uq_mt_campaign_settings_singleton", "campaign_settings", "tenant_id", "tenant_id IS NOT NULL"),
    ("uq_mt_marketing_settings_singleton", "marketing_settings", "tenant_id", "tenant_id IS NOT NULL"),
    ("uq_mt_email_config_singleton", "email_config", "tenant_id", "tenant_id IS NOT NULL"),
    ("uq_mt_whatsapp_config_singleton", "whatsapp_config", "tenant_id", "tenant_id IS NOT NULL"),
    ("uq_mt_exit_popup_singleton", "exit_popup_config", "tenant_id", "tenant_id IS NOT NULL"),
    ("uq_mt_chatbot_settings_singleton", "chatbot_settings", "tenant_id", "tenant_id IS NOT NULL"),
    ("uq_mt_agente_ai_settings_singleton", "agente_whatsapp_ai_settings", "tenant_id", "tenant_id IS NOT NULL"),
    ("uq_mt_agente_channel_settings_singleton", "agente_whatsapp_channel_settings", "tenant_id", "tenant_id IS NOT NULL"),
)

COMPOSITE_FKS = (
    ("customer_tag_assignments", "customer_id", "customers", "CASCADE"),
    ("customer_tag_assignments", "tag_id", "customer_tags", "CASCADE"),
    ("customer_ai_profiles", "customer_id", "customers", "CASCADE"),
    ("customer_ai_suggestions", "customer_id", "customers", "CASCADE"),
    ("crm_stages", "pipeline_id", "crm_pipelines", "CASCADE"),
    ("crm_cards", "pipeline_id", "crm_pipelines", "CASCADE"),
    ("crm_cards", "stage_id", "crm_stages", "CASCADE"),
    ("crm_cards", "customer_id", "customers", "SET NULL"),
    ("crm_tasks", "card_id", "crm_cards", "SET NULL"),
    ("crm_tasks", "customer_id", "customers", "SET NULL"),
    ("customer_timeline", "customer_id", "customers", "CASCADE"),
    ("crm_card_notes", "card_id", "crm_cards", "CASCADE"),
    ("crm_card_history", "card_id", "crm_cards", "CASCADE"),
    ("marketing_campaigns", "product_id", "products", "SET NULL"),
    ("marketing_campaigns", "coupon_id", "coupons", "SET NULL"),
    ("marketing_campaigns", "group_id", "customer_groups", "SET NULL"),
    ("visitor_profiles", "customer_id", "customers", "SET NULL"),
    ("visitor_sessions", "visitor_id", "visitor_profiles", "CASCADE"),
    ("visitor_events", "visitor_id", "visitor_profiles", "CASCADE"),
    ("visitor_events", "session_id", "visitor_sessions", "SET NULL"),
    ("tracking_links", "campaign_id", "marketing_campaigns", "SET NULL"),
    ("tracking_links", "product_id", "products", "SET NULL"),
    ("tracking_links", "coupon_id", "coupons", "SET NULL"),
    ("automation_logs", "automation_id", "marketing_automations", "CASCADE"),
    ("automation_logs", "customer_id", "customers", "SET NULL"),
    ("email_contact_list_items", "list_id", "email_contact_lists", "CASCADE"),
    ("email_messages", "template_id", "email_templates", "SET NULL"),
    ("email_messages", "campaign_id", "email_campaigns", "SET NULL"),
    ("email_messages", "customer_id", "customers", "SET NULL"),
    ("email_campaigns", "template_id", "email_templates", "SET NULL"),
    ("email_campaigns", "contact_list_id", "email_contact_lists", "SET NULL"),
    ("whatsapp_contact_list_items", "list_id", "whatsapp_contact_lists", "CASCADE"),
    ("whatsapp_messages", "template_id", "whatsapp_templates", "SET NULL"),
    ("whatsapp_messages", "campaign_id", "whatsapp_campaigns", "SET NULL"),
    ("whatsapp_messages", "customer_id", "customers", "SET NULL"),
    ("whatsapp_campaign_deliveries", "whatsapp_message_id", "whatsapp_messages", "SET NULL"),
    ("whatsapp_campaign_deliveries", "campaign_id", "whatsapp_campaigns", "SET NULL"),
    ("whatsapp_campaign_deliveries", "template_id", "whatsapp_templates", "SET NULL"),
    ("whatsapp_campaign_deliveries", "customer_id", "customers", "SET NULL"),
    ("whatsapp_campaign_deliveries", "conversation_id", "agente_whatsapp_sessions", "SET NULL"),
    ("whatsapp_campaign_deliveries", "agente_message_id", "agente_whatsapp_messages", "SET NULL"),
    ("whatsapp_campaigns", "template_id", "whatsapp_templates", "SET NULL"),
    ("whatsapp_campaigns", "contact_list_id", "whatsapp_contact_lists", "SET NULL"),
    ("whatsapp_config", "whatsapp_gateway_instance_id", "whatsapp_gateway_instances", "SET NULL"),
    ("traffic_campaigns", "product_id", "products", "SET NULL"),
    ("traffic_campaigns", "coupon_id", "coupons", "SET NULL"),
    ("campaign_creatives", "campaign_id", "traffic_campaigns", "CASCADE"),
    ("campaign_links", "campaign_id", "traffic_campaigns", "CASCADE"),
    ("tracking_sessions", "campaign_id", "traffic_campaigns", "SET NULL"),
    ("tracking_events", "session_id", "tracking_sessions", "SET NULL"),
    ("tracking_events", "campaign_id", "traffic_campaigns", "SET NULL"),
    ("ad_accounts", "integration_id", "ad_platform_integrations", "CASCADE"),
    ("ad_campaigns_external", "traffic_campaign_id", "traffic_campaigns", "SET NULL"),
    ("ad_campaigns_external", "ad_account_id", "ad_accounts", "SET NULL"),
    ("ad_daily_metrics", "traffic_campaign_id", "traffic_campaigns", "SET NULL"),
    ("product_performance", "product_id", "products", "SET NULL"),
    ("marketing_goals", "campaign_id", "campaigns", "SET NULL"),
    ("marketing_goals", "traffic_campaign_id", "traffic_campaigns", "SET NULL"),
    ("marketing_goals", "coupon_id", "coupons", "SET NULL"),
    ("marketing_goals", "promotion_id", "product_promotions", "SET NULL"),
    ("marketing_goals", "product_id", "products", "SET NULL"),
    ("marketing_timeline_events", "goal_id", "marketing_goals", "SET NULL"),
    ("marketing_timeline_events", "campaign_id", "campaigns", "SET NULL"),
    ("marketing_timeline_events", "traffic_campaign_id", "traffic_campaigns", "SET NULL"),
    ("marketing_timeline_events", "coupon_id", "coupons", "SET NULL"),
    ("marketing_timeline_events", "promotion_id", "product_promotions", "SET NULL"),
    ("marketing_timeline_events", "product_id", "products", "SET NULL"),
    ("chatbot_faq", "vinculo_produto_id", "products", "SET NULL"),
    ("chatbot_conversations", "cliente_id", "customers", "SET NULL"),
    ("chatbot_messages", "conversation_id", "chatbot_conversations", "CASCADE"),
    ("chatbot_handoffs", "conversation_id", "chatbot_conversations", "CASCADE"),
    ("agente_whatsapp_sessions", "customer_id", "customers", "SET NULL"),
    ("agente_whatsapp_channel_settings", "whatsapp_gateway_instance_id", "whatsapp_gateway_instances", "SET NULL"),
    ("agente_whatsapp_messages", "session_id", "agente_whatsapp_sessions", "CASCADE"),
    ("agente_whatsapp_messages", "customer_id", "customers", "SET NULL"),
    ("agente_whatsapp_messages", "response_to_message_id", "agente_whatsapp_messages", "SET NULL"),
    ("agente_whatsapp_messages", "campaign_id", "whatsapp_campaigns", "SET NULL"),
    ("agente_whatsapp_messages", "campaign_delivery_id", "whatsapp_campaign_deliveries", "SET NULL"),
    ("agente_whatsapp_audio_artifacts", "message_id", "agente_whatsapp_messages", "CASCADE"),
    ("agente_whatsapp_processing_jobs", "message_id", "agente_whatsapp_messages", "CASCADE"),
    ("agente_whatsapp_processing_jobs", "session_id", "agente_whatsapp_sessions", "CASCADE"),
    ("agente_whatsapp_processing_jobs", "customer_id", "customers", "SET NULL"),
    ("agente_whatsapp_outbox", "message_id", "agente_whatsapp_messages", "CASCADE"),
    ("agente_whatsapp_outbox", "session_id", "agente_whatsapp_sessions", "CASCADE"),
    ("agente_whatsapp_outbox", "customer_id", "customers", "SET NULL"),
    ("agente_whatsapp_events", "session_id", "agente_whatsapp_sessions", "CASCADE"),
    ("agente_whatsapp_events", "customer_id", "customers", "SET NULL"),
    ("agente_whatsapp_events", "order_id", "orders", "SET NULL"),
    ("agente_whatsapp_context", "session_id", "agente_whatsapp_sessions", "CASCADE"),
    ("agente_whatsapp_context", "customer_id", "customers", "SET NULL"),
    ("agente_whatsapp_tool_calls", "session_id", "agente_whatsapp_sessions", "SET NULL"),
    ("agente_whatsapp_tool_calls", "customer_id", "customers", "SET NULL"),
    ("agente_whatsapp_stories", "campaign_id", "agente_whatsapp_campaigns", "SET NULL"),
    ("whatsapp_gateway_logs", "instance_id", "whatsapp_gateway_instances", "SET NULL"),
)


def _name(prefix: str, *parts: str) -> str:
    raw = "_".join((prefix,) + parts)
    return raw if len(raw) <= 63 else f"{raw[:54]}_{sha1(raw.encode()).hexdigest()[:8]}"


def upgrade() -> None:
    legacy_tables = (
        """CREATE TABLE IF NOT EXISTS customer_timeline (id VARCHAR PRIMARY KEY, customer_id VARCHAR NOT NULL REFERENCES customers(id) ON DELETE CASCADE, event_type VARCHAR(80) NOT NULL, title VARCHAR(300) NOT NULL, description TEXT, metadata_json TEXT, created_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS crm_pipelines (id VARCHAR PRIMARY KEY, name VARCHAR(200) NOT NULL, description TEXT, pipeline_type VARCHAR(30) DEFAULT 'custom', active BOOLEAN DEFAULT TRUE, sort_order INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS crm_stages (id VARCHAR PRIMARY KEY, pipeline_id VARCHAR NOT NULL REFERENCES crm_pipelines(id) ON DELETE CASCADE, name VARCHAR(200) NOT NULL, description TEXT, color VARCHAR(20) DEFAULT '#2d3d56', sort_order INTEGER DEFAULT 0, auto_move_rule TEXT, created_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS crm_cards (id VARCHAR PRIMARY KEY, pipeline_id VARCHAR NOT NULL REFERENCES crm_pipelines(id) ON DELETE CASCADE, stage_id VARCHAR NOT NULL REFERENCES crm_stages(id) ON DELETE CASCADE, customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL, title VARCHAR(300) NOT NULL, description TEXT, value FLOAT, source VARCHAR(100), responsible VARCHAR(200), tags TEXT DEFAULT '[]', last_interaction_at TIMESTAMPTZ, next_follow_up_at TIMESTAMPTZ, sort_order INTEGER DEFAULT 0, archived BOOLEAN DEFAULT FALSE, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS crm_tasks (id VARCHAR PRIMARY KEY, card_id VARCHAR REFERENCES crm_cards(id) ON DELETE SET NULL, customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL, title VARCHAR(300) NOT NULL, description TEXT, task_type VARCHAR(50) DEFAULT 'other', responsible VARCHAR(200), due_date TIMESTAMPTZ, priority VARCHAR(20) DEFAULT 'medium', status VARCHAR(20) DEFAULT 'pending', completed_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS crm_card_notes (id VARCHAR PRIMARY KEY, card_id VARCHAR NOT NULL REFERENCES crm_cards(id) ON DELETE CASCADE, author VARCHAR(200) DEFAULT 'Admin', body TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS crm_card_history (id VARCHAR PRIMARY KEY, card_id VARCHAR NOT NULL REFERENCES crm_cards(id) ON DELETE CASCADE, event_type VARCHAR(80) NOT NULL, description TEXT, created_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS marketing_campaigns (id VARCHAR PRIMARY KEY, name VARCHAR(300) NOT NULL, campaign_type VARCHAR(50) NOT NULL, channel VARCHAR(50), status VARCHAR(30) DEFAULT 'draft', product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL, coupon_id VARCHAR REFERENCES coupons(id) ON DELETE SET NULL, group_id VARCHAR REFERENCES customer_groups(id) ON DELETE SET NULL, budget FLOAT, spend FLOAT DEFAULT 0, revenue FLOAT DEFAULT 0, leads INTEGER DEFAULT 0, orders_count INTEGER DEFAULT 0, clicks INTEGER DEFAULT 0, impressions INTEGER DEFAULT 0, start_date DATE, end_date DATE, target_url TEXT, description TEXT, metadata_json TEXT, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS visitor_sessions (id VARCHAR PRIMARY KEY, visitor_id VARCHAR NOT NULL REFERENCES visitor_profiles(id) ON DELETE CASCADE, utm_source VARCHAR(100), utm_medium VARCHAR(100), utm_campaign VARCHAR(200), utm_content VARCHAR(200), utm_term VARCHAR(200), landing_page TEXT, referrer TEXT, started_at TIMESTAMPTZ DEFAULT NOW(), ended_at TIMESTAMPTZ, pageviews INTEGER DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS visitor_events (id VARCHAR PRIMARY KEY, visitor_id VARCHAR NOT NULL REFERENCES visitor_profiles(id) ON DELETE CASCADE, session_id VARCHAR REFERENCES visitor_sessions(id) ON DELETE SET NULL, event_type VARCHAR(80) NOT NULL, page TEXT, product_id VARCHAR, metadata_json TEXT, created_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS tracking_links (id VARCHAR PRIMARY KEY, slug VARCHAR(100) UNIQUE NOT NULL, destination_url TEXT NOT NULL, campaign_id VARCHAR REFERENCES marketing_campaigns(id) ON DELETE SET NULL, product_id VARCHAR REFERENCES products(id) ON DELETE SET NULL, coupon_id VARCHAR REFERENCES coupons(id) ON DELETE SET NULL, utm_source VARCHAR(100), utm_medium VARCHAR(100), utm_campaign VARCHAR(200), clicks INTEGER DEFAULT 0, unique_clicks INTEGER DEFAULT 0, orders_count INTEGER DEFAULT 0, revenue FLOAT DEFAULT 0, active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS marketing_settings (id VARCHAR PRIMARY KEY DEFAULT 'default', tracking_enabled BOOLEAN DEFAULT TRUE, ip_anonymization BOOLEAN DEFAULT TRUE, online_visitor_minutes INTEGER DEFAULT 5, data_retention_days INTEGER DEFAULT 365, attribution_window_days INTEGER DEFAULT 30, default_utm_source VARCHAR(100), default_utm_medium VARCHAR(100), tracking_domain VARCHAR(300), created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS automation_logs (id VARCHAR PRIMARY KEY, automation_id VARCHAR NOT NULL REFERENCES marketing_automations(id) ON DELETE CASCADE, customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL, channel VARCHAR(20), status VARCHAR(20), error TEXT, created_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS automation_templates (id VARCHAR PRIMARY KEY, name VARCHAR(200) NOT NULL, channel VARCHAR(20) NOT NULL DEFAULT 'whatsapp', subject VARCHAR(500), body TEXT NOT NULL, variables VARCHAR(500), category VARCHAR(50) DEFAULT 'marketing', created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS email_templates (id VARCHAR PRIMARY KEY, name VARCHAR(200) NOT NULL, subject VARCHAR(500) NOT NULL, body_html TEXT NOT NULL, active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS email_messages (id VARCHAR PRIMARY KEY, template_id VARCHAR REFERENCES email_templates(id) ON DELETE SET NULL, customer_id VARCHAR REFERENCES customers(id) ON DELETE SET NULL, to_email VARCHAR(300) NOT NULL, subject_sent VARCHAR(500), status VARCHAR(20) DEFAULT 'pending', error TEXT, sent_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW(), campaign_id VARCHAR REFERENCES email_campaigns(id) ON DELETE SET NULL)""",
        """CREATE TABLE IF NOT EXISTS email_config (id VARCHAR PRIMARY KEY DEFAULT 'default', provider VARCHAR(30) DEFAULT 'smtp', smtp_host VARCHAR(200) DEFAULT '', smtp_port INTEGER DEFAULT 587, smtp_user VARCHAR(300) DEFAULT '', smtp_password VARCHAR(500) DEFAULT '', from_name VARCHAR(200) DEFAULT 'Moschettieri', from_email VARCHAR(300) DEFAULT '', reply_to VARCHAR(300) DEFAULT '', status VARCHAR(20) DEFAULT 'disconnected', daily_limit INTEGER DEFAULT 5000, rate_per_hour INTEGER DEFAULT 500, updated_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS campaign_creatives (id VARCHAR PRIMARY KEY, campaign_id VARCHAR NOT NULL REFERENCES traffic_campaigns(id) ON DELETE CASCADE, name VARCHAR(300), media_url TEXT NOT NULL, creative_type VARCHAR(20) NOT NULL DEFAULT 'image', created_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS ads_oauth_states (id VARCHAR PRIMARY KEY, platform VARCHAR(30) NOT NULL, redirect_uri TEXT, created_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS ads_campaigns (id VARCHAR PRIMARY KEY, platform VARCHAR(30) NOT NULL, external_id VARCHAR(200) NOT NULL, name VARCHAR(300), status VARCHAR(30), objective VARCHAR(100), budget_daily FLOAT, spend FLOAT DEFAULT 0, impressions INTEGER DEFAULT 0, clicks INTEGER DEFAULT 0, conversions INTEGER DEFAULT 0, revenue FLOAT DEFAULT 0, ctr FLOAT DEFAULT 0, cpc FLOAT DEFAULT 0, cpa FLOAT DEFAULT 0, roas FLOAT DEFAULT 0, last_synced_at TIMESTAMPTZ, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS ads_utm_links (id VARCHAR PRIMARY KEY, name VARCHAR(300) NOT NULL, url TEXT NOT NULL, utm_source VARCHAR(100) DEFAULT '', utm_medium VARCHAR(100) DEFAULT '', utm_campaign VARCHAR(200) DEFAULT '', utm_term VARCHAR(200) DEFAULT '', utm_content VARCHAR(200) DEFAULT '', clicks INTEGER DEFAULT 0, conversions INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT NOW())""",
    )
    for statement in legacy_tables:
        op.execute(statement)

    for table in NEW_TENANT_COLUMNS:
        op.execute(sa.text(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS tenant_id VARCHAR"
        ))

    for table in EXISTING_TENANT_COLUMNS:
        op.alter_column(table, "tenant_id", existing_type=sa.String(), nullable=True, server_default=None)

    for table in TABLES:
        op.execute(sa.text(
            f"ALTER TABLE {table} ADD CONSTRAINT {_name('fk', table, 'tenant')} "
            "FOREIGN KEY (tenant_id) REFERENCES tenants(id) NOT VALID"
        ))
        op.create_index(_name("uq", table, "tenant_id_id"), table, ["tenant_id", "id"], unique=True)

    for name, table, columns, predicate in SCOPED_UNIQUES:
        where = f" WHERE {predicate}" if predicate else ""
        op.execute(sa.text(f"CREATE UNIQUE INDEX {name} ON {table} ({columns}){where}"))

    for table, column, parent, ondelete in COMPOSITE_FKS:
        # A composite ON DELETE SET NULL would also clear tenant_id. Keep the
        # existing scalar FK responsible for SET NULL and make the ownership FK
        # NO ACTION; CASCADE remains safe because the whole child row is deleted.
        delete = f" ON DELETE {ondelete}" if ondelete == "CASCADE" else ""
        op.execute(sa.text(
            f"ALTER TABLE {table} ADD CONSTRAINT {_name('fkmt', table, column)} "
            f"FOREIGN KEY (tenant_id, {column}) REFERENCES {parent} (tenant_id, id)"
            f"{delete} NOT VALID"
        ))


def downgrade() -> None:
    for table, column, _parent, _ondelete in reversed(COMPOSITE_FKS):
        op.drop_constraint(_name("fkmt", table, column), table, type_="foreignkey")
    for name, table, _columns, _predicate in reversed(SCOPED_UNIQUES):
        op.drop_index(name, table_name=table)
    for table in reversed(TABLES):
        op.drop_index(_name("uq", table, "tenant_id_id"), table_name=table)
        op.drop_constraint(_name("fk", table, "tenant"), table, type_="foreignkey")
    for table in reversed(NEW_TENANT_COLUMNS):
        op.drop_column(table, "tenant_id")

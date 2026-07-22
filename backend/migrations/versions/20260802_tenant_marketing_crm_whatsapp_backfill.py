"""Backfill legacy tenant ownership for marketing, CRM, WhatsApp, traffic and BI."""
from alembic import op
import sqlalchemy as sa


revision = "20260802_tenant_marketing_crm_whatsapp_backfill"
down_revision = "20260801_tenant_marketing_crm_whatsapp_expand"
branch_labels = None
depends_on = None

LEGACY_TENANT_ID = "tenant-legacy-default"

TABLES = (
    "customer_tags", "customer_tag_assignments", "customer_segments",
    "customer_ai_profiles", "customer_ai_suggestions", "customer_ai_analysis_jobs",
    "crm_pipelines", "crm_stages", "crm_cards", "crm_tasks", "customer_groups",
    "customer_timeline", "crm_card_notes", "crm_card_history",
    "marketing_campaigns", "visitor_profiles", "visitor_sessions", "visitor_events",
    "tracking_links", "marketing_settings", "integration_connections",
    "marketing_automations", "automation_logs", "automation_templates", "exit_popup_config",
    "email_templates", "email_contact_lists", "email_contact_list_items", "email_messages",
    "email_campaigns", "email_config", "whatsapp_templates", "whatsapp_contact_lists",
    "whatsapp_contact_list_items", "whatsapp_messages", "whatsapp_campaign_deliveries",
    "whatsapp_campaigns", "whatsapp_config", "traffic_campaigns", "campaign_creatives",
    "campaign_links", "tracking_sessions", "tracking_events", "ad_platform_integrations",
    "ad_accounts", "ad_campaigns_external", "ad_daily_metrics", "campaign_settings",
    "ad_sync_logs", "ads_oauth_states", "ads_campaigns", "ads_utm_links", "ads_pixels",
    "business_insights", "product_performance", "marketing_goals", "marketing_timeline_events",
    "chatbot_settings", "chatbot_faq", "chatbot_conversations", "chatbot_messages",
    "chatbot_automations", "chatbot_handoffs", "chatbot_knowledge_docs",
    "agente_whatsapp_sessions", "agente_whatsapp_ai_settings",
    "agente_whatsapp_channel_settings", "agente_whatsapp_messages",
    "agente_whatsapp_audio_artifacts", "agente_whatsapp_processing_jobs",
    "agente_whatsapp_outbox", "agente_whatsapp_provider_states",
    "agente_whatsapp_internal_alerts", "agente_whatsapp_events", "agente_whatsapp_context",
    "agente_whatsapp_tool_calls", "agente_whatsapp_metrics", "agente_whatsapp_campaigns",
    "agente_whatsapp_stories", "whatsapp_gateway_instances", "whatsapp_gateway_logs",
    "whatsapp_gateway_update_logs", "whatsapp_gateway_scheduler_settings",
)

UNIQUE_PREFLIGHTS = (
    ("customer_tags", "slug", "slug IS NOT NULL"),
    ("customer_tag_assignments", "customer_id, tag_id", "customer_id IS NOT NULL AND tag_id IS NOT NULL"),
    ("customer_segments", "slug", "slug IS NOT NULL"),
    ("customer_ai_profiles", "customer_id", "customer_id IS NOT NULL"),
    ("customer_ai_suggestions", "customer_id, suggestion_type, slug, status", "customer_id IS NOT NULL AND suggestion_type IS NOT NULL AND slug IS NOT NULL AND status IS NOT NULL"),
    ("visitor_profiles", "fingerprint", "fingerprint IS NOT NULL"),
    ("integration_connections", "integration_type", "integration_type IS NOT NULL"),
    ("ad_platform_integrations", "platform", "platform IS NOT NULL"),
    ("business_insights", "dedupe_key", "dedupe_key IS NOT NULL"),
    ("product_performance", "metric_date, product_id", "metric_date IS NOT NULL AND product_id IS NOT NULL"),
    ("agente_whatsapp_provider_states", "provider", "provider IS NOT NULL"),
    ("agente_whatsapp_internal_alerts", "dedupe_key", "dedupe_key IS NOT NULL"),
    ("agente_whatsapp_outbox", "message_id", "message_id IS NOT NULL"),
    ("agente_whatsapp_context", "session_id", "session_id IS NOT NULL"),
    ("chatbot_conversations", "session_id", "session_id IS NOT NULL"),
    ("whatsapp_gateway_instances", "name", "name IS NOT NULL"),
)

SINGLETON_PREFLIGHTS = (
    "campaign_settings", "marketing_settings", "email_config", "whatsapp_config",
    "exit_popup_config", "whatsapp_gateway_scheduler_settings",
    "chatbot_settings", "agente_whatsapp_ai_settings", "agente_whatsapp_channel_settings",
)

OWNERSHIP_PREFLIGHTS = (
    ("customer_tag_assignments", "customer_id", "customers"),
    ("customer_tag_assignments", "tag_id", "customer_tags"),
    ("customer_ai_profiles", "customer_id", "customers"),
    ("customer_ai_suggestions", "customer_id", "customers"),
    ("crm_stages", "pipeline_id", "crm_pipelines"),
    ("crm_cards", "pipeline_id", "crm_pipelines"), ("crm_cards", "stage_id", "crm_stages"),
    ("crm_cards", "customer_id", "customers"), ("crm_tasks", "card_id", "crm_cards"),
    ("crm_tasks", "customer_id", "customers"), ("customer_timeline", "customer_id", "customers"),
    ("crm_card_notes", "card_id", "crm_cards"), ("crm_card_history", "card_id", "crm_cards"),
    ("marketing_campaigns", "product_id", "products"), ("marketing_campaigns", "coupon_id", "coupons"),
    ("marketing_campaigns", "group_id", "customer_groups"), ("visitor_profiles", "customer_id", "customers"),
    ("visitor_sessions", "visitor_id", "visitor_profiles"), ("visitor_events", "visitor_id", "visitor_profiles"),
    ("visitor_events", "session_id", "visitor_sessions"), ("tracking_links", "campaign_id", "marketing_campaigns"),
    ("tracking_links", "product_id", "products"), ("tracking_links", "coupon_id", "coupons"),
    ("automation_logs", "automation_id", "marketing_automations"), ("automation_logs", "customer_id", "customers"),
    ("email_contact_list_items", "list_id", "email_contact_lists"),
    ("email_messages", "template_id", "email_templates"), ("email_messages", "campaign_id", "email_campaigns"),
    ("email_messages", "customer_id", "customers"), ("email_campaigns", "template_id", "email_templates"),
    ("email_campaigns", "contact_list_id", "email_contact_lists"),
    ("whatsapp_contact_list_items", "list_id", "whatsapp_contact_lists"),
    ("whatsapp_messages", "template_id", "whatsapp_templates"),
    ("whatsapp_messages", "campaign_id", "whatsapp_campaigns"), ("whatsapp_messages", "customer_id", "customers"),
    ("whatsapp_campaign_deliveries", "whatsapp_message_id", "whatsapp_messages"),
    ("whatsapp_campaign_deliveries", "campaign_id", "whatsapp_campaigns"),
    ("whatsapp_campaign_deliveries", "template_id", "whatsapp_templates"),
    ("whatsapp_campaign_deliveries", "customer_id", "customers"),
    ("whatsapp_campaign_deliveries", "conversation_id", "agente_whatsapp_sessions"),
    ("whatsapp_campaign_deliveries", "agente_message_id", "agente_whatsapp_messages"),
    ("whatsapp_campaigns", "template_id", "whatsapp_templates"),
    ("whatsapp_campaigns", "contact_list_id", "whatsapp_contact_lists"),
    ("whatsapp_config", "whatsapp_gateway_instance_id", "whatsapp_gateway_instances"),
    ("traffic_campaigns", "product_id", "products"), ("traffic_campaigns", "coupon_id", "coupons"),
    ("campaign_creatives", "campaign_id", "traffic_campaigns"),
    ("campaign_links", "campaign_id", "traffic_campaigns"),
    ("tracking_sessions", "campaign_id", "traffic_campaigns"),
    ("tracking_events", "session_id", "tracking_sessions"), ("tracking_events", "campaign_id", "traffic_campaigns"),
    ("ad_accounts", "integration_id", "ad_platform_integrations"),
    ("ad_campaigns_external", "traffic_campaign_id", "traffic_campaigns"),
    ("ad_campaigns_external", "ad_account_id", "ad_accounts"),
    ("ad_daily_metrics", "traffic_campaign_id", "traffic_campaigns"),
    ("product_performance", "product_id", "products"),
    ("marketing_goals", "campaign_id", "campaigns"), ("marketing_goals", "traffic_campaign_id", "traffic_campaigns"),
    ("marketing_goals", "coupon_id", "coupons"), ("marketing_goals", "promotion_id", "product_promotions"),
    ("marketing_goals", "product_id", "products"),
    ("marketing_timeline_events", "goal_id", "marketing_goals"),
    ("marketing_timeline_events", "campaign_id", "campaigns"),
    ("marketing_timeline_events", "traffic_campaign_id", "traffic_campaigns"),
    ("marketing_timeline_events", "coupon_id", "coupons"),
    ("marketing_timeline_events", "promotion_id", "product_promotions"),
    ("marketing_timeline_events", "product_id", "products"),
    ("chatbot_faq", "vinculo_produto_id", "products"),
    ("chatbot_conversations", "cliente_id", "customers"),
    ("chatbot_messages", "conversation_id", "chatbot_conversations"),
    ("chatbot_handoffs", "conversation_id", "chatbot_conversations"),
    ("agente_whatsapp_sessions", "customer_id", "customers"),
    ("agente_whatsapp_channel_settings", "whatsapp_gateway_instance_id", "whatsapp_gateway_instances"),
    ("agente_whatsapp_messages", "session_id", "agente_whatsapp_sessions"),
    ("agente_whatsapp_messages", "customer_id", "customers"),
    ("agente_whatsapp_messages", "response_to_message_id", "agente_whatsapp_messages"),
    ("agente_whatsapp_messages", "campaign_id", "whatsapp_campaigns"),
    ("agente_whatsapp_messages", "campaign_delivery_id", "whatsapp_campaign_deliveries"),
    ("agente_whatsapp_audio_artifacts", "message_id", "agente_whatsapp_messages"),
    ("agente_whatsapp_processing_jobs", "message_id", "agente_whatsapp_messages"),
    ("agente_whatsapp_processing_jobs", "session_id", "agente_whatsapp_sessions"),
    ("agente_whatsapp_processing_jobs", "customer_id", "customers"),
    ("agente_whatsapp_outbox", "message_id", "agente_whatsapp_messages"),
    ("agente_whatsapp_outbox", "session_id", "agente_whatsapp_sessions"),
    ("agente_whatsapp_outbox", "customer_id", "customers"),
    ("agente_whatsapp_events", "session_id", "agente_whatsapp_sessions"),
    ("agente_whatsapp_events", "customer_id", "customers"), ("agente_whatsapp_events", "order_id", "orders"),
    ("agente_whatsapp_context", "session_id", "agente_whatsapp_sessions"),
    ("agente_whatsapp_context", "customer_id", "customers"),
    ("agente_whatsapp_tool_calls", "session_id", "agente_whatsapp_sessions"),
    ("agente_whatsapp_tool_calls", "customer_id", "customers"),
    ("agente_whatsapp_stories", "campaign_id", "agente_whatsapp_campaigns"),
    ("whatsapp_gateway_logs", "instance_id", "whatsapp_gateway_instances"),
)


def _effective(alias: str) -> str:
    return f"CASE WHEN {alias}.tenant_id IS NULL OR {alias}.tenant_id = 'default' THEN :tenant_id ELSE {alias}.tenant_id END"


def upgrade() -> None:
    bind = op.get_bind()
    exists = bind.execute(sa.text(
        "SELECT 1 FROM tenants WHERE id = :tenant_id AND deleted_at IS NULL"
    ), {"tenant_id": LEGACY_TENANT_ID}).scalar()
    if exists != 1:
        raise RuntimeError("Legacy tenant is missing; refusing marketing/CRM/WhatsApp backfill")

    for table in TABLES:
        invalid = bind.execute(sa.text(
            f"SELECT 1 FROM {table} child LEFT JOIN tenants tenant ON tenant.id = child.tenant_id "
            "WHERE child.tenant_id IS NOT NULL AND child.tenant_id <> 'default' "
            "AND tenant.id IS NULL LIMIT 1"
        )).scalar()
        if invalid is not None:
            raise RuntimeError(f"Unknown tenant label in {table} blocks backfill")

    company_tables = (
        "whatsapp_campaign_deliveries", "whatsapp_gateway_instances", "whatsapp_gateway_logs",
        "whatsapp_gateway_update_logs", "whatsapp_gateway_scheduler_settings",
    )
    for table in company_tables:
        company_mismatch = bind.execute(sa.text(
            f"SELECT 1 FROM {table} WHERE company_id IS NOT NULL "
            "AND company_id <> 'default' AND company_id <> :tenant_id LIMIT 1"
        ), {"tenant_id": LEGACY_TENANT_ID}).scalar()
        if company_mismatch is not None:
            raise RuntimeError(f"Unknown company_id in {table} blocks backfill")

    for table, columns, predicate in UNIQUE_PREFLIGHTS:
        duplicate = bind.execute(sa.text(
            f"SELECT 1 FROM {table} WHERE {predicate} GROUP BY "
            "CASE WHEN tenant_id IS NULL OR tenant_id = 'default' THEN :tenant_id ELSE tenant_id END, "
            f"{columns} HAVING COUNT(*) > 1 LIMIT 1"
        ), {"tenant_id": LEGACY_TENANT_ID}).scalar()
        if duplicate is not None:
            raise RuntimeError(f"Duplicate {table} ({columns}) blocks backfill")

    for table in SINGLETON_PREFLIGHTS:
        duplicate = bind.execute(sa.text(
            f"SELECT 1 FROM {table} GROUP BY CASE WHEN tenant_id IS NULL OR tenant_id = 'default' "
            "THEN :tenant_id ELSE tenant_id END HAVING COUNT(*) > 1 LIMIT 1"
        ), {"tenant_id": LEGACY_TENANT_ID}).scalar()
        if duplicate is not None:
            raise RuntimeError(f"Multiple {table} rows for one tenant block backfill")

    for table, column, parent in OWNERSHIP_PREFLIGHTS:
        mismatch = bind.execute(sa.text(
            f"SELECT 1 FROM {table} child JOIN {parent} parent ON parent.id = child.{column} "
            f"WHERE child.{column} IS NOT NULL AND {_effective('child')} <> {_effective('parent')} LIMIT 1"
        ), {"tenant_id": LEGACY_TENANT_ID}).scalar()
        if mismatch is not None:
            raise RuntimeError(f"Cross-tenant relationship {table}.{column} -> {parent}.id blocks backfill")

    for table in TABLES:
        bind.execute(sa.text(
            f"UPDATE {table} SET tenant_id = :tenant_id WHERE tenant_id IS NULL OR tenant_id = 'default'"
        ), {"tenant_id": LEGACY_TENANT_ID})

    for table in company_tables:
        bind.execute(sa.text(
            f"UPDATE {table} SET company_id = :tenant_id "
            "WHERE company_id IS NULL OR company_id = 'default'"
        ), {"tenant_id": LEGACY_TENANT_ID})


def downgrade() -> None:
    # Ownership backfills are intentionally non-destructive.
    pass

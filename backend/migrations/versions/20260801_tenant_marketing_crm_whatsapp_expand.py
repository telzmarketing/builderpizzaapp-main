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
    for table in NEW_TENANT_COLUMNS:
        op.add_column(table, sa.Column("tenant_id", sa.String(), nullable=True))

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

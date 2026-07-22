"""Contract tenant ownership for marketing, CRM, WhatsApp, traffic and BI."""
from alembic import op
import sqlalchemy as sa

revision = "20260809_tenant_marketing_contract"
down_revision = "20260808_tenant_operations_contract"
branch_labels = None
depends_on = None

TABLES = (
    "customer_ai_profiles", "customer_ai_suggestions", "customer_ai_analysis_jobs", "crm_pipelines", "crm_stages", "crm_cards", "crm_tasks", "customer_groups", "customer_timeline", "crm_card_notes", "crm_card_history", "marketing_campaigns", "visitor_profiles", "visitor_sessions", "visitor_events", "tracking_links", "marketing_settings", "integration_connections", "marketing_automations", "automation_logs", "automation_templates", "exit_popup_config", "email_templates", "email_contact_lists", "email_contact_list_items", "email_messages", "email_campaigns", "email_config", "whatsapp_templates", "whatsapp_contact_lists", "whatsapp_contact_list_items", "whatsapp_messages", "whatsapp_campaigns", "whatsapp_config", "traffic_campaigns", "campaign_creatives", "campaign_links", "tracking_sessions", "tracking_events", "ad_platform_integrations", "ad_accounts", "ad_campaigns_external", "ad_daily_metrics", "campaign_settings", "ad_sync_logs", "ads_oauth_states", "ads_campaigns", "ads_utm_links", "ads_pixels", "business_insights", "product_performance", "marketing_goals", "marketing_timeline_events", "chatbot_settings", "chatbot_faq", "chatbot_conversations", "chatbot_messages", "chatbot_automations", "chatbot_handoffs", "chatbot_knowledge_docs", "agente_whatsapp_sessions", "agente_whatsapp_ai_settings", "agente_whatsapp_channel_settings", "agente_whatsapp_messages", "agente_whatsapp_audio_artifacts", "agente_whatsapp_processing_jobs", "agente_whatsapp_outbox", "agente_whatsapp_provider_states", "agente_whatsapp_internal_alerts", "agente_whatsapp_events", "agente_whatsapp_context", "agente_whatsapp_tool_calls", "agente_whatsapp_metrics", "agente_whatsapp_campaigns", "agente_whatsapp_stories", "customer_tags", "customer_tag_assignments", "customer_segments", "whatsapp_campaign_deliveries", "whatsapp_gateway_instances", "whatsapp_gateway_logs", "whatsapp_gateway_update_logs", "whatsapp_gateway_scheduler_settings",
)

def upgrade() -> None:
    bind = op.get_bind()
    for table in TABLES:
        invalid = bind.execute(sa.text(f"SELECT 1 FROM {table} child LEFT JOIN tenants tenant ON tenant.id=child.tenant_id WHERE child.tenant_id IS NULL OR child.tenant_id='default' OR tenant.id IS NULL OR tenant.deleted_at IS NOT NULL LIMIT 1")).scalar()
        if invalid:
            raise RuntimeError(f"Contract gate failed for {table}: invalid tenant ownership")
    for table in TABLES:
        names = bind.execute(sa.text("SELECT con.conname FROM pg_constraint con JOIN pg_class rel ON rel.oid=con.conrelid JOIN pg_namespace ns ON ns.oid=rel.relnamespace WHERE ns.nspname=current_schema() AND rel.relname=:table AND con.contype='f' AND NOT con.convalidated AND (con.conname=:tenant_fk OR con.conname LIKE :fkmt)"), {"table": table, "tenant_fk": f"fk_{table}_tenant_id_tenants", "fkmt": "fkmt_%"}).scalars().all()
        for name in names:
            op.execute(sa.text(f'ALTER TABLE "{table}" VALIDATE CONSTRAINT "{name}"'))
        op.alter_column(table, "tenant_id", existing_type=sa.String(), nullable=False, server_default=None)

def downgrade() -> None:
    for table in reversed(TABLES):
        op.alter_column(table, "tenant_id", existing_type=sa.String(), nullable=True)

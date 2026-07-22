"""ORM metadata contract for the Wave 6 tenant-owned tables.

This module only aligns SQLAlchemy metadata with the expand migration.  It does
not scope queries and must never be treated as an isolation boundary.
"""
from __future__ import annotations

from hashlib import sha1

from sqlalchemy import Column, ForeignKey, Index, String, event, text
from sqlalchemy.sql.schema import Table


WAVE6_TABLES = frozenset({
    "customer_ai_profiles", "customer_ai_suggestions", "customer_ai_analysis_jobs",
    "crm_pipelines", "crm_stages", "crm_cards", "crm_tasks", "customer_groups",
    "customer_timeline", "crm_card_notes", "crm_card_history", "marketing_campaigns",
    "visitor_profiles", "visitor_sessions", "visitor_events", "tracking_links",
    "marketing_settings", "integration_connections", "marketing_automations",
    "automation_logs", "automation_templates", "exit_popup_config", "email_templates",
    "email_contact_lists", "email_contact_list_items", "email_messages", "email_campaigns",
    "email_config", "whatsapp_templates", "whatsapp_contact_lists",
    "whatsapp_contact_list_items", "whatsapp_messages", "whatsapp_campaigns",
    "whatsapp_config", "traffic_campaigns", "campaign_creatives", "campaign_links",
    "tracking_sessions", "tracking_events", "ad_platform_integrations", "ad_accounts",
    "ad_campaigns_external", "ad_daily_metrics", "campaign_settings", "ad_sync_logs",
    "ads_oauth_states", "ads_campaigns", "ads_utm_links", "ads_pixels",
    "business_insights", "product_performance", "marketing_goals",
    "marketing_timeline_events", "chatbot_settings", "chatbot_faq",
    "chatbot_conversations", "chatbot_messages", "chatbot_automations", "chatbot_handoffs",
    "chatbot_knowledge_docs", "agente_whatsapp_sessions", "agente_whatsapp_ai_settings",
    "agente_whatsapp_channel_settings", "agente_whatsapp_messages",
    "agente_whatsapp_audio_artifacts", "agente_whatsapp_processing_jobs",
    "agente_whatsapp_outbox", "agente_whatsapp_provider_states",
    "agente_whatsapp_internal_alerts", "agente_whatsapp_events", "agente_whatsapp_context",
    "agente_whatsapp_tool_calls", "agente_whatsapp_metrics", "agente_whatsapp_campaigns",
    "agente_whatsapp_stories", "customer_tags", "customer_tag_assignments",
    "customer_segments", "whatsapp_campaign_deliveries", "whatsapp_gateway_instances",
    "whatsapp_gateway_logs", "whatsapp_gateway_update_logs",
    "whatsapp_gateway_scheduler_settings", "store_notification_settings",
    "store_notifications", "store_notification_days", "store_notification_impressions",
    "store_notification_captured",
})

SCOPED_UNIQUES = {
    "customer_ai_profiles": ("uq_mt_customer_ai_profile_customer", ("tenant_id", "customer_id"), None),
    "customer_ai_suggestions": ("uq_mt_customer_ai_suggestion_status", ("tenant_id", "customer_id", "suggestion_type", "slug", "status"), None),
    "visitor_profiles": ("uq_mt_visitor_profile_fingerprint", ("tenant_id", "fingerprint"), "fingerprint IS NOT NULL"),
    "integration_connections": ("uq_mt_integration_connection_type", ("tenant_id", "integration_type"), None),
    "ad_platform_integrations": ("uq_mt_ad_integration_platform", ("tenant_id", "platform"), None),
    "business_insights": ("uq_mt_business_insight_dedupe", ("tenant_id", "dedupe_key"), None),
    "product_performance": ("uq_mt_product_performance_date_product", ("tenant_id", "metric_date", "product_id"), None),
    "agente_whatsapp_provider_states": ("uq_mt_provider_state_provider", ("tenant_id", "provider"), None),
    "agente_whatsapp_internal_alerts": ("uq_mt_internal_alert_dedupe", ("tenant_id", "dedupe_key"), None),
    "agente_whatsapp_outbox": ("uq_mt_whatsapp_outbox_message", ("tenant_id", "message_id"), None),
    "agente_whatsapp_context": ("uq_mt_whatsapp_context_session", ("tenant_id", "session_id"), None),
    "chatbot_conversations": ("uq_mt_chatbot_conversation_session", ("tenant_id", "session_id"), None),
    "whatsapp_gateway_instances": ("uq_mt_gateway_instance_name", ("tenant_id", "name"), None),
    "whatsapp_gateway_scheduler_settings": ("uq_mt_gateway_scheduler_singleton", ("tenant_id",), "tenant_id IS NOT NULL"),
    "campaign_settings": ("uq_mt_campaign_settings_singleton", ("tenant_id",), "tenant_id IS NOT NULL"),
    "marketing_settings": ("uq_mt_marketing_settings_singleton", ("tenant_id",), "tenant_id IS NOT NULL"),
    "email_config": ("uq_mt_email_config_singleton", ("tenant_id",), "tenant_id IS NOT NULL"),
    "whatsapp_config": ("uq_mt_whatsapp_config_singleton", ("tenant_id",), "tenant_id IS NOT NULL"),
    "exit_popup_config": ("uq_mt_exit_popup_singleton", ("tenant_id",), "tenant_id IS NOT NULL"),
    "chatbot_settings": ("uq_mt_chatbot_settings_singleton", ("tenant_id",), "tenant_id IS NOT NULL"),
    "agente_whatsapp_ai_settings": ("uq_mt_agente_ai_settings_singleton", ("tenant_id",), "tenant_id IS NOT NULL"),
    "agente_whatsapp_channel_settings": ("uq_mt_agente_channel_settings_singleton", ("tenant_id",), "tenant_id IS NOT NULL"),
    "store_notification_settings": ("uq_mt_store_notification_settings_singleton", ("tenant_id",), "tenant_id IS NOT NULL"),
    "store_notification_captured": ("uq_mt_store_notification_captured_order", ("tenant_id", "order_id"), "order_id IS NOT NULL"),
}

def _name(prefix: str, *parts: str) -> str:
    raw = "_".join((prefix,) + parts)
    return raw if len(raw) <= 63 else f"{raw[:54]}_{sha1(raw.encode()).hexdigest()[:8]}"


def wave6_tenant_orm_enabled() -> bool:
    """Return explicit application opt-in; default is safely disabled."""
    from backend.config import get_settings

    return get_settings().MULTI_TENANT_WAVE6_ORM_ENABLED


def wave6_tenant_column(table_name: str):
    """Create the nullable, no-default ownership column used during expand."""
    if table_name not in WAVE6_TABLES:
        raise ValueError(f"Table is outside Wave 6: {table_name}")
    return Column(
        String(),
        ForeignKey("tenants.id", name=_name("fk", table_name, "tenant")),
        nullable=True,
        default=None,
        server_default=None,
    )


@event.listens_for(Table, "after_parent_attach", propagate=True)
def _align_wave6_indexes(table: Table, _metadata) -> None:
    if table.name not in WAVE6_TABLES or "tenant_id" not in table.c or "id" not in table.c:
        return
    known = {index.name for index in table.indexes}
    pair_name = _name("uq", table.name, "tenant_id_id")
    if pair_name not in known:
        Index(pair_name, table.c.tenant_id, table.c.id, unique=True)
    scoped = SCOPED_UNIQUES.get(table.name)
    if scoped and scoped[0] not in known:
        name, columns, predicate = scoped
        kwargs = {"postgresql_where": text(predicate)} if predicate else {}
        Index(name, *(table.c[column] for column in columns), unique=True, **kwargs)

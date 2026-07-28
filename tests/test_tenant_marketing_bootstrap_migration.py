from pathlib import Path


def test_all_legacy_tables_are_created_before_tenant_expansion():
    migration = (
        Path(__file__).parents[1]
        / "backend/migrations/versions/20260801_tenant_marketing_crm_whatsapp_expand.py"
    ).read_text(encoding="utf-8")
    expansion_at = migration.index("for table in NEW_TENANT_COLUMNS:")
    tables = (
        "crm_pipelines", "crm_stages", "crm_cards", "crm_tasks",
        "customer_timeline", "crm_card_notes", "crm_card_history",
        "marketing_campaigns", "visitor_sessions", "visitor_events",
        "tracking_links", "marketing_settings", "automation_logs",
        "automation_templates", "email_templates", "email_messages",
        "email_config", "campaign_creatives", "ads_oauth_states",
        "ads_campaigns", "ads_utm_links",
    )
    for table in tables:
        assert migration.index(
            f"CREATE TABLE IF NOT EXISTS {table}"
        ) < expansion_at

    campaign_migration = (
        Path(__file__).parents[1]
        / "backend/migrations/versions/20260704_campaign_contact_lists.py"
    ).read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS email_campaigns" in campaign_migration

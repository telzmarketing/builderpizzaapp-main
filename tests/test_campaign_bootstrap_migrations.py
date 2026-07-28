from pathlib import Path


VERSIONS = Path(__file__).parents[1] / "backend/migrations/versions"


def test_email_campaigns_precedes_contact_list_alter():
    migration = (
        VERSIONS / "20260704_campaign_contact_lists.py"
    ).read_text(encoding="utf-8")

    template_at = migration.index(
        "CREATE TABLE IF NOT EXISTS email_templates"
    )
    campaign_at = migration.index(
        "CREATE TABLE IF NOT EXISTS email_campaigns"
    )
    alter_at = migration.index("ALTER TABLE email_campaigns")

    assert template_at < campaign_at < alter_at


def test_legacy_bootstrap_tables_are_restored_before_first_hard_reference():
    cases = (
        (
            "20260501_crm_tags_segments.py",
            "CREATE TABLE IF NOT EXISTS customer_groups",
            "ALTER TABLE customer_groups",
        ),
        (
            "20260503_driver_mobile_logistics.py",
            "CREATE TABLE IF NOT EXISTS delivery_events",
            "ALTER TABLE IF EXISTS delivery_events",
        ),
        (
            "20260512_ads_pixel_capi_config.py",
            "CREATE TABLE IF NOT EXISTS ads_pixels",
            "ALTER TABLE ads_pixels",
        ),
        (
            "20260527_whatsapp_uazapi_unofficial.py",
            "CREATE TABLE IF NOT EXISTS integration_connections",
            "INSERT INTO integration_connections",
        ),
        (
            "20260701_whatsapp_audio_phase1_deliveries.py",
            "CREATE TABLE IF NOT EXISTS whatsapp_campaigns",
            "REFERENCES whatsapp_campaigns",
        ),
        (
            "20260704_campaign_contact_lists.py",
            "CREATE TABLE IF NOT EXISTS email_campaigns",
            "ALTER TABLE email_campaigns",
        ),
    )

    for filename, create_sql, use_sql in cases:
        migration = (VERSIONS / filename).read_text(encoding="utf-8")
        assert migration.index(create_sql) < migration.index(use_sql)

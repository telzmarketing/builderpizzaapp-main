from pathlib import Path


def test_crm_group_tables_are_created_before_incremental_alters():
    migration = (
        Path(__file__).parents[1]
        / "backend/migrations/versions/20260501_crm_tags_segments.py"
    ).read_text(encoding="utf-8")

    for table in ("customer_groups", "customer_group_members"):
        create_at = migration.index(f"CREATE TABLE IF NOT EXISTS {table}")
        alter_at = migration.index(f"ALTER TABLE {table} ADD COLUMN")
        assert create_at < alter_at


def test_runtime_bootstrap_tables_are_created_before_incremental_alters():
    root = Path(__file__).parents[1]
    cases = (
        ("20260502_marketing_automation_queue.py", "marketing_automations"),
        ("20260507_whatsapp_providers_media.py", "whatsapp_messages"),
        ("20260507_whatsapp_providers_media.py", "whatsapp_config"),
        ("20260511_visitor_location_status.py", "visitor_profiles"),
    )
    for filename, table in cases:
        migration = (
            root / "backend/migrations/versions" / filename
        ).read_text(encoding="utf-8")
        assert migration.index(f"CREATE TABLE IF NOT EXISTS {table}") < migration.index(
            f"ALTER TABLE {table} ADD COLUMN"
        )


def test_whatsapp_template_precedes_message_foreign_key():
    migration = (
        Path(__file__).parents[1]
        / "backend/migrations/versions/20260507_whatsapp_providers_media.py"
    ).read_text(encoding="utf-8")

    assert migration.index("CREATE TABLE IF NOT EXISTS whatsapp_templates") < migration.index(
        "CREATE TABLE IF NOT EXISTS whatsapp_messages"
    )

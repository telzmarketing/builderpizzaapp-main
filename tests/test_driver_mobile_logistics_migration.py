from pathlib import Path


def test_runtime_logistics_tables_are_created_before_alters_and_indexes():
    migration = (
        Path(__file__).parents[1]
        / "backend/migrations/versions/20260503_driver_mobile_logistics.py"
    ).read_text(encoding="utf-8")

    cases = (
        (
            "delivery_events",
            "ALTER TABLE IF EXISTS delivery_events ADD COLUMN",
            "ix_delivery_events_delivery_created",
        ),
        (
            "delivery_earnings",
            "ALTER TABLE IF EXISTS delivery_earnings ALTER COLUMN",
            "ix_delivery_earnings_driver_period",
        ),
    )
    for table, alter, index in cases:
        create_at = migration.index(f"CREATE TABLE IF NOT EXISTS {table}")
        assert create_at < migration.index(alter)
        assert create_at < migration.index(index)

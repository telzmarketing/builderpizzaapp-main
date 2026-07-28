from pathlib import Path


def test_integration_connections_precedes_historical_and_uazapi_seeds():
    migration = (
        Path(__file__).parents[1]
        / "backend/migrations/versions/20260527_whatsapp_uazapi_unofficial.py"
    ).read_text(encoding="utf-8")

    create_at = migration.index(
        "CREATE TABLE IF NOT EXISTS integration_connections"
    )
    first_seed_at = migration.index(
        "INSERT INTO integration_connections"
    )
    uazapi_seed_at = migration.rindex(
        "INSERT INTO integration_connections"
    )

    assert create_at < first_seed_at <= uazapi_seed_at
    for integration_type in (
        "meta_ads",
        "google_ads",
        "tiktok_ads",
        "whatsapp_cloud",
        "whatsapp_qr",
        "smtp",
        "whatsapp_unofficial",
    ):
        assert integration_type in migration

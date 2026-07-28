from pathlib import Path


VERSIONS = Path(__file__).parents[1] / "backend/migrations/versions"


def test_ads_pixels_is_created_before_capi_alters():
    migration = (
        VERSIONS / "20260512_ads_pixel_capi_config.py"
    ).read_text(encoding="utf-8")

    create_at = migration.index("CREATE TABLE IF NOT EXISTS ads_pixels")
    assert create_at < migration.index(
        "ALTER TABLE ads_pixels ADD COLUMN IF NOT EXISTS conversion_access_token"
    )
    assert create_at < migration.index(
        "ALTER TABLE ads_pixels ADD COLUMN IF NOT EXISTS base_code"
    )


def test_ads_pixels_exists_before_event_default_branch_migration():
    capi_migration = (
        VERSIONS / "20260512_ads_pixel_capi_config.py"
    ).read_text(encoding="utf-8")
    defaults_migration = (
        VERSIONS / "20260512_ads_pixel_event_defaults.py"
    ).read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS ads_pixels" in capi_migration
    assert 'down_revision = "20260512_ads_pixel_capi_config"' in defaults_migration

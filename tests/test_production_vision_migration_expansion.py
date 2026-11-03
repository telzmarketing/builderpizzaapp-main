from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "backend/migrations/versions/20261103_production_vision_expansion.py"
ORIGINAL = ROOT / "backend/migrations/versions/20261102_production_vision.py"


def test_expansion_is_a_new_incremental_revision_and_does_not_edit_original():
    migration = MIGRATION.read_text(encoding="utf-8")
    original = ORIGINAL.read_text(encoding="utf-8")

    assert 'revision = "20261103_production_vision_expansion"' in migration
    assert 'down_revision = "20261102_production_vision"' in migration
    assert 'revision = "20261103_production_vision_expansion"' not in original
    assert "def downgrade()" in migration
    assert "pass" in migration[migration.index("def downgrade()") :]


def test_expansion_guards_existing_objects_and_adds_required_columns():
    migration = MIGRATION.read_text(encoding="utf-8")

    for token in (
        "production_attempt_id",
        "station_id",
        "camera_id",
        "zone_id",
        "sha256",
        "processing_status",
        "production_vision_settings",
        "production_vision_zones",
        "production_vision_zone_occupancies",
        "production_vision_history_events",
        "production_vision_incidents",
        "production_vision_evidence_holds",
    ):
        assert token in migration

    for token in ("_table_exists", "_column_exists", "_index_exists", "_fk_exists", "postgresql_where"):
        assert token in migration


def test_expansion_preserves_tenant_scoped_postgresql_constraints():
    migration = MIGRATION.read_text(encoding="utf-8")

    assert "tenant_id" in migration
    assert "production_units.tenant_id" not in migration or "production_attempts" in migration
    assert "production_vision_sessions.tenant_id" in migration
    assert "production_vision_photos.tenant_id" in migration
    assert "ondelete=\"RESTRICT\"" in migration
    assert "ondelete=\"SET NULL\"" in migration
    assert "uq_production_vision_zone_active" in migration


def test_zone_composite_key_exists_before_occupancy_foreign_key():
    migration = MIGRATION.read_text(encoding="utf-8")

    unique_zone_key = migration.index(
        '"uq_production_vision_zones_tenant_id", "production_vision_zones", ["tenant_id", "id"], unique=True'
    )
    occupancy_table = migration.index('"production_vision_zone_occupancies"')

    assert unique_zone_key < occupancy_table


def test_photo_composite_key_exists_before_history_foreign_key():
    migration = MIGRATION.read_text(encoding="utf-8")

    unique_photo_key = migration.index(
        '"uq_production_vision_photos_tenant_id", "production_vision_photos", ["tenant_id", "id"], unique=True'
    )
    history_table = migration.index('"production_vision_history_events"')

    assert unique_photo_key < history_table
    assert 'production_vision_photos.tenant_id", "production_vision_photos.id"], ondelete="RESTRICT"' in migration

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_expansion_contract_is_tenant_scoped_and_has_required_surfaces():
    model = (ROOT / "backend/models/production_vision.py").read_text(encoding="utf-8")
    service = (ROOT / "backend/services/production_vision_service.py").read_text(encoding="utf-8")
    route = (ROOT / "backend/routes/production_vision.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend/migrations/versions/20261102_production_vision.py").read_text(encoding="utf-8")
    for token in ("ProductionVisionZone", "ProductionVisionZoneOccupancy", "ProductionVisionSettings", "ProductionVisionIncident", "ProductionVisionEvidenceHold", "ProductionVisionHistoryEvent", "production_attempt_id"):
        assert token in model
    for token in ("photos_per_session", "max_width_px", "image_format", "image_quality", "retention_days"):
        assert token in service
    for token in ("/settings", "/diagnostics", "/history", "/retention/dry-run", "/evidence-holds"):
        assert token in route
    assert '"files_deleted": 0' in service
    assert "production_vision_history_events" in migration
    assert "kds_audit" not in model.lower()


def test_retention_is_explicitly_non_destructive_first_delivery():
    service = (ROOT / "backend/services/production_vision_service.py").read_text(encoding="utf-8")
    assert "files_deleted" in service
    assert "metadata_preserved" in service
    assert "os.remove" not in service
    assert "Path(" not in service

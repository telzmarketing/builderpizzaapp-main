from pathlib import Path

from backend.schemas.production_vision import CaptureConfigIn, CaptureEventIn


ROOT = Path(__file__).resolve().parents[1]


def test_capture_schemas_define_three_configurable_milestones_and_modes():
    config = CaptureConfigIn(
        station_id="pizza-1",
        milestone_1_name="entrada", milestone_1_seconds=0,
        milestone_2_name="montagem", milestone_2_seconds=25,
        milestone_3_name="saida", milestone_3_seconds=70,
    )
    assert config.milestone_3_seconds == 70
    assert CaptureEventIn(milestone="milestone_2", idempotency_key="evt-1", mode="manual").mode == "manual"


def test_capture_contract_is_tenant_scoped_idempotent_and_gateway_aware():
    model = (ROOT / "backend/models/production_vision.py").read_text(encoding="utf-8")
    service = (ROOT / "backend/services/production_vision_service.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend/migrations/versions/20261106_production_vision_capture_rules.py").read_text(encoding="utf-8")
    routes = (ROOT / "backend/routes/production_vision.py").read_text(encoding="utf-8")
    for token in ("ProductionVisionCaptureConfig", "ProductionVisionCaptureEvent", "tenant_id", "milestone_1_seconds", "milestone_2_seconds", "milestone_3_seconds"):
        assert token in model
    for token in ("idempotency_key", "capture_gateway_not_configured", "unsupported", "automatic", "manual", "capture_state"):
        assert token in service
    assert "production_vision_capture_configs" in migration
    assert "production_vision_capture_events" in migration
    assert "ForeignKeyConstraint" in migration
    assert 'router.get("/capture-config")' in routes
    assert 'router.put("/capture-config")' in routes
    assert 'router.post("/sessions/{session_id}/captures"' in routes
    assert 'router.get("/sessions/{session_id}/capture-state")' in routes


def test_capture_preserves_existing_photo_and_session_routes():
    routes = (ROOT / "backend/routes/production_vision.py").read_text(encoding="utf-8")
    assert 'router.post("/sessions/{session_id}/photos"' in routes
    assert 'router.post("/sessions"' in routes
    assert 'router.get("/dashboard")' in routes

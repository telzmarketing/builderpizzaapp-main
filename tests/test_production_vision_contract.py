from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_production_vision_contract_is_tenant_scoped_and_separate_from_delivery_audit():
    model = (ROOT / "backend/models/production_vision.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend/migrations/versions/20261102_production_vision.py").read_text(encoding="utf-8")
    route = (ROOT / "backend/routes/production_vision.py").read_text(encoding="utf-8")

    assert "tenant_id" in model
    assert "production_units.tenant_id" in model
    assert "credentials_encrypted" in model
    assert "connection_url" not in route
    assert "kds_audit" not in model.lower()
    assert "production_vision_photos" in migration
    assert "idempotency" in migration


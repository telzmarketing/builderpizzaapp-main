from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_phase7_models_have_tenant_safe_identities_and_queue_indexes():
    source = (ROOT / "backend/models/kds_production.py").read_text(encoding="utf-8")
    assert "production_units" in source and "production_attempts" in source
    assert "uq_production_units_tenant_item_index" in source
    assert "uq_production_attempts_tenant_unit_number" in source
    assert "kds_operator_states" in source and "kds_assignments" in source
    assert "ForeignKeyConstraint([\"tenant_id\", \"production_unit_id\"]" in source

def test_phase7_migration_is_forward_only_and_after_preparation():
    source = (ROOT / "backend/migrations/versions/20261022_kds_production.py").read_text(encoding="utf-8")
    assert 'revision = "20261022_kds_production"' in source
    assert 'down_revision = "20261022_preparation_execution"' in source
    assert "Forward-only" in source

def test_phase7_routes_keep_published_kds_paths():
    source = (ROOT / "backend/routes/kds.py").read_text(encoding="utf-8")
    for path in ("/kitchen/my-queue", "/kitchen/presence", "/kitchen/heartbeat", "/kitchen/tasks/{task_id}/start", "/kitchen/tasks/{task_id}/finish-assembly", "/kitchen/tasks/{task_id}/start-oven", "/kitchen/tasks/{task_id}/complete-oven", "/kitchen/tasks/{task_id}/check", "/kitchen/tasks/{task_id}/remake", "/management/redistributions"):
        assert path in source
    assert "expected_version" in (ROOT / "backend/schemas/kds_production.py").read_text(encoding="utf-8")
    assert "require_rbac_permission" in source

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_wave6_compatibility_mode_uses_seeded_legacy_tenant(monkeypatch):
    from backend.config import get_settings
    from backend.core.wave6_tenant_context import wave6_tenant_id

    monkeypatch.delenv("MULTI_TENANT_WAVE6_ORM_ENABLED", raising=False)
    get_settings.cache_clear()
    assert wave6_tenant_id(None) == "tenant-legacy-default"
    get_settings.cache_clear()


def test_marketing_workflow_migration_backfills_and_constrains_tenants():
    source = (ROOT / "backend/migrations/versions/20261003_marketing_workflow_tenant_isolation.py").read_text(encoding="utf-8")
    assert "tenant-legacy-default" in source
    assert "marketing_workflows" in source
    assert "marketing_workflow_comments" in source
    assert "create_foreign_key" in source
    assert "nullable=False" in source


def test_marketing_workflow_route_scopes_every_operation():
    source = (ROOT / "backend/routes/marketing_workflow.py").read_text(encoding="utf-8")
    assert "block_unsafe_wave6_route" not in source
    assert "panel_wave6_context" in source
    assert "wave6_tenant_id(context)" in source
    assert "tenant_id = :tenant_id" in source
    assert "tenant_id, workflow_id" in source

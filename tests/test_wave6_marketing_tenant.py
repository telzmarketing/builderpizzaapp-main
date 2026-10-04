from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_marketing_routes_scope_orm_and_public_tracking_by_tenant():
    source = (ROOT / "backend/routes/marketing.py").read_text(encoding="utf-8")
    assert "block_unsafe_wave6_route" not in source
    assert "panel_wave6_context" in source
    assert "public_wave6_context" in source
    assert "tenant_id=tenant_id" in source
    assert "VisitorSession.tenant_id == tenant_id" in source
    assert "MarketingSettings.tenant_id == tenant_id" in source
    assert "IntegrationConnection.tenant_id == tenant_id" in source


def test_marketing_tenant_key_migration_removes_global_contracts():
    source = (ROOT / "backend/migrations/versions/20261003_marketing_tenant_keys.py").read_text(encoding="utf-8")
    for table in ("visitor_profiles", "tracking_links", "integration_connections"):
        assert table in source
    assert "whatsapp_config ALTER COLUMN id DROP DEFAULT" in source

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_exit_popup_is_tenant_scoped_and_not_wave6_guarded():
    source = (ROOT / "backend" / "routes" / "exit_popup.py").read_text(encoding="utf-8")

    assert "block_unsafe_wave6_route" not in source
    assert "public_wave6_context" in source
    assert "panel_wave6_context" in source
    assert "wave6_tenant_id(context)" in source
    assert "ExitPopupConfig.tenant_id == tenant_id" in source
    assert "cfg = ExitPopupConfig(id=config_id, tenant_id=tenant_id)" in source


def test_wave6_context_helper_fails_closed_when_enabled():
    source = (ROOT / "backend" / "core" / "wave6_tenant_context.py").read_text(encoding="utf-8")

    assert "resolve_panel_tenant_context" in source
    assert "resolve_public_tenant_context" in source
    assert "wave6_tenant_orm_enabled()" in source
    assert "WAVE6_SESSION_TENANT_KEY" in source
    assert "db.info[WAVE6_SESSION_TENANT_KEY] = trusted" in source
    assert "require_context_when_enabled(context, enabled=wave6_tenant_orm_enabled())" in source

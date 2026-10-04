from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_customer_events_are_tenant_scoped_and_not_wave6_guarded():
    source = (ROOT / "backend" / "routes" / "customer_events.py").read_text(encoding="utf-8")

    assert "block_unsafe_wave6_route" not in source
    assert "public_wave6_context" in source
    assert "panel_wave6_context" in source
    assert "tenant_id = wave6_tenant_id(context)" in source
    assert "tenant_id=tenant_id" in source
    assert "expected_tenant_id=tenant_id" in source
    assert "CustomerEvent.tenant_id == wave6_tenant_id(context)" in source
    assert "CustomerEvent.tenant_id == tenant_id" in source

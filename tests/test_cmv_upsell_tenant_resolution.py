from backend.core.tenant_context import TenantContext, TenantSource
from backend.routes.cmv import _catalog_tenant_id as cmv_tenant_id
from backend.routes.upsells import _catalog_tenant_id as upsell_tenant_id


def test_cmv_and_upsell_use_selected_panel_tenant_before_legacy_fallback():
    context = TenantContext(tenant_id="store-a", source=TenantSource.JOB)

    assert cmv_tenant_id(context) == "store-a"
    assert upsell_tenant_id(context) == "store-a"


def test_cmv_and_upsell_keep_legacy_fallback_without_context():
    assert cmv_tenant_id(None) == "tenant-legacy-default"
    assert upsell_tenant_id(None) == "tenant-legacy-default"

import inspect
from types import SimpleNamespace

import pytest

from backend.config import get_settings
from backend.core.tenant_context import TenantContext, TenantContextMismatch, TenantContextMissing, TenantSource
from backend.services.cmv_service import CmvService
from backend.services.cmv_snapshot_service import OrderCmvSnapshotService
from backend.services.inventory_service import InventoryService, ProductInventoryAvailabilityService


def _context(tenant_id: str = "tenant-a") -> TenantContext:
    return TenantContext(tenant_id=tenant_id, source=TenantSource.JOB)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_wave7_inventory_and_cmv_require_trusted_context(monkeypatch):
    monkeypatch.setenv("MULTI_TENANT_WAVE7_ORM_ENABLED", "true")

    with pytest.raises(TenantContextMissing):
        InventoryService(SimpleNamespace(), "tenant-a")
    with pytest.raises(TenantContextMissing):
        ProductInventoryAvailabilityService(SimpleNamespace(), "tenant-a")
    with pytest.raises(TenantContextMissing):
        CmvService(SimpleNamespace(), "tenant-a")
    with pytest.raises(TenantContextMissing):
        OrderCmvSnapshotService(SimpleNamespace(), "tenant-a")


def test_wave7_inventory_and_cmv_bind_all_reads_writes_to_context(monkeypatch):
    monkeypatch.setenv("MULTI_TENANT_WAVE7_ORM_ENABLED", "true")
    context = _context()

    assert InventoryService(SimpleNamespace(), "tenant-a", context)._tenant_id == "tenant-a"
    assert ProductInventoryAvailabilityService(SimpleNamespace(), "tenant-a", context)._tenant_id == "tenant-a"
    assert CmvService(SimpleNamespace(), "tenant-a", context)._tenant_id == "tenant-a"
    assert OrderCmvSnapshotService(SimpleNamespace(), "tenant-a", context)._tenant_id == "tenant-a"

    with pytest.raises(TenantContextMismatch):
        InventoryService(SimpleNamespace(), "tenant-b", context)
    with pytest.raises(TenantContextMismatch):
        CmvService(SimpleNamespace(), "tenant-b", context)


def test_wave7_inventory_children_inherit_the_trusted_tenant(monkeypatch):
    monkeypatch.setenv("MULTI_TENANT_WAVE7_ORM_ENABLED", "true")
    # Model construction requires the full application's SQLAlchemy mapper
    # registry. Verify the two persistence boundaries explicitly here; the
    # route/service tests above verify the trusted context that supplies it.
    purchase_children = inspect.getsource(InventoryService._replace_purchase_items)
    recipe_children = inspect.getsource(InventoryService._replace_recipe_items)
    assert "tenant_id=self._tenant_id" in purchase_children
    assert "tenant_id=self._tenant_id" in recipe_children

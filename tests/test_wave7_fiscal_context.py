from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.config import get_settings
from backend.core.tenant_context import TenantContext, TenantContextMismatch, TenantContextMissing, TenantSource
from backend.services.fiscal_service import FiscalService


def _context(tenant_id: str = "tenant-a") -> TenantContext:
    return TenantContext(tenant_id=tenant_id, source=TenantSource.JOB)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_fiscal_keeps_legacy_tenant_while_wave7_is_disabled(monkeypatch):
    monkeypatch.delenv("MULTI_TENANT_WAVE7_ORM_ENABLED", raising=False)
    assert FiscalService(SimpleNamespace(), "legacy-company")._tenant_id == "legacy-company"


def test_fiscal_requires_a_trusted_context_when_wave7_is_enabled(monkeypatch):
    monkeypatch.setenv("MULTI_TENANT_WAVE7_ORM_ENABLED", "true")
    with pytest.raises(TenantContextMissing):
        FiscalService(SimpleNamespace(), "tenant-a")


def test_fiscal_binds_to_context_and_rejects_cross_tenant_id(monkeypatch):
    monkeypatch.setenv("MULTI_TENANT_WAVE7_ORM_ENABLED", "true")
    context = _context()
    assert FiscalService(SimpleNamespace(), "tenant-a", context)._tenant_id == "tenant-a"
    with pytest.raises(TenantContextMismatch):
        FiscalService(SimpleNamespace(), "tenant-b", context)


def test_fiscal_route_and_persistence_boundaries_propagate_tenant_context():
    route_source = Path("backend/routes/fiscal.py").read_text(encoding="utf-8")
    service_source = Path("backend/services/fiscal_service.py").read_text(encoding="utf-8")

    assert "FiscalService(db, operation_tenant_id(tenant_context), tenant_context)" in route_source
    assert "Order.tenant_id == self._tenant_id" in service_source
    assert "Product.tenant_id == self._tenant_id" in service_source
    assert "tenant_id=self._tenant_id,\n                document_id=row.id" in service_source

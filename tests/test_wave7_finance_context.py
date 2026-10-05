from pathlib import Path
from types import SimpleNamespace
import pytest

from backend.config import get_settings
from backend.core.tenant_context import TenantContext, TenantContextMismatch, TenantContextMissing, TenantSource
from backend.services.finance_service import FinanceService


def _context(tenant_id: str = "tenant-a") -> TenantContext:
    return TenantContext(tenant_id=tenant_id, source=TenantSource.JOB)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_finance_keeps_legacy_tenant_while_wave7_is_disabled(monkeypatch):
    monkeypatch.delenv("MULTI_TENANT_WAVE7_ORM_ENABLED", raising=False)
    assert FinanceService(SimpleNamespace(), "legacy-company")._tenant_id == "legacy-company"


def test_finance_requires_a_trusted_context_when_wave7_is_enabled(monkeypatch):
    monkeypatch.setenv("MULTI_TENANT_WAVE7_ORM_ENABLED", "true")
    with pytest.raises(TenantContextMissing):
        FinanceService(SimpleNamespace(), "tenant-a")


def test_finance_binds_to_context_and_rejects_cross_tenant_id(monkeypatch):
    monkeypatch.setenv("MULTI_TENANT_WAVE7_ORM_ENABLED", "true")
    context = _context()
    assert FinanceService(SimpleNamespace(), "tenant-a", context)._tenant_id == "tenant-a"
    with pytest.raises(TenantContextMismatch):
        FinanceService(SimpleNamespace(), "tenant-b", context)


def test_finance_route_and_async_consumers_propagate_trusted_context():
    route_source = Path("backend/routes/finance.py").read_text(encoding="utf-8")
    main_source = Path("backend/main.py").read_text(encoding="utf-8")
    service_source = Path("backend/services/finance_service.py").read_text(encoding="utf-8")

    assert "FinanceService(db, operation_tenant_id(tenant_context), tenant_context)" in route_source
    assert "trusted_process_context(tenant_id, source=TenantSource.JOB)" in main_source
    assert "Payment.tenant_id == self._tenant_id" in service_source
    assert "Order.tenant_id == self._tenant_id" in service_source
    assert "InventoryPurchase.tenant_id == self._tenant_id" in service_source

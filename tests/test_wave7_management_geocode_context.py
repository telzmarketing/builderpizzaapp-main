from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.config import get_settings
from backend.core.tenant_context import TenantContext, TenantContextMismatch, TenantContextMissing, TenantSource
from backend.services.store_operation_service import StoreOperationService


def _context(tenant_id: str = "tenant-a") -> TenantContext:
    return TenantContext(tenant_id=tenant_id, source=TenantSource.JOB)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_management_keeps_legacy_default_while_wave7_is_disabled(monkeypatch):
    monkeypatch.delenv("MULTI_TENANT_WAVE7_ORM_ENABLED", raising=False)
    assert StoreOperationService(SimpleNamespace())._tenant_id == "default"


def test_management_requires_trusted_context_when_wave7_is_enabled(monkeypatch):
    monkeypatch.setenv("MULTI_TENANT_WAVE7_ORM_ENABLED", "true")
    with pytest.raises(TenantContextMissing):
        StoreOperationService(SimpleNamespace())


def test_management_rejects_cross_tenant_identifier_when_wave7_is_enabled(monkeypatch):
    monkeypatch.setenv("MULTI_TENANT_WAVE7_ORM_ENABLED", "true")
    assert StoreOperationService(SimpleNamespace(), "tenant-a", _context())._tenant_id == "tenant-a"
    with pytest.raises(TenantContextMismatch):
        StoreOperationService(SimpleNamespace(), "tenant-b", _context())


def test_management_and_geocode_routes_propagate_trusted_context():
    management_route = Path("backend/routes/store_operation.py").read_text(encoding="utf-8")
    management_service = Path("backend/services/store_operation_service.py").read_text(encoding="utf-8")
    delivery_route = Path("backend/routes/delivery.py").read_text(encoding="utf-8")
    delivery_service = Path("backend/services/delivery_service.py").read_text(encoding="utf-8")

    assert "StoreOperationService(db, tenant_id, tenant_context)" in management_route
    assert "Contexto confiavel obrigatorio para gestao da Wave 7." in management_service
    assert "tenant_context=context" in delivery_route
    assert "f\"{tenant_id}:{query.lower().strip()}\"" in delivery_service
    assert "GeocodeCache.tenant_id == tenant_id" in delivery_service


def test_bootstrap_no_longer_owns_management_or_geocode_schema():
    main = Path("backend/main.py").read_text(encoding="utf-8")
    migration = Path(
        "backend/migrations/versions/20261004_wave7_management_geocode_contract.py"
    ).read_text(encoding="utf-8")

    assert 'CREATE TABLE IF NOT EXISTS store_operation_settings' not in main
    assert 'CREATE TABLE IF NOT EXISTS geocode_cache' not in main
    assert "op.alter_column(GEOCODE_TABLE, \"tenant_id\"" in migration
    assert "tenant ownership invalido" in migration

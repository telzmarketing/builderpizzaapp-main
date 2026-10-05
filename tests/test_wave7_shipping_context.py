from types import SimpleNamespace

import pytest

from backend.config import get_settings
from backend.core.tenant_context import TenantContext, TenantContextMissing, TenantSource
from backend.models.shipping_v2 import ShippingNeighborhood
from backend.services.shipping_service import ShippingService


class QueryProbe:
    def __init__(self):
        self.conditions = []

    def filter(self, *conditions):
        self.conditions.extend(conditions)
        return self


def _context(tenant_id: str) -> TenantContext:
    return TenantContext(tenant_id=tenant_id, source=TenantSource.JOB)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_shipping_keeps_legacy_global_behavior_while_wave7_is_disabled(monkeypatch):
    monkeypatch.delenv("MULTI_TENANT_WAVE7_ORM_ENABLED", raising=False)
    service = ShippingService(SimpleNamespace())

    assert service._tenant_enabled is False
    assert service._singleton_id("shipping-config") == "default"


def test_shipping_requires_trusted_context_when_wave7_is_enabled(monkeypatch):
    monkeypatch.setenv("MULTI_TENANT_WAVE7_ORM_ENABLED", "true")

    with pytest.raises(TenantContextMissing, match="frete da Wave 7"):
        ShippingService(SimpleNamespace())


def test_shipping_scopes_the_same_resource_to_each_tenant_when_wave7_is_enabled(monkeypatch):
    monkeypatch.setenv("MULTI_TENANT_WAVE7_ORM_ENABLED", "true")
    query_a = QueryProbe()
    query_b = QueryProbe()

    ShippingService(SimpleNamespace(query=lambda _model: query_a), _context("tenant-a"))._query(ShippingNeighborhood)
    ShippingService(SimpleNamespace(query=lambda _model: query_b), _context("tenant-b"))._query(ShippingNeighborhood)

    assert query_a.conditions[0].right.value == "tenant-a"
    assert query_b.conditions[0].right.value == "tenant-b"
    assert query_a.conditions[0].right.value != query_b.conditions[0].right.value


def test_shipping_source_scopes_all_rules_and_passes_context_to_geocode():
    source = open("backend/services/shipping_service.py", encoding="utf-8").read()

    assert "self._tenant_enabled = operations_enforcement_enabled() or self._wave7_enabled" in source
    assert "Contexto confiavel obrigatorio para frete da Wave 7." in source
    assert "tenant_context=self._tenant_context" in source
    assert "self._query(ShippingZoneArea)" in source
    assert "tenant_id=self._tenant_context.tenant_id" in source

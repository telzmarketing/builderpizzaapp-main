from types import SimpleNamespace

import pytest

from backend.config import get_settings
from backend.core.tenant_context import TenantContext, TenantContextMissing, TenantSource
from backend.models.shipping_v2 import FreightTypeConfig, ShippingNeighborhood
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


def test_shipping_scopes_trusted_context_even_when_rollout_flag_is_disabled(monkeypatch):
    monkeypatch.delenv("MULTI_TENANT_WAVE7_ORM_ENABLED", raising=False)
    monkeypatch.delenv("TENANT_OPERATIONS_ENFORCEMENT_ENABLED", raising=False)

    service = ShippingService(SimpleNamespace(), _context("tenant-a"))

    assert service._tenant_enabled is True
    assert service._singleton_id("shipping-config") == "shipping-config-tenant-a"
    config = service._own(FreightTypeConfig(id="freight-tenant-a", freight_type="pickup"))
    assert config.tenant_id == "tenant-a"


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

    assert "self._tenant_enabled = operations_enforcement_enabled() or self._wave7_enabled or tenant_context is not None" in source
    assert "Contexto confiavel obrigatorio para frete da Wave 7." in source
    assert "tenant_context=self._tenant_context" in source
    assert "self._query(ShippingZoneArea)" in source
    assert "tenant_id=self._tenant_context.tenant_id" in source


def test_shipping_compatibility_mode_assigns_backfilled_legacy_owner_on_create(monkeypatch):
    monkeypatch.delenv("TENANT_OPERATIONS_ENFORCEMENT_ENABLED", raising=False)
    monkeypatch.delenv("MULTI_TENANT_WAVE7_ORM_ENABLED", raising=False)
    service = ShippingService(SimpleNamespace())

    config = service._own(FreightTypeConfig(id="freight-test", freight_type="pickup"))

    assert config.tenant_id == "tenant-legacy-default"

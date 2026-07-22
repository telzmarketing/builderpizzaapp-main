from types import SimpleNamespace

import pytest

from backend.core.tenant_context import TenantContext, TenantContextMismatch, TenantContextMissing, TenantSource
from backend.core.wave7_tenant_orm import assign_wave7_tenant, scope_wave7_query, wave7_orm_enabled


class QueryProbe:
    def __init__(self):
        self.predicate = None

    def filter(self, predicate):
        self.predicate = predicate
        return self


def context() -> TenantContext:
    return TenantContext(tenant_id="tenant-a", source=TenantSource.JOB)


def test_wave7_gate_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MULTI_TENANT_WAVE7_ORM_ENABLED", raising=False)
    assert wave7_orm_enabled() is False
    resource = SimpleNamespace(tenant_id=None)
    assert assign_wave7_tenant(resource, None) is resource
    assert resource.tenant_id is None


def test_wave7_enabled_requires_trusted_context(monkeypatch):
    monkeypatch.setenv("MULTI_TENANT_WAVE7_ORM_ENABLED", "true")
    with pytest.raises(TenantContextMissing):
        assign_wave7_tenant(SimpleNamespace(tenant_id=None), None)
    with pytest.raises(TenantContextMissing):
        scope_wave7_query(QueryProbe(), SimpleNamespace(tenant_id="column"), None)


def test_wave7_assigns_and_rejects_cross_tenant(monkeypatch):
    monkeypatch.setenv("MULTI_TENANT_WAVE7_ORM_ENABLED", "true")
    resource = SimpleNamespace(tenant_id=None)
    assign_wave7_tenant(resource, context())
    assert resource.tenant_id == "tenant-a"
    with pytest.raises(TenantContextMismatch):
        assign_wave7_tenant(SimpleNamespace(tenant_id="tenant-b"), context())

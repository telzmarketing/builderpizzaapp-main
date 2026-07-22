from types import SimpleNamespace

import pytest

from backend.core.tenant_context import TenantContextMismatch, TenantContextMissing, TenantSource, trusted_process_context
from backend.core import tenant_ownership
from backend.core.tenant_ownership import (
    assign_tenant_on_create,
    assert_resource_ownership,
    customers_orders_enforcement_enabled,
    operations_enforcement_enabled,
    scope_query_to_tenant,
)


class FakeColumn:
    def __eq__(self, value):
        return ("tenant_id", value)


class FakeQuery:
    def __init__(self):
        self.predicates = []

    def filter(self, predicate):
        self.predicates.append(predicate)
        return self


def context(tenant_id="tenant-a"):
    return trusted_process_context(tenant_id, source=TenantSource.JOB)


def test_disabled_query_is_unchanged_without_context():
    query = FakeQuery()
    assert scope_query_to_tenant(query, SimpleNamespace(tenant_id=FakeColumn()), None, enabled=False) is query
    assert query.predicates == []


def test_enabled_query_requires_context_and_adds_exact_predicate():
    query = FakeQuery()
    with pytest.raises(TenantContextMissing):
        scope_query_to_tenant(query, SimpleNamespace(tenant_id=FakeColumn()), None, enabled=True)
    scope_query_to_tenant(query, SimpleNamespace(tenant_id=FakeColumn()), context(), enabled=True)
    assert query.predicates == [("tenant_id", "tenant-a")]


def test_create_assignment_is_opt_in_and_does_not_overwrite():
    legacy = SimpleNamespace(tenant_id=None)
    assign_tenant_on_create(legacy, None, enabled=False)
    assert legacy.tenant_id is None
    assign_tenant_on_create(legacy, context(), enabled=True)
    assert legacy.tenant_id == "tenant-a"
    with pytest.raises(TenantContextMismatch):
        assign_tenant_on_create(legacy, context("tenant-b"), enabled=True)


def test_id_lookup_ownership_fails_closed_when_enabled():
    assert_resource_ownership(SimpleNamespace(tenant_id=None), None, enabled=False)
    with pytest.raises(TenantContextMismatch):
        assert_resource_ownership(SimpleNamespace(tenant_id=None), context(), enabled=True)
    with pytest.raises(TenantContextMismatch):
        assert_resource_ownership(SimpleNamespace(tenant_id="tenant-b"), context(), enabled=True)
    assert_resource_ownership(SimpleNamespace(tenant_id="tenant-a"), context(), enabled=True)


def test_customers_orders_gate_is_explicit_and_opt_in(monkeypatch):
    monkeypatch.setattr(
        tenant_ownership,
        "get_settings",
        lambda: SimpleNamespace(TENANT_CUSTOMERS_ORDERS_ENFORCEMENT_ENABLED=False),
    )
    assert customers_orders_enforcement_enabled() is False

    monkeypatch.setattr(
        tenant_ownership,
        "get_settings",
        lambda: SimpleNamespace(TENANT_CUSTOMERS_ORDERS_ENFORCEMENT_ENABLED=True),
    )
    assert customers_orders_enforcement_enabled() is True


def test_operations_gate_is_explicit_and_opt_in(monkeypatch):
    monkeypatch.setattr(
        tenant_ownership,
        "get_settings",
        lambda: SimpleNamespace(TENANT_OPERATIONS_ENFORCEMENT_ENABLED=False),
    )
    assert operations_enforcement_enabled() is False

    monkeypatch.setattr(
        tenant_ownership,
        "get_settings",
        lambda: SimpleNamespace(TENANT_OPERATIONS_ENFORCEMENT_ENABLED=True),
    )
    assert operations_enforcement_enabled() is True

"""Opt-in helpers for incrementally adopting tenant-owned ORM resources.

Schema expansion alone is not isolation.  Existing routes keep their legacy
queries while the rollout flag is disabled.  A migrated route must pass a
trusted ``TenantContext`` and use these helpers for both reads and writes.
"""
from __future__ import annotations

from typing import Any, TypeVar

from backend.config import get_settings
from backend.core.tenant_context import TenantContext, TenantContextMissing


QueryT = TypeVar("QueryT")


def identity_catalog_enforcement_enabled() -> bool:
    """Return the dedicated Wave 2 runtime gate (disabled by default)."""
    return bool(get_settings().TENANT_IDENTITY_CATALOG_ENFORCEMENT_ENABLED)


def customers_orders_enforcement_enabled() -> bool:
    """Return the dedicated Wave 3 runtime gate (disabled by default)."""
    return bool(get_settings().TENANT_CUSTOMERS_ORDERS_ENFORCEMENT_ENABLED)


def operations_enforcement_enabled() -> bool:
    # Return the Wave 5 runtime gate (disabled by default).
    return bool(get_settings().TENANT_OPERATIONS_ENFORCEMENT_ENABLED)


def require_context_when_enabled(
    context: TenantContext | None,
    *,
    enabled: bool,
) -> TenantContext | None:
    if enabled and context is None:
        raise TenantContextMissing("Contexto de tenant obrigatorio para recurso isolado.")
    return context


def scope_query_to_tenant(
    query: QueryT,
    model: Any,
    context: TenantContext | None,
    *,
    enabled: bool,
) -> QueryT:
    """Apply an exact tenant predicate only after a route opts into isolation."""
    trusted = require_context_when_enabled(context, enabled=enabled)
    if not enabled:
        return query
    assert trusted is not None
    tenant_column = getattr(model, "tenant_id", None)
    if tenant_column is None:
        raise TypeError("Model sem ownership tenant_id nao pode ser isolado.")
    return query.filter(tenant_column == trusted.tenant_id)


def assign_tenant_on_create(
    resource: Any,
    context: TenantContext | None,
    *,
    enabled: bool,
) -> Any:
    """Assign ownership to a new object without overwriting existing ownership."""
    trusted = require_context_when_enabled(context, enabled=enabled)
    if not enabled:
        return resource
    assert trusted is not None
    if not hasattr(resource, "tenant_id"):
        raise TypeError("Recurso sem campo tenant_id nao pode receber ownership.")
    current = getattr(resource, "tenant_id")
    if current is not None:
        trusted.assert_tenant(current)
    else:
        setattr(resource, "tenant_id", trusted.tenant_id)
    return resource


def assert_resource_ownership(
    resource: Any,
    context: TenantContext | None,
    *,
    enabled: bool,
) -> None:
    """Fail closed for ID lookups after the calling route enables enforcement."""
    trusted = require_context_when_enabled(context, enabled=enabled)
    if enabled:
        assert trusted is not None
        trusted.assert_tenant(getattr(resource, "tenant_id", None))

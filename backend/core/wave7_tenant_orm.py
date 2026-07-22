"""Opt-in ownership helpers for Wave 7 backoffice models.

The schema/model expansion is not an authorization boundary. Callers must opt
in explicitly and pass a trusted TenantContext before reads or writes are
scoped. The gate is disabled by default and no route is enabled in this wave.
"""
from __future__ import annotations

import os
from typing import Any, TypeVar

from backend.core.tenant_context import TenantContext, TenantContextMissing


QueryT = TypeVar("QueryT")
WAVE7_ENV_FLAG = "MULTI_TENANT_WAVE7_ORM_ENABLED"


def wave7_orm_enabled() -> bool:
    return os.getenv(WAVE7_ENV_FLAG, "false").strip().lower() in {"1", "true", "yes", "on"}


def scope_wave7_query(query: QueryT, model: Any, context: TenantContext | None) -> QueryT:
    if not wave7_orm_enabled():
        return query
    if context is None:
        raise TenantContextMissing("Contexto de tenant obrigatorio para recurso da Wave 7.")
    tenant_column = getattr(model, "tenant_id", None)
    if tenant_column is None:
        raise TypeError("Model da Wave 7 sem campo tenant_id.")
    return query.filter(tenant_column == context.tenant_id)


def assign_wave7_tenant(resource: Any, context: TenantContext | None) -> Any:
    if not wave7_orm_enabled():
        return resource
    if context is None:
        raise TenantContextMissing("Contexto de tenant obrigatorio para recurso da Wave 7.")
    if not hasattr(resource, "tenant_id"):
        raise TypeError("Recurso da Wave 7 sem campo tenant_id.")
    current = getattr(resource, "tenant_id")
    if current is None:
        setattr(resource, "tenant_id", context.tenant_id)
    else:
        context.assert_tenant(current)
    return resource

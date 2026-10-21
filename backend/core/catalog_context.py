"""Explicit tenant ownership for the catalog, including single-store legacy mode."""
from backend.core.tenant_context import TenantContext, TenantSource
from backend.core.tenant_ownership import (
    identity_catalog_enforcement_enabled, require_context_when_enabled,
    scope_query_to_tenant, assign_tenant_on_create,
)

LEGACY_TENANT_ID = "tenant-legacy-default"


def catalog_tenant_context(context: TenantContext | None) -> TenantContext:
    require_context_when_enabled(context, enabled=identity_catalog_enforcement_enabled())
    return context or TenantContext(tenant_id=LEGACY_TENANT_ID, source=TenantSource.JOB)


def catalog_query(db, model, context: TenantContext | None):
    return scope_query_to_tenant(db.query(model), model, catalog_tenant_context(context), enabled=True)


def assign_catalog_tenant(resource, context: TenantContext | None):
    return assign_tenant_on_create(resource, catalog_tenant_context(context), enabled=True)

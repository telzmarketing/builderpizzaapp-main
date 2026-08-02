"""FastAPI dependencies for operation modules migrated behind the Wave 5 gate."""
from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.core.tenant_context import TenantContext, TenantSource
from backend.core.tenant_ownership import operations_enforcement_enabled, require_context_when_enabled
from backend.core.tenant_runtime import resolve_panel_tenant_context, resolve_public_tenant_context
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.admin_auth import get_current_admin


def panel_operation_context(request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)) -> TenantContext | None:
    context = resolve_panel_tenant_context(request, db, admin)
    return require_context_when_enabled(context, enabled=operations_enforcement_enabled())


def public_operation_context(request: Request, db: Session = Depends(get_db)) -> TenantContext | None:
    context = resolve_public_tenant_context(request, db)
    return require_context_when_enabled(context, enabled=operations_enforcement_enabled())


def operation_tenant_id(context: TenantContext | None) -> str:
    if context is not None and context.source == TenantSource.SUPPORT:
        return context.tenant_id
    if not operations_enforcement_enabled():
        return "default"
    trusted = require_context_when_enabled(context, enabled=True)
    assert trusted is not None
    return trusted.tenant_id

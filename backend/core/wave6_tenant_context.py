"""Tenant context helpers for Wave 6 marketing/CRM/engagement modules."""
from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.core.tenant_context import TenantContext, TenantSource
from backend.core.tenant_ownership import require_context_when_enabled
from backend.core.tenant_runtime import resolve_panel_tenant_context, resolve_public_tenant_context
from backend.core.wave6_tenant_orm import wave6_tenant_orm_enabled
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.admin_auth import get_current_admin

WAVE6_SESSION_TENANT_KEY = "wave6_tenant_context"


def bind_wave6_tenant_context(db: Session, context: TenantContext | None) -> TenantContext | None:
    """Bind a trusted Wave 6 context to the SQLAlchemy session for this request."""
    trusted = require_context_when_enabled(context, enabled=wave6_tenant_orm_enabled())
    if trusted is not None:
        db.info[WAVE6_SESSION_TENANT_KEY] = trusted
    return trusted


def panel_wave6_context(
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> TenantContext | None:
    context = resolve_panel_tenant_context(request, db, admin)
    return bind_wave6_tenant_context(db, context)


def public_wave6_context(
    request: Request,
    db: Session = Depends(get_db),
) -> TenantContext | None:
    context = resolve_public_tenant_context(request, db)
    return bind_wave6_tenant_context(db, context)


def wave6_tenant_id(context: TenantContext | None) -> str:
    if context is not None and context.source == TenantSource.SUPPORT:
        return context.tenant_id
    if not wave6_tenant_orm_enabled():
        # Compatibility mode still points at the seeded tenant.  The historic
        # literal ``default`` is not an ownership authority and was normalized
        # by the tenant backfills.
        return "tenant-legacy-default"
    trusted = require_context_when_enabled(context, enabled=True)
    assert trusted is not None
    return trusted.tenant_id

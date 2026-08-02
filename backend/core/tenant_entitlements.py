"""Reusable FastAPI dependencies for tenant license/module enforcement."""
from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.tenant_auth import get_current_tenant_context
from backend.core.tenant_context import TenantContext
from backend.core.tenant_runtime import resolve_panel_tenant_context
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.admin_auth import get_current_admin
from backend.services.tenant_entitlement_service import TenantEntitlementService


TENANT_MODULE_ROUTE_MAP = {
    "orders.write": "orders",
    "payments.write": "payments",
}


def require_tenant_license(*, write: bool = False):
    def dependency(
        context: TenantContext = Depends(get_current_tenant_context),
        db: Session = Depends(get_db),
    ):
        return TenantEntitlementService(db).require_tenant_access(context.tenant_id, write=write)
    return dependency


def require_tenant_module(module_key: str, *, write: bool = False):
    if not module_key.strip():
        raise ValueError("module_key e obrigatoria")

    def dependency(
        context: TenantContext = Depends(get_current_tenant_context),
        db: Session = Depends(get_db),
    ):
        return TenantEntitlementService(db).require_module(
            context.tenant_id, module_key.strip(), write=write
        )
    return dependency


def require_operational_entitlement(capability: str, *, write: bool = False):
    """Preserve legacy behavior while the explicit entitlement gate is disabled."""
    module_key = TENANT_MODULE_ROUTE_MAP.get(capability)
    if module_key is None:
        raise ValueError(f"Capability sem mapeamento estavel: {capability}")

    def dependency(
        request: Request,
        db: Session = Depends(get_db),
        admin: AdminUser = Depends(get_current_admin),
    ):
        if not get_settings().TENANT_ENTITLEMENT_ENFORCEMENT_ENABLED:
            return None
        context = resolve_panel_tenant_context(request, db, admin)
        if context is None:
            from backend.services.tenant_entitlement_service import TenantAccessDenied
            raise TenantAccessDenied(
                "Contexto multiempresa obrigatorio quando entitlement esta habilitado.",
                code="TenantEntitlementContextRequired",
            )
        return TenantEntitlementService(db).require_module(
            context.tenant_id, module_key, write=write
        )

    return dependency

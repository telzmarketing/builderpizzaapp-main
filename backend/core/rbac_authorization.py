"""Fail-closed tenant RBAC dependencies for operational APIs."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.core.tenant_runtime import resolve_panel_tenant_context
from backend.core.tenant_context import TenantContext, TenantSource
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.models.membership import TenantMembership
from backend.models.rbac import RbacModule, RbacPermission, Role, RolePermission, UserPermission
from backend.routes.admin_auth import get_current_admin


LEGACY_TENANT_ID = "tenant-legacy-default"


@dataclass(frozen=True, slots=True)
class AuthorizedTenantActor:
    tenant_id: str
    user_id: str
    user_name: str
    tenant_context: TenantContext


def require_rbac_permission(module_key: str, permission_key: str):
    def dependency(
        request: Request,
        db: Session = Depends(get_db),
        admin: AdminUser = Depends(get_current_admin),
    ) -> AuthorizedTenantActor:
        context = resolve_panel_tenant_context(request, db, admin)
        tenant_id = context.tenant_id if context is not None else LEGACY_TENANT_ID
        trusted_context = context or TenantContext(tenant_id=tenant_id, source=TenantSource.JOB)

        membership = db.query(TenantMembership).filter(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.user_id == admin.id,
            TenantMembership.status == "active",
        ).first()
        role = db.query(Role).filter(
            Role.id == admin.role_id,
            Role.tenant_id == tenant_id,
        ).first() if admin.role_id else None
        is_owner = membership is not None and membership.role == "owner"
        is_legacy_master = context is None and (
            admin.role_id is None or (role is not None and role.name.lower() == "master")
        )
        if not (is_owner or is_legacy_master):
            station_module = {
                "cozinha": "cozinha", "expedicao": "expedicao",
            }.get(role.name.strip().lower() if role else "")
            if station_module is not None and module_key != station_module:
                raise HTTPException(status_code=403, detail="Conta KDS restrita a sua propria estacao.")
            module = db.query(RbacModule).filter(
                RbacModule.key == module_key,
                RbacModule.is_active.is_(True),
            ).first()
            permission = db.query(RbacPermission).filter(
                RbacPermission.key == permission_key
            ).first()
            if module is None or permission is None:
                raise HTTPException(status_code=403, detail="Permissao operacional indisponivel.")

            override = db.query(UserPermission).filter(
                UserPermission.tenant_id == tenant_id,
                UserPermission.user_id == admin.id,
                UserPermission.module_id == module.id,
                UserPermission.permission_id == permission.id,
                UserPermission.overrides_role.is_(True),
            ).first()
            # Positive user overrides cannot widen a system KDS role. Negative
            # overrides still allow an owner to revoke an action explicitly.
            if override is not None and (station_module is None or not override.allowed):
                allowed = bool(override.allowed)
            else:
                allowed = role is not None and db.query(RolePermission.id).filter(
                    RolePermission.tenant_id == tenant_id,
                    RolePermission.role_id == role.id,
                    RolePermission.module_id == module.id,
                    RolePermission.permission_id == permission.id,
                    RolePermission.allowed.is_(True),
                ).first() is not None
            if not allowed:
                raise HTTPException(status_code=403, detail="Permissao insuficiente para esta estacao KDS.")

        return AuthorizedTenantActor(
            tenant_id=tenant_id,
            user_id=admin.id,
            user_name=admin.name,
            tenant_context=trusted_context,
        )

    return dependency

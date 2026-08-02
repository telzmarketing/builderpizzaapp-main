"""
RBAC — Roles, Modules, Permissions, Audit Logs.

Endpoints
---------
GET    /admin/roles
POST   /admin/roles
PUT    /admin/roles/{role_id}
DELETE /admin/roles/{role_id}
POST   /admin/roles/{role_id}/duplicate

GET    /admin/modules
GET    /admin/permissions

GET    /admin/roles/{role_id}/permissions
PUT    /admin/roles/{role_id}/permissions

GET    /admin/users/{user_id}/permissions
PUT    /admin/users/{user_id}/permissions

GET    /admin/audit-logs
GET    /admin/auth/me/permissions      (effective permissions for current session)
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from backend.core.response import ok, created
from backend.core.tenant_runtime import resolve_panel_tenant_context
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.models.membership import TenantMembership
from backend.models.rbac import (
    AdminAuditLog, RbacModule, RbacPermission, Role,
    RolePermission, UserPermission,
)
from backend.routes.admin_auth import get_current_admin
from backend.schemas.rbac import (
    AuditLogOut, EffectivePermissions, ModuleOut, PermissionOut,
    RoleCreate, RoleOut, RolePermissionsUpdate, RoleUpdate, UserPermissionsUpdate,
)

router = APIRouter(prefix="/admin", tags=["rbac"])

ALL_PERM_KEYS = {"view", "create", "edit", "delete", "approve", "export", "manage"}
LEGACY_TENANT_ID = "tenant-legacy-default"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class _TenantScope:
    tenant_id: str
    enforced: bool


def _tenant_scope(request: Request, db: Session, user: AdminUser) -> _TenantScope:
    context = resolve_panel_tenant_context(request, db, user)
    if context is None:
        return _TenantScope(tenant_id=LEGACY_TENANT_ID, enforced=False)
    return _TenantScope(tenant_id=context.tenant_id, enforced=True)


def _scoped_query(query, model, scope: _TenantScope):
    if scope.enforced:
        return query.filter(model.tenant_id == scope.tenant_id)
    return query


def _role_query(db: Session, scope: _TenantScope):
    return _scoped_query(db.query(Role), Role, scope)


def _tenant_user_query(db: Session, scope: _TenantScope):
    query = db.query(AdminUser)
    if scope.enforced:
        query = query.join(
            TenantMembership,
            TenantMembership.user_id == AdminUser.id,
        ).filter(
            TenantMembership.tenant_id == scope.tenant_id,
            TenantMembership.status != "revoked",
        )
    return query


def _role_user_count(
    db: Session,
    role_id: str,
    scope: _TenantScope,
    *,
    active_only: bool = True,
) -> int:
    query = db.query(AdminUser).filter(AdminUser.role_id == role_id)
    if active_only:
        query = query.filter(AdminUser.active == True)  # noqa: E712
    if scope.enforced:
        query = query.join(
            TenantMembership,
            TenantMembership.user_id == AdminUser.id,
        ).filter(
            TenantMembership.tenant_id == scope.tenant_id,
        )
        if active_only:
            query = query.filter(TenantMembership.status == "active")
        else:
            query = query.filter(TenantMembership.status != "revoked")
    return query.count()


def _is_master(user: AdminUser, db: Session, scope: _TenantScope) -> bool:
    """Resolve tenant management independently from platform authorization."""
    if scope.enforced:
        membership = db.query(TenantMembership).filter(
            TenantMembership.user_id == user.id,
            TenantMembership.tenant_id == scope.tenant_id,
            TenantMembership.status == "active",
        ).first()
        if membership is None:
            return False
        if membership.role == "owner":
            return True
    if not user.role_id:
        return not scope.enforced
    role = _role_query(db, scope).filter(Role.id == user.role_id).first()
    return role is not None and role.name.lower() == "master"


def _effective_permissions(
    user: AdminUser,
    db: Session,
    scope: _TenantScope,
) -> EffectivePermissions:
    """Compute effective permission map for the given user."""
    if _is_master(user, db, scope):
        modules = db.query(RbacModule).filter(RbacModule.is_active == True).all()  # noqa: E712
        perms   = db.query(RbacPermission).all()
        return EffectivePermissions(
            is_master=True,
            role_id=user.role_id,
            role_name="master",
            modules={m.key: {p.key: True for p in perms} for m in modules},
        )

    # Collect role permissions
    perm_map: dict[str, dict[str, bool]] = {}

    if user.role_id:
        role_permissions = db.query(
            RolePermission, RbacModule, RbacPermission
        )
        if scope.enforced:
            role_permissions = role_permissions.filter(
                RolePermission.tenant_id == scope.tenant_id
            )
        rows = (
            role_permissions
            .join(RbacModule, RolePermission.module_id == RbacModule.id)
            .join(RbacPermission, RolePermission.permission_id == RbacPermission.id)
            .filter(RolePermission.role_id == user.role_id)
            .all()
        )
        for rp, mod, perm in rows:
            perm_map.setdefault(mod.key, {})[perm.key] = rp.allowed

    # Apply user-level overrides
    user_permissions = db.query(
        UserPermission, RbacModule, RbacPermission
    )
    if scope.enforced:
        user_permissions = user_permissions.filter(
            UserPermission.tenant_id == scope.tenant_id
        )
    overrides = (
        user_permissions
        .join(RbacModule, UserPermission.module_id == RbacModule.id)
        .join(RbacPermission, UserPermission.permission_id == RbacPermission.id)
        .filter(UserPermission.user_id == user.id, UserPermission.overrides_role == True)  # noqa: E712
        .all()
    )
    for up, mod, perm in overrides:
        perm_map.setdefault(mod.key, {})[perm.key] = up.allowed

    role = (
        _role_query(db, scope).filter(Role.id == user.role_id).first()
        if user.role_id
        else None
    )

    return EffectivePermissions(
        is_master=False,
        role_id=user.role_id,
        role_name=role.name if role else None,
        modules=perm_map,
    )


def _require_master(user: AdminUser, db: Session, scope: _TenantScope) -> None:
    if not _is_master(user, db, scope):
        raise HTTPException(403, "Acesso restrito a usuários master.")


def _log(db: Session, user: AdminUser, action: str, module_key: str,
         entity_type: str, entity_id: str,
         old_val: Optional[str] = None, new_val: Optional[str] = None,
         request: Optional[Request] = None,
         tenant_id: str = LEGACY_TENANT_ID) -> None:
    ip = None
    ua = None
    if request:
        ip = request.client.host if request.client else None
        ua = request.headers.get("user-agent")
    db.add(AdminAuditLog(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=user.id,
        user_name=user.name,
        action=action,
        module_key=module_key,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_val,
        new_value=new_val,
        ip_address=ip,
        user_agent=ua,
        created_at=_now(),
    ))


# ── Effective permissions for current session ──────────────────────────────────

@router.get("/auth/me/permissions")
def me_permissions(
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    return ok(_effective_permissions(current, db, scope).model_dump())


# ── Roles ─────────────────────────────────────────────────────────────────────

@router.get("/roles")
def list_roles(
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    _require_master(current, db, scope)
    roles = _role_query(db, scope).order_by(Role.created_at).all()
    # Enrich with user count
    result = []
    for r in roles:
        rd = RoleOut.model_validate(r).model_dump()
        rd["user_count"] = _role_user_count(db, r.id, scope)
        result.append(rd)
    return ok(result)


@router.post("/roles")
def create_role(
    body: RoleCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    _require_master(current, db, scope)
    tenant_id = scope.tenant_id
    if _role_query(db, scope).filter(Role.name == body.name).first():
        raise HTTPException(400, "Já existe um perfil com esse nome.")
    role = Role(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=body.name,
        description=body.description,
        is_system=False,
    )
    db.add(role)
    db.flush()
    _log(
        db, current, "create", "usuarios", "role", role.id,
        new_val=body.name, request=request, tenant_id=tenant_id,
    )
    db.commit()
    db.refresh(role)
    return created(RoleOut.model_validate(role), "Perfil criado.")


@router.put("/roles/{role_id}")
def update_role(
    role_id: str,
    body: RoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    _require_master(current, db, scope)
    tenant_id = scope.tenant_id
    role = _role_query(db, scope).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(404, "Perfil não encontrado.")
    if role.is_system and body.name and body.name != role.name:
        raise HTTPException(400, "Não é possível renomear perfis do sistema.")
    old = role.name
    if body.name is not None:
        if _role_query(db, scope).filter(
            Role.name == body.name, Role.id != role_id
        ).first():
            raise HTTPException(400, "Nome já em uso por outro perfil.")
        role.name = body.name
    if body.description is not None:
        role.description = body.description
    _log(
        db, current, "update", "usuarios", "role", role_id,
        old_val=old, new_val=role.name, request=request, tenant_id=tenant_id,
    )
    db.commit()
    db.refresh(role)
    return ok(RoleOut.model_validate(role), "Perfil atualizado.")


@router.delete("/roles/{role_id}")
def delete_role(
    role_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    _require_master(current, db, scope)
    tenant_id = scope.tenant_id
    role = _role_query(db, scope).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(404, "Perfil não encontrado.")
    if role.is_system:
        raise HTTPException(400, "Perfis do sistema não podem ser excluídos.")
    users_with_role = _role_user_count(
        db, role_id, scope, active_only=False
    )
    if users_with_role > 0:
        raise HTTPException(400, f"Não é possível excluir: {users_with_role} usuário(s) vinculado(s) a este perfil.")
    _log(
        db, current, "delete", "usuarios", "role", role_id,
        old_val=role.name, request=request, tenant_id=tenant_id,
    )
    db.delete(role)
    db.commit()
    return ok(None, "Perfil excluído.")


@router.post("/roles/{role_id}/duplicate")
def duplicate_role(
    role_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    _require_master(current, db, scope)
    tenant_id = scope.tenant_id
    source = _role_query(db, scope).filter(Role.id == role_id).first()
    if not source:
        raise HTTPException(404, "Perfil não encontrado.")
    new_name = f"Cópia de {source.name}"
    counter = 1
    while _role_query(db, scope).filter(Role.name == new_name).first():
        counter += 1
        new_name = f"Cópia de {source.name} ({counter})"
    new_role = Role(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=new_name,
        description=source.description,
        is_system=False,
    )
    db.add(new_role)
    db.flush()
    # Copy permissions
    src_perms = _scoped_query(
        db.query(RolePermission), RolePermission, scope
    ).filter(RolePermission.role_id == role_id).all()
    for sp in src_perms:
        db.add(RolePermission(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            role_id=new_role.id,
            module_id=sp.module_id,
            permission_id=sp.permission_id,
            allowed=sp.allowed,
        ))
    _log(
        db, current, "create", "usuarios", "role", new_role.id,
        new_val=new_name, request=request, tenant_id=tenant_id,
    )
    db.commit()
    db.refresh(new_role)
    return created(RoleOut.model_validate(new_role), "Perfil duplicado.")


# ── Modules & Permissions ──────────────────────────────────────────────────────

@router.get("/modules")
def list_modules(
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    _require_master(current, db, scope)
    mods = db.query(RbacModule).order_by(RbacModule.order_index).all()
    return ok([ModuleOut.model_validate(m) for m in mods])


@router.get("/permissions")
def list_permissions(
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    _require_master(current, db, scope)
    perms = db.query(RbacPermission).all()
    return ok([PermissionOut.model_validate(p) for p in perms])


# ── Role permission matrix ────────────────────────────────────────────────────

@router.get("/roles/{role_id}/permissions")
def get_role_permissions(
    role_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    _require_master(current, db, scope)
    role = _role_query(db, scope).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(404, "Perfil não encontrado.")
    rows = _scoped_query(
        db.query(RolePermission), RolePermission, scope
    ).filter(RolePermission.role_id == role_id).all()
    return ok([{"module_id": r.module_id, "permission_id": r.permission_id, "allowed": r.allowed} for r in rows])


@router.put("/roles/{role_id}/permissions")
def update_role_permissions(
    role_id: str,
    body: RolePermissionsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    _require_master(current, db, scope)
    tenant_id = scope.tenant_id
    role = _role_query(db, scope).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(404, "Perfil não encontrado.")
    role_permissions = _scoped_query(
        db.query(RolePermission), RolePermission, scope
    )
    old_rows = role_permissions.filter(RolePermission.role_id == role_id).all()
    old_repr = json.dumps([{"m": r.module_id, "p": r.permission_id, "a": r.allowed} for r in old_rows], sort_keys=True)
    # Replace all permissions for this role
    role_permissions.filter(RolePermission.role_id == role_id).delete(
        synchronize_session=False
    )
    for entry in body.permissions:
        db.add(RolePermission(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            role_id=role_id,
            module_id=entry.module_id,
            permission_id=entry.permission_id,
            allowed=entry.allowed,
        ))
    new_repr = json.dumps([{"m": e.module_id, "p": e.permission_id, "a": e.allowed} for e in body.permissions], sort_keys=True)
    _log(db, current, "update_permissions", "usuarios", "role", role_id,
         old_val=old_repr, new_val=new_repr, request=request, tenant_id=tenant_id)
    db.commit()
    return ok(None, "Permissões do perfil atualizadas.")


# ── User permission overrides ─────────────────────────────────────────────────

@router.get("/users/{user_id}/permissions")
def get_user_permissions(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    _require_master(current, db, scope)
    user = _tenant_user_query(db, scope).filter(AdminUser.id == user_id).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado.")
    rows = _scoped_query(
        db.query(UserPermission), UserPermission, scope
    ).filter(UserPermission.user_id == user_id).all()
    return ok([{"module_id": r.module_id, "permission_id": r.permission_id,
                "allowed": r.allowed, "overrides_role": r.overrides_role} for r in rows])


@router.put("/users/{user_id}/permissions")
def update_user_permissions(
    user_id: str,
    body: UserPermissionsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    _require_master(current, db, scope)
    tenant_id = scope.tenant_id
    user = _tenant_user_query(db, scope).filter(AdminUser.id == user_id).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado.")
    _scoped_query(db.query(UserPermission), UserPermission, scope).filter(
        UserPermission.user_id == user_id
    ).delete(synchronize_session=False)
    for entry in body.permissions:
        db.add(UserPermission(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            user_id=user_id,
            module_id=entry.module_id,
            permission_id=entry.permission_id,
            allowed=entry.allowed,
            overrides_role=True,
        ))
    _log(
        db, current, "update_permissions", "usuarios", "admin_user", user_id,
        request=request, tenant_id=tenant_id,
    )
    db.commit()
    return ok(None, "Permissões individuais atualizadas.")


# ── Audit logs ────────────────────────────────────────────────────────────────

@router.get("/audit-logs")
def list_audit_logs(
    request: Request,
    user_id: Optional[str] = Query(None),
    module_key: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    _require_master(current, db, scope)
    q = _scoped_query(db.query(AdminAuditLog), AdminAuditLog, scope)
    if user_id:
        q = q.filter(AdminAuditLog.user_id == user_id)
    if module_key:
        q = q.filter(AdminAuditLog.module_key == module_key)
    if action:
        q = q.filter(AdminAuditLog.action == action)
    total = q.count()
    logs = q.order_by(AdminAuditLog.created_at.desc()).offset(offset).limit(limit).all()
    return ok({
        "total": total,
        "items": [AuditLogOut.model_validate(l) for l in logs],
    })

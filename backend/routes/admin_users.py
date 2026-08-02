"""Admin user management — CRUD for admin_users table (with RBAC fields)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from backend.core.response import ok, created
from backend.core.security import hash_password
from backend.core.tenant_runtime import resolve_panel_tenant_context
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.models.membership import TenantMembership
from backend.models.rbac import AdminAuditLog, Role
from backend.routes.admin_auth import get_current_admin
from backend.schemas.admin import AdminOut

router = APIRouter(prefix="/admin/users", tags=["admin-users"])
LEGACY_TENANT_ID = "tenant-legacy-default"


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


def _role_query(db: Session, scope: _TenantScope):
    query = db.query(Role)
    if scope.enforced:
        query = query.filter(Role.tenant_id == scope.tenant_id)
    return query


def _tenant_user_rows(db: Session, scope: _TenantScope):
    if not scope.enforced:
        return [(user, None) for user in db.query(AdminUser).order_by(
            AdminUser.created_at
        ).all()]
    return (
        db.query(AdminUser, TenantMembership)
        .join(TenantMembership, TenantMembership.user_id == AdminUser.id)
        .filter(
            TenantMembership.tenant_id == scope.tenant_id,
            TenantMembership.status != "revoked",
        )
        .order_by(AdminUser.created_at)
        .all()
    )


def _target_user(
    db: Session,
    user_id: str,
    scope: _TenantScope,
) -> tuple[AdminUser, TenantMembership | None] | None:
    if not scope.enforced:
        user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
        return (user, None) if user is not None else None
    return (
        db.query(AdminUser, TenantMembership)
        .join(TenantMembership, TenantMembership.user_id == AdminUser.id)
        .filter(
            AdminUser.id == user_id,
            TenantMembership.tenant_id == scope.tenant_id,
            TenantMembership.status != "revoked",
        )
        .first()
    )


def _require_tenant_owned_identity(
    db: Session,
    user_id: str,
    scope: _TenantScope,
) -> None:
    foreign_membership = db.query(TenantMembership.id).filter(
        TenantMembership.user_id == user_id,
        TenantMembership.tenant_id != scope.tenant_id,
        TenantMembership.status != "revoked",
    ).first()
    if foreign_membership is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Usuario possui vinculo nao revogado com outra empresa; dados "
                "globais da identidade nao podem ser alterados por este tenant."
            ),
        )


def _membership_role(role: Role | None) -> str:
    if role is None:
        return "viewer"
    name = role.name.strip().lower()
    if name in {"master", "administrador", "admin"}:
        return "admin"
    if name in {"gerente", "manager"}:
        return "manager"
    return "operator"


def _protect_owner_membership(
    membership: TenantMembership | None,
    *,
    role_change: bool = False,
    status_change: bool = False,
) -> None:
    if membership is None or membership.role != "owner":
        return
    if role_change:
        raise HTTPException(
            status_code=409,
            detail="Owner deve ser alterado somente pelo fluxo de transferencia de propriedade.",
        )
    if status_change:
        raise HTTPException(
            status_code=409,
            detail="Owner nao pode ser desativado ou removido sem transferir a propriedade.",
        )


def _admin_data(
    user: AdminUser,
    membership: TenantMembership | None = None,
) -> dict:
    data = AdminOut.model_validate(user).model_dump()
    if membership is not None:
        data["active"] = bool(user.active and membership.status == "active")
    return data


def _set_membership_active(
    db: Session,
    user: AdminUser,
    membership: TenantMembership,
    active: bool,
) -> None:
    other_active = db.query(TenantMembership.id).filter(
        TenantMembership.user_id == user.id,
        TenantMembership.id != membership.id,
        TenantMembership.status == "active",
    ).count()
    if active and other_active > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "Usuario ja possui outra membership ativa; o RBAC global nao "
                "permite ativar duas empresas simultaneamente."
            ),
        )
    membership.status = "active" if active else "suspended"
    membership.updated_at = _now()
    if active:
        user.active = True
        return
    if other_active == 0:
        user.active = False


def _log(db: Session, actor: AdminUser, action: str, target_id: str,
         old_val: Optional[str] = None, new_val: Optional[str] = None,
         request: Optional[Request] = None,
         tenant_id: str = LEGACY_TENANT_ID) -> None:
    ip = request.client.host if request and request.client else None
    ua = request.headers.get("user-agent") if request else None
    db.add(AdminAuditLog(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        user_id=actor.id,
        user_name=actor.name,
        action=action,
        module_key="usuarios",
        entity_type="admin_user",
        entity_id=target_id,
        old_value=old_val,
        new_value=new_val,
        ip_address=ip,
        user_agent=ua,
        created_at=_now(),
    ))


# ── Schemas ───────────────────────────────────────────────────────────────────

def _is_master(user: AdminUser, db: Session, scope: _TenantScope) -> bool:
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


def _require_master(user: AdminUser, db: Session, scope: _TenantScope) -> None:
    if not _is_master(user, db, scope):
        raise HTTPException(403, "Acesso restrito a usuarios master.")


class AdminUserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    active: bool = True
    phone: Optional[str] = None
    role_id: Optional[str] = None
    store_id: Optional[str] = None

    @field_validator("password")
    @classmethod
    def bcrypt_safe_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Senha excede o limite seguro de 72 bytes.")
        return value


class AdminUserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=72)
    phone: Optional[str] = None
    role_id: Optional[str] = None
    store_id: Optional[str] = None

    @field_validator("password")
    @classmethod
    def bcrypt_safe_password(cls, value: str | None) -> str | None:
        if value is not None and len(value.encode("utf-8")) > 72:
            raise ValueError("Senha excede o limite seguro de 72 bytes.")
        return value


class ResetPasswordIn(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=72)

    @field_validator("new_password")
    @classmethod
    def bcrypt_safe_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Senha excede o limite seguro de 72 bytes.")
        return value


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("")
def list_admin_users(
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    _require_master(current, db, scope)
    users = _tenant_user_rows(db, scope)
    result = []
    for u, membership in users:
        ud = _admin_data(u, membership)
        # Enrich with role name
        if u.role_id:
            role = _role_query(db, scope).filter(Role.id == u.role_id).first()
            ud["role_name"] = role.name if role else None
        else:
            ud["role_name"] = "Master" if not scope.enforced else None
        result.append(ud)
    return ok(result)


@router.post("")
def create_admin_user(
    body: AdminUserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    _require_master(current, db, scope)
    if db.query(AdminUser).filter(AdminUser.email == body.email.lower().strip()).first():
        raise HTTPException(400, "E-mail já cadastrado.")
    role = (
        _role_query(db, scope).filter(Role.id == body.role_id).first()
        if body.role_id
        else None
    )
    if body.role_id and role is None:
        raise HTTPException(400, "Perfil não encontrado.")
    user = AdminUser(
        id=str(uuid.uuid4()),
        name=body.name,
        email=body.email.lower().strip(),
        password_hash=hash_password(body.password),
        active=body.active,
        phone=body.phone,
        role_id=body.role_id,
        store_id=body.store_id,
        created_by=current.id,
        updated_by=current.id,
    )
    db.add(user)
    db.flush()
    if scope.enforced:
        db.add(TenantMembership(
            id=str(uuid.uuid4()),
            tenant_id=scope.tenant_id,
            user_id=user.id,
            role=_membership_role(role),
            status="active" if body.active else "suspended",
            is_default=bool(body.active),
            invited_by=current.id,
            joined_at=_now() if body.active else None,
        ))
    _log(
        db,
        current,
        "create",
        user.id,
        new_val=user.email,
        request=request,
        tenant_id=scope.tenant_id,
    )
    db.commit()
    db.refresh(user)
    return created(AdminOut.model_validate(user), "Usuário criado com sucesso.")


@router.put("/{user_id}")
def update_admin_user(
    user_id: str,
    body: AdminUserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    _require_master(current, db, scope)
    target = _target_user(db, user_id, scope)
    if target is None:
        raise HTTPException(404, "Usuario nao encontrado.")
    user, membership = target
    _protect_owner_membership(
        membership,
        role_change=body.role_id is not None,
        status_change=body.active is False,
    )
    identity_change = any(
        value is not None
        for value in (
            body.name,
            body.email,
            body.password,
            body.phone,
            body.role_id,
            body.store_id,
        )
    )
    if scope.enforced and (identity_change or body.active is not None):
        _require_tenant_owned_identity(db, user.id, scope)
    if not user:
        raise HTTPException(404, "Usuário não encontrado.")
    old_repr = user.email

    if body.name is not None:
        user.name = body.name
    if body.email is not None:
        existing = db.query(AdminUser).filter(
            AdminUser.email == body.email.lower().strip(), AdminUser.id != user_id
        ).first()
        if existing:
            raise HTTPException(400, "E-mail já em uso.")
        user.email = body.email.lower().strip()
    if body.active is not None:
        if user_id == current.id and not body.active:
            raise HTTPException(400, "Você não pode desativar sua própria conta.")
        if membership is not None:
            _set_membership_active(db, user, membership, body.active)
        else:
            user.active = body.active
    if body.password is not None:
        user.password_hash = hash_password(body.password)
        user.auth_version = int(getattr(user, "auth_version", 0) or 0) + 1
    if body.phone is not None:
        user.phone = body.phone
    if body.role_id is not None:
        role = (
            _role_query(db, scope).filter(Role.id == body.role_id).first()
            if body.role_id
            else None
        )
        if body.role_id and role is None:
            raise HTTPException(400, "Perfil não encontrado.")
        user.role_id = body.role_id or None
        if membership is not None:
            membership.role = _membership_role(role)
            membership.updated_at = _now()
    if body.store_id is not None:
        user.store_id = body.store_id or None

    user.updated_by = current.id
    _log(
        db, current, "update", user_id,
        old_val=old_repr, new_val=user.email, request=request,
        tenant_id=scope.tenant_id,
    )
    db.commit()
    db.refresh(user)
    return ok(_admin_data(user, membership), "Usuário atualizado.")


@router.patch("/{user_id}/status")
def toggle_user_status(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    _require_master(current, db, scope)
    target = _target_user(db, user_id, scope)
    if target is None:
        raise HTTPException(404, "Usuário não encontrado.")
    user, membership = target
    _protect_owner_membership(membership, status_change=True)
    if user_id == current.id:
        raise HTTPException(400, "Você não pode alterar o próprio status.")
    if scope.enforced:
        _require_tenant_owned_identity(db, user.id, scope)
    was_active = bool(
        user.active
        and (membership is None or membership.status == "active")
    )
    old = "ativo" if was_active else "inativo"
    if membership is not None:
        _set_membership_active(db, user, membership, not was_active)
    else:
        user.active = not user.active
    is_active = bool(
        user.active
        and (membership is None or membership.status == "active")
    )
    user.updated_by = current.id
    _log(db, current, "toggle_status", user_id, old_val=old,
         new_val="ativo" if is_active else "inativo", request=request,
         tenant_id=scope.tenant_id)
    db.commit()
    db.refresh(user)
    return ok(_admin_data(user, membership), f"Usuário {'ativado' if is_active else 'desativado'}.")


@router.patch("/{user_id}/reset-password")
def reset_password(
    user_id: str,
    body: ResetPasswordIn,
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    _require_master(current, db, scope)
    target = _target_user(db, user_id, scope)
    if target is None:
        raise HTTPException(404, "Usuário não encontrado.")
    user, _membership = target
    if scope.enforced:
        _require_tenant_owned_identity(db, user.id, scope)
    user.password_hash = hash_password(body.new_password)
    user.auth_version = int(getattr(user, "auth_version", 0) or 0) + 1
    user.updated_by = current.id
    _log(
        db, current, "reset_password", user_id, request=request,
        tenant_id=scope.tenant_id,
    )
    db.commit()
    return ok(None, "Senha redefinida com sucesso.")


@router.delete("/{user_id}")
def delete_admin_user(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    scope = _tenant_scope(request, db, current)
    _require_master(current, db, scope)
    if user_id == current.id:
        raise HTTPException(400, "Você não pode excluir sua própria conta.")
    target = _target_user(db, user_id, scope)
    if target is None:
        raise HTTPException(404, "Usuário não encontrado.")
    user, membership = target
    _protect_owner_membership(membership, status_change=True)
    if scope.enforced:
        _require_tenant_owned_identity(db, user.id, scope)
    old_email = user.email
    action = "deactivate"
    if membership is not None:
        _set_membership_active(db, user, membership, False)
        membership.status = "revoked"
        membership.is_default = False
        membership.updated_at = _now()
        action = "revoke_membership"
    else:
        user.active = False
    user.updated_by = current.id
    _log(
        db, current, action, user_id,
        old_val=old_email, request=request, tenant_id=scope.tenant_id,
    )
    db.commit()
    return ok(None, "Usuário desativado.")

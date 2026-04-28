"""Admin user management — CRUD for admin_users table (with RBAC fields)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from backend.core.response import ok, created
from backend.core.security import hash_password
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.models.rbac import AdminAuditLog, Role
from backend.routes.admin_auth import get_current_admin
from backend.schemas.admin import AdminOut

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _log(db: Session, actor: AdminUser, action: str, target_id: str,
         old_val: Optional[str] = None, new_val: Optional[str] = None,
         request: Optional[Request] = None) -> None:
    ip = request.client.host if request and request.client else None
    ua = request.headers.get("user-agent") if request else None
    db.add(AdminAuditLog(
        id=str(uuid.uuid4()),
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

class AdminUserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(..., min_length=8)
    active: bool = True
    phone: Optional[str] = None
    role_id: Optional[str] = None
    store_id: Optional[str] = None


class AdminUserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8)
    phone: Optional[str] = None
    role_id: Optional[str] = None
    store_id: Optional[str] = None


class ResetPasswordIn(BaseModel):
    new_password: str = Field(..., min_length=8)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("")
def list_admin_users(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    users = db.query(AdminUser).order_by(AdminUser.created_at).all()
    result = []
    for u in users:
        ud = AdminOut.model_validate(u).model_dump()
        # Enrich with role name
        if u.role_id:
            role = db.query(Role).filter(Role.id == u.role_id).first()
            ud["role_name"] = role.name if role else None
        else:
            ud["role_name"] = "Master"  # legacy: no role = full access
        result.append(ud)
    return ok(result)


@router.post("")
def create_admin_user(
    body: AdminUserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    if db.query(AdminUser).filter(AdminUser.email == body.email.lower().strip()).first():
        raise HTTPException(400, "E-mail já cadastrado.")
    if body.role_id and not db.query(Role).filter(Role.id == body.role_id).first():
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
    _log(db, current, "create", user.id, new_val=user.email, request=request)
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
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
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
        user.active = body.active
    if body.password is not None:
        user.password_hash = hash_password(body.password)
    if body.phone is not None:
        user.phone = body.phone
    if body.role_id is not None:
        if body.role_id and not db.query(Role).filter(Role.id == body.role_id).first():
            raise HTTPException(400, "Perfil não encontrado.")
        user.role_id = body.role_id or None
    if body.store_id is not None:
        user.store_id = body.store_id or None

    user.updated_by = current.id
    _log(db, current, "update", user_id, old_val=old_repr, new_val=user.email, request=request)
    db.commit()
    db.refresh(user)
    return ok(AdminOut.model_validate(user), "Usuário atualizado.")


@router.patch("/{user_id}/status")
def toggle_user_status(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado.")
    if user_id == current.id:
        raise HTTPException(400, "Você não pode alterar o próprio status.")
    old = "ativo" if user.active else "inativo"
    user.active = not user.active
    user.updated_by = current.id
    _log(db, current, "toggle_status", user_id, old_val=old,
         new_val="ativo" if user.active else "inativo", request=request)
    db.commit()
    db.refresh(user)
    return ok(AdminOut.model_validate(user), f"Usuário {'ativado' if user.active else 'desativado'}.")


@router.patch("/{user_id}/reset-password")
def reset_password(
    user_id: str,
    body: ResetPasswordIn,
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado.")
    user.password_hash = hash_password(body.new_password)
    user.updated_by = current.id
    _log(db, current, "reset_password", user_id, request=request)
    db.commit()
    return ok(None, "Senha redefinida com sucesso.")


@router.delete("/{user_id}")
def delete_admin_user(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    if user_id == current.id:
        raise HTTPException(400, "Você não pode excluir sua própria conta.")
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado.")
    old_email = user.email
    user.active = False
    user.updated_by = current.id
    _log(db, current, "deactivate", user_id, old_val=old_email, request=request)
    db.commit()
    return ok(None, "Usuário desativado.")

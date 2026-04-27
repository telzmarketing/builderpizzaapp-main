"""Admin user management — CRUD for admin_users table."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from backend.core.response import ok, created
from backend.core.security import hash_password
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.admin_auth import get_current_admin
from backend.schemas.admin import AdminOut

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


class AdminUserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(..., min_length=8)
    active: bool = True


class AdminUserUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    active: bool | None = None
    password: str | None = Field(default=None, min_length=8)


@router.get("", response_model=None)
def list_admin_users(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    users = db.query(AdminUser).order_by(AdminUser.created_at).all()
    return ok([AdminOut.model_validate(u) for u in users])


@router.post("", response_model=None)
def create_admin_user(body: AdminUserCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    if db.query(AdminUser).filter(AdminUser.email == body.email.lower().strip()).first():
        raise HTTPException(400, "E-mail já cadastrado.")
    user = AdminUser(
        id=str(uuid.uuid4()),
        name=body.name,
        email=body.email.lower().strip(),
        password_hash=hash_password(body.password),
        active=body.active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return created(AdminOut.model_validate(user), "Usuário criado com sucesso.")


@router.put("/{user_id}", response_model=None)
def update_admin_user(
    user_id: str,
    body: AdminUserUpdate,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado.")
    if body.name is not None:
        user.name = body.name
    if body.email is not None:
        existing = db.query(AdminUser).filter(AdminUser.email == body.email.lower().strip(), AdminUser.id != user_id).first()
        if existing:
            raise HTTPException(400, "E-mail já em uso.")
        user.email = body.email.lower().strip()
    if body.active is not None:
        # Prevent self-deactivation
        if user_id == current.id and not body.active:
            raise HTTPException(400, "Você não pode desativar sua própria conta.")
        user.active = body.active
    if body.password is not None:
        user.password_hash = hash_password(body.password)
    db.commit()
    db.refresh(user)
    return ok(AdminOut.model_validate(user), "Usuário atualizado.")


@router.delete("/{user_id}", response_model=None)
def delete_admin_user(
    user_id: str,
    db: Session = Depends(get_db),
    current: AdminUser = Depends(get_current_admin),
):
    if user_id == current.id:
        raise HTTPException(400, "Você não pode excluir sua própria conta.")
    user = db.query(AdminUser).filter(AdminUser.id == user_id).first()
    if not user:
        raise HTTPException(404, "Usuário não encontrado.")
    # Soft delete — just deactivate
    user.active = False
    db.commit()
    return ok(None, "Usuário desativado.")

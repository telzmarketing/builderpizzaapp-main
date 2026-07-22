"""Explicit authorization dependencies for platform-wide operations."""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from backend.config import get_settings
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.models.platform_rbac import PlatformPermission, PlatformRolePermission, PlatformUserRole
from backend.routes.admin_auth import get_current_admin

def has_platform_permission(db: Session, user_id: str, permission_key: str) -> bool:
    row = (db.query(PlatformUserRole.id)
           .join(PlatformRolePermission, PlatformRolePermission.role_id == PlatformUserRole.role_id)
           .join(PlatformPermission, PlatformPermission.id == PlatformRolePermission.permission_id)
           .filter(PlatformUserRole.user_id == user_id, PlatformPermission.key == permission_key)
           .first())
    return row is not None

def require_platform_permission(permission_key: str):
    normalized = (permission_key or "").strip()
    if not normalized:
        raise ValueError("permission_key e obrigatoria")

    def dependency(current_admin: AdminUser = Depends(get_current_admin), db: Session = Depends(get_db)) -> AdminUser:
        if not get_settings().PLATFORM_RBAC_ENABLED:
            raise HTTPException(status_code=404, detail="Recurso nao encontrado.")
        if not has_platform_permission(db, current_admin.id, normalized):
            raise HTTPException(status_code=403, detail="Permissao de plataforma insuficiente.")
        return current_admin
    return dependency

"""Thin HTTP adapter for the read-only platform user directory."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.platform_authorization import require_platform_permission
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.platform_tenants import _success
from backend.schemas.platform_master import ApiEnvelope
from backend.schemas.platform_users import PlatformUserPageOut
from backend.services.platform_user_service import PlatformUserService


router = APIRouter(prefix="/admin/platform/users", tags=["platform-users"])


@router.get("", response_model=ApiEnvelope[PlatformUserPageOut])
def list_platform_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None, pattern="^(active|inactive)$"),
    role: str | None = Query(default=None, max_length=50),
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(
        require_platform_permission("platform_users.view")
    ),
):
    return _success(PlatformUserService(db).list_users(
        page=page,
        page_size=page_size,
        q=q,
        status=status,
        role=role,
    ))

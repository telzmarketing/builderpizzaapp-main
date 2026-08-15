"""Authenticated Master control-plane session endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.platform_authorization import require_platform_access
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.platform_tenants import _success
from backend.schemas.platform_master import ApiEnvelope
from backend.schemas.platform_session import PlatformSessionOut
from backend.services.platform_session_service import PlatformSessionService


router = APIRouter(prefix="/admin/platform/session", tags=["platform-session"])


@router.get("", response_model=ApiEnvelope[PlatformSessionOut])
def get_platform_session(
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(require_platform_access()),
):
    return _success(PlatformSessionService(db).get_session(current_admin.id))

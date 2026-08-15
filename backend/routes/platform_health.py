"""Master Central service-health endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.platform_authorization import require_platform_permission
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.platform_tenants import _success
from backend.schemas.platform_master import ApiEnvelope
from backend.schemas.platform_operations import PlatformHealthOut
from backend.services.platform_health_service import PlatformHealthService

router = APIRouter(prefix="/admin/platform/health", tags=["platform-health"])


@router.get("", response_model=ApiEnvelope[PlatformHealthOut])
def get_platform_health(
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("monitoring.view")),
):
    return _success(PlatformHealthService(db).get_health())

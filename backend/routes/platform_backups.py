"""Master Central backup-manifest endpoints."""
from fastapi import APIRouter, Depends, Query

from backend.core.platform_authorization import require_platform_permission
from backend.models.admin import AdminUser
from backend.routes.platform_tenants import _success
from backend.schemas.platform_master import ApiEnvelope
from backend.schemas.platform_operations import BackupRunListOut, BackupsOverviewOut
from backend.services.platform_backups_service import PlatformBackupsService

router = APIRouter(prefix="/admin/platform/backups", tags=["platform-backups"])


@router.get("/overview", response_model=ApiEnvelope[BackupsOverviewOut])
def backups_overview(
    _admin: AdminUser = Depends(require_platform_permission("backups.view")),
):
    return _success(PlatformBackupsService().overview())


@router.get("/runs", response_model=ApiEnvelope[BackupRunListOut])
def backup_runs(
    limit: int = Query(default=20, ge=1, le=100),
    _admin: AdminUser = Depends(require_platform_permission("backups.view")),
):
    return _success(PlatformBackupsService().list_runs(limit=limit))

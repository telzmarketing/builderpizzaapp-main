"""Master Central cached storage metrics endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.platform_authorization import require_platform_permission
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.platform_tenants import _success
from backend.schemas.platform_master import ApiEnvelope
from backend.schemas.platform_operations import StorageOverviewOut, TenantStoragePageOut
from backend.services.platform_storage_service import PlatformStorageService

router = APIRouter(prefix="/admin/platform/storage", tags=["platform-storage"])


@router.get("/overview", response_model=ApiEnvelope[StorageOverviewOut])
def storage_overview(
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("storage.view")),
):
    return _success(PlatformStorageService(db).overview())


@router.get("/tenants", response_model=ApiEnvelope[TenantStoragePageOut])
def tenant_storage(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, max_length=200),
    usage_state: str | None = Query(default=None, pattern="^(normal|warning|critical|unknown)$"),
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("storage.view")),
):
    return _success(PlatformStorageService(db).list_tenants(
        page=page, page_size=page_size, q=q, usage_state=usage_state,
    ))

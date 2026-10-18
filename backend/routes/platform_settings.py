"""Runtime settings snapshot and independently editable platform identity."""
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.core.platform_authorization import require_platform_permission
from backend.models.admin import AdminUser
from backend.routes.platform_tenants import _success
from backend.schemas.platform_master import ApiEnvelope
from backend.schemas.platform_settings import PlatformSettingsOut
from backend.services.platform_settings_service import PlatformSettingsService
from backend.database import get_db
from backend.schemas.platform_branding import PlatformBranding, PlatformBrandingUploadOut
from backend.services.platform_branding_service import PlatformBrandingService


router = APIRouter(prefix="/admin/platform/settings", tags=["platform-settings"])
public_router = APIRouter(prefix="/platform/branding", tags=["platform-branding"])


@router.get("", response_model=ApiEnvelope[PlatformSettingsOut])
def get_platform_settings(
    _admin: AdminUser = Depends(
        require_platform_permission("platform_settings.view")
    ),
):
    return _success(PlatformSettingsService().get_settings())


@router.get("/branding", response_model=ApiEnvelope[PlatformBranding])
def get_platform_branding(
    _admin: AdminUser = Depends(require_platform_permission("platform_settings.view")),
    db: Session = Depends(get_db),
):
    return _success(PlatformBrandingService(db).get())


@router.put("/branding", response_model=ApiEnvelope[PlatformBranding])
def update_platform_branding(
    body: PlatformBranding,
    _admin: AdminUser = Depends(require_platform_permission("platform_settings.manage")),
    db: Session = Depends(get_db),
):
    return _success(PlatformBrandingService(db).save(body))


@router.post("/branding/upload", response_model=ApiEnvelope[PlatformBrandingUploadOut])
async def upload_platform_branding(
    file: UploadFile = File(...),
    _admin: AdminUser = Depends(require_platform_permission("platform_settings.manage")),
):
    return _success(await PlatformBrandingService().upload(file))


@public_router.get("/assets/{filename}")
def get_platform_branding_asset(filename: str):
    return FileResponse(
        PlatformBrandingService.asset_path(filename), media_type="image/png",
        headers={"Cache-Control": "public, max-age=31536000, immutable", "X-Content-Type-Options": "nosniff"},
    )

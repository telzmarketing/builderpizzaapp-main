"""Thin HTTP adapter for the read-only platform settings snapshot."""
from fastapi import APIRouter, Depends

from backend.core.platform_authorization import require_platform_permission
from backend.models.admin import AdminUser
from backend.routes.platform_tenants import _success
from backend.schemas.platform_master import ApiEnvelope
from backend.schemas.platform_settings import PlatformSettingsOut
from backend.services.platform_settings_service import PlatformSettingsService


router = APIRouter(prefix="/admin/platform/settings", tags=["platform-settings"])


@router.get("", response_model=ApiEnvelope[PlatformSettingsOut])
def get_platform_settings(
    _admin: AdminUser = Depends(
        require_platform_permission("platform_settings.view")
    ),
):
    return _success(PlatformSettingsService().get_settings())

"""Master Central integration inventory endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.platform_authorization import require_platform_permission
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.platform_tenants import _success
from backend.schemas.platform_master import ApiEnvelope
from backend.schemas.platform_operations import IntegrationConnectionPageOut, IntegrationsOverviewOut
from backend.services.platform_integrations_service import PlatformIntegrationsService

router = APIRouter(prefix="/admin/platform/integrations", tags=["platform-integrations"])


@router.get("/overview", response_model=ApiEnvelope[IntegrationsOverviewOut])
def integrations_overview(
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("integrations.view")),
):
    return _success(PlatformIntegrationsService(db).overview())


@router.get("/connections", response_model=ApiEnvelope[IntegrationConnectionPageOut])
def integration_connections(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    tenant_id: str | None = Query(default=None, max_length=100),
    provider: str | None = Query(default=None, max_length=80),
    category: str | None = Query(default=None, pattern="^(marketing|advertising|payments)$"),
    status: str | None = Query(default=None, pattern="^(healthy|degraded|failed|unknown)$"),
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("integrations.view")),
):
    return _success(PlatformIntegrationsService(db).list_connections(
        page=page, page_size=page_size, tenant_id=tenant_id,
        provider=provider, category=category, status=status,
    ))

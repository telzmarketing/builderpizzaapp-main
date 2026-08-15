"""Master Central WhatsApp Gateway fleet endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.platform_authorization import require_platform_permission
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.platform_tenants import _success
from backend.schemas.platform_master import ApiEnvelope
from backend.schemas.platform_operations import GatewayInstancePageOut, GatewayLogListOut, GatewayOverviewOut
from backend.services.platform_gateway_service import PlatformGatewayService
from backend.services.platform_operations_common import PlatformOperationNotFound

router = APIRouter(prefix="/admin/platform/gateway", tags=["platform-gateway"])


@router.get("/overview", response_model=ApiEnvelope[GatewayOverviewOut])
def gateway_overview(
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("gateway.view")),
):
    return _success(PlatformGatewayService(db).overview())


@router.get("/instances", response_model=ApiEnvelope[GatewayInstancePageOut])
def gateway_instances(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    tenant_id: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None, max_length=40),
    provider: str | None = Query(default=None, max_length=40),
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("gateway.view")),
):
    return _success(PlatformGatewayService(db).list_instances(
        page=page, page_size=page_size, tenant_id=tenant_id,
        status=status, provider=provider,
    ))


@router.get("/instances/{instance_id}/logs", response_model=ApiEnvelope[GatewayLogListOut])
def gateway_instance_logs(
    instance_id: str,
    tenant_id: str = Query(max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("gateway.view")),
):
    try:
        return _success(PlatformGatewayService(db).instance_logs(
            instance_id=instance_id, tenant_id=tenant_id, limit=limit,
        ))
    except PlatformOperationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

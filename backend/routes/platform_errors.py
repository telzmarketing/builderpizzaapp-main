"""Master Central redacted error registry endpoints."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from backend.core.platform_authorization import require_platform_permission
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.platform_tenants import _success
from backend.schemas.platform_master import ApiEnvelope
from backend.schemas.platform_operations import (
    ErrorDispositionIn,
    ErrorEventDetailOut,
    ErrorEventPageOut,
    ErrorsOverviewOut,
)
from backend.services.platform_errors_service import PlatformErrorService
from backend.services.platform_operations_common import PlatformOperationConflict, PlatformOperationNotFound

router = APIRouter(prefix="/admin/platform/errors", tags=["platform-errors"])


@router.get("/overview", response_model=ApiEnvelope[ErrorsOverviewOut])
def errors_overview(
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("errors.view")),
):
    return _success(PlatformErrorService(db).overview())


@router.get("", response_model=ApiEnvelope[ErrorEventPageOut])
def error_events(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    tenant_id: str | None = Query(default=None, max_length=100),
    source: str | None = Query(default=None, max_length=80),
    severity: str | None = Query(default=None, pattern="^(info|warning|error|critical)$"),
    status: str | None = Query(default=None, pattern="^(open|acknowledged|resolved)$"),
    from_at: datetime | None = Query(default=None, alias="from"),
    to_at: datetime | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("errors.view")),
):
    return _success(PlatformErrorService(db).list_events(
        page=page, page_size=page_size, tenant_id=tenant_id,
        source=source, severity=severity, status=status,
        from_at=from_at, to_at=to_at,
    ))


@router.get("/{error_id}", response_model=ApiEnvelope[ErrorEventDetailOut])
def error_event(
    error_id: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(require_platform_permission("errors.view")),
):
    try:
        return _success(PlatformErrorService(db).get_event(error_id))
    except PlatformOperationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{error_id}/acknowledge", response_model=ApiEnvelope[ErrorEventDetailOut])
def acknowledge_error(
    error_id: str,
    body: ErrorDispositionIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_platform_permission("errors.manage")),
):
    try:
        return _success(PlatformErrorService(db).acknowledge(
            error_id=error_id, actor=admin, note=body.note, request=request,
        ))
    except PlatformOperationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PlatformOperationConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{error_id}/resolve", response_model=ApiEnvelope[ErrorEventDetailOut])
def resolve_error(
    error_id: str,
    body: ErrorDispositionIn,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(require_platform_permission("errors.manage")),
):
    try:
        return _success(PlatformErrorService(db).resolve(
            error_id=error_id, actor=admin, note=body.note, request=request,
        ))
    except PlatformOperationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PlatformOperationConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

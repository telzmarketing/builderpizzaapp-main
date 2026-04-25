from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import err, no_content
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.admin_auth import get_current_admin
from backend.schemas.store_operation import (
    StoreOperationConfigOut,
    StoreOperationExceptionIn,
    StoreOperationExceptionOut,
    StoreOperationLogOut,
    StoreOperationSettingsIn,
    StoreOperationSettingsOut,
    StoreOperationStatusOut,
    StoreWeeklyScheduleIn,
    StoreWeeklyScheduleOut,
)
from backend.services.store_operation_service import StoreOperationService

router = APIRouter(prefix="/store-operation", tags=["store-operation"])


@router.get("/status", response_model=StoreOperationStatusOut)
def get_store_status(db: Session = Depends(get_db)):
    return StoreOperationService(db).get_status()


@router.get("/config", response_model=StoreOperationConfigOut)
def get_config(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return StoreOperationService(db).get_config()


@router.put("/settings", response_model=StoreOperationSettingsOut)
def update_settings(
    body: StoreOperationSettingsIn,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    try:
        return StoreOperationService(db).update_settings(body, admin)
    except DomainError as exc:
        return err(exc)


@router.put("/weekly-schedules", response_model=list[StoreWeeklyScheduleOut])
def update_weekly_schedules(
    body: list[StoreWeeklyScheduleIn],
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    try:
        return StoreOperationService(db).replace_weekly_schedules(body, admin)
    except DomainError as exc:
        return err(exc)


@router.post("/exceptions", response_model=StoreOperationExceptionOut, status_code=201)
def create_exception(
    body: StoreOperationExceptionIn,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    try:
        return StoreOperationService(db).create_exception(body, admin)
    except DomainError as exc:
        return err(exc)


@router.put("/exceptions/{exception_id}", response_model=StoreOperationExceptionOut)
def update_exception(
    exception_id: str,
    body: StoreOperationExceptionIn,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    try:
        return StoreOperationService(db).update_exception(exception_id, body, admin)
    except DomainError as exc:
        return err(exc)


@router.delete("/exceptions/{exception_id}", status_code=204)
def delete_exception(
    exception_id: str,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    try:
        StoreOperationService(db).delete_exception(exception_id, admin)
        return no_content()
    except DomainError as exc:
        return err(exc)


@router.get("/logs", response_model=list[StoreOperationLogOut])
def list_logs(
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    return StoreOperationService(db).list_logs(limit)

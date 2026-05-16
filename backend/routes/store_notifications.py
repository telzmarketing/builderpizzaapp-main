from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.core.response import ok, created
from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.schemas.store_notification import (
    StoreNotificationCapturedOut,
    StoreNotificationCreate,
    StoreNotificationImpressionIn,
    StoreNotificationNextEnvelope,
    StoreNotificationOut,
    StoreNotificationPreviewIn,
    StoreNotificationPreviewOut,
    StoreNotificationSettingsIn,
    StoreNotificationSettingsOut,
    StoreNotificationSummary,
    StoreNotificationUpdate,
)
from backend.services.store_notification_service import StoreNotificationService

router = APIRouter(prefix="/store-notifications", tags=["store-notifications"])


def _service(db: Session) -> StoreNotificationService:
    return StoreNotificationService(db)


@router.get("/next", response_model=StoreNotificationNextEnvelope)
def next_store_notification(
    page: str = Query(default="home"),
    customer_id: str | None = Query(default=None),
    anonymous_session_id: str | None = Query(default=None),
    seen_ids: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    seen_list = [s.strip() for s in (seen_ids or "").split(",") if s.strip()]
    return _service(db).next_notification(
        page=page,
        customer_id=customer_id or None,
        anonymous_session_id=anonymous_session_id or None,
        seen_ids=seen_list,
    )


@router.get("", response_model=list[StoreNotificationOut])
def list_notifications(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return _service(db).list_notifications()


@router.get("/summary", response_model=StoreNotificationSummary)
def summary(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return _service(db).summary()


@router.get("/settings", response_model=StoreNotificationSettingsOut)
def get_settings(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    svc = _service(db)
    return svc.serialize_settings(svc.get_settings())


@router.put("/settings", response_model=StoreNotificationSettingsOut)
def update_settings(
    body: StoreNotificationSettingsIn,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    svc = _service(db)
    return svc.serialize_settings(svc.update_settings(body))


@router.post("/preview", response_model=StoreNotificationPreviewOut)
def preview(
    body: StoreNotificationPreviewIn,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return _service(db).preview(body)


@router.get("/captured", response_model=list[StoreNotificationCapturedOut])
def list_captured(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return _service(db).list_captured()


@router.post("/{notification_id}/impression")
def record_impression(
    notification_id: str,
    body: StoreNotificationImpressionIn,
    db: Session = Depends(get_db),
):
    try:
        _service(db).record_impression(
            notification_id,
            page=body.page,
            customer_id=body.customer_id or None,
            anonymous_session_id=body.anonymous_session_id or None,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    return ok({"recorded": True})


@router.delete("/captured/{captured_id}", status_code=204)
def discard_captured(
    captured_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    try:
        _service(db).discard_captured(captured_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc))


@router.post("/captured/{captured_id}/activate", response_model=StoreNotificationOut, status_code=201)
def activate_captured(
    captured_id: str,
    body: StoreNotificationCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    try:
        return _service(db).activate_captured(captured_id, body)
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post("", response_model=StoreNotificationOut, status_code=201)
def create_notification(
    body: StoreNotificationCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    try:
        notification = _service(db).create_notification(body)
        return _service(db).serialize_notification(notification)
    except LookupError as exc:
        raise HTTPException(404, str(exc))


@router.put("/{notification_id}", response_model=StoreNotificationOut)
def update_notification(
    notification_id: str,
    body: StoreNotificationUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    try:
        notification = _service(db).update_notification(notification_id, body)
        return _service(db).serialize_notification(notification)
    except LookupError as exc:
        raise HTTPException(404, str(exc))


@router.post("/{notification_id}/duplicate", response_model=StoreNotificationOut, status_code=201)
def duplicate_notification(
    notification_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    try:
        notification = _service(db).duplicate_notification(notification_id)
        return _service(db).serialize_notification(notification)
    except LookupError as exc:
        raise HTTPException(404, str(exc))


@router.patch("/{notification_id}/status", response_model=StoreNotificationOut)
def update_notification_status(
    notification_id: str,
    body: dict,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    try:
        status = body.get("status")
        notification = _service(db).set_status(notification_id, status)
        return _service(db).serialize_notification(notification)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except LookupError as exc:
        raise HTTPException(404, str(exc))


@router.delete("/{notification_id}", status_code=204)
def delete_notification(
    notification_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    try:
        _service(db).delete_notification(notification_id)
    except LookupError as exc:
        raise HTTPException(404, str(exc))


@router.get("/ping")
def ping():
    return ok({"status": "ok"})

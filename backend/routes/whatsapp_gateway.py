from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.schemas.whatsapp_gateway import (
    WhatsAppGatewayInstanceCreate,
    WhatsAppGatewayInstanceOut,
    WhatsAppGatewayLogOut,
    WhatsAppGatewayOverviewOut,
    WhatsAppGatewayProviderStatusOut,
    WhatsAppGatewayRuntimeCommandOut,
    WhatsAppGatewayRuntimeEventIn,
    WhatsAppGatewayRuntimeEventOut,
    WhatsAppGatewaySchedulerSettingsOut,
    WhatsAppGatewayUpdateConfirmIn,
    WhatsAppGatewayUpdateConfirmOut,
    WhatsAppGatewayUpdateStatusOut,
)
from backend.services.whatsapp_gateway_service import WhatsAppGatewayService

router = APIRouter(prefix="/whatsapp-gateway", tags=["whatsapp-gateway"])


@router.get("/overview", response_model=WhatsAppGatewayOverviewOut)
def overview(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return WhatsAppGatewayService(db).overview()


@router.get("/provider/status", response_model=WhatsAppGatewayProviderStatusOut)
def provider_status(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return WhatsAppGatewayService(db).provider_status()


@router.get("/updates/status", response_model=WhatsAppGatewayUpdateStatusOut)
def update_status(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return WhatsAppGatewayService(db).update_status()


@router.post("/updates/check", response_model=WhatsAppGatewayUpdateStatusOut)
def check_update(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    service = WhatsAppGatewayService(db)
    result = service.check_update()
    db.commit()
    return result


@router.post("/updates/confirm", response_model=WhatsAppGatewayUpdateConfirmOut)
def confirm_update(
    body: WhatsAppGatewayUpdateConfirmIn,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = WhatsAppGatewayService(db)
    try:
        result = service.confirm_update(
            check_id=body.check_id,
            target_version=body.target_version,
            confirm=body.confirm,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    return result


@router.get("/scheduler/settings", response_model=WhatsAppGatewaySchedulerSettingsOut)
def scheduler_settings(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    service = WhatsAppGatewayService(db)
    settings = service.get_scheduler_settings()
    db.commit()
    return service.serialize_scheduler_settings(settings)


@router.get("/instances", response_model=list[WhatsAppGatewayInstanceOut])
def list_instances(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    service = WhatsAppGatewayService(db)
    return [service.serialize_instance(instance) for instance in service.list_instances()]


@router.post("/instances", response_model=WhatsAppGatewayInstanceOut, status_code=201)
def create_instance(
    body: WhatsAppGatewayInstanceCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = WhatsAppGatewayService(db)
    try:
        instance = service.create_instance(body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(instance)
    return service.serialize_instance(instance)


@router.get("/instances/{instance_id}", response_model=WhatsAppGatewayInstanceOut)
def get_instance(instance_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    service = WhatsAppGatewayService(db)
    instance = service.get_instance(instance_id)
    if not instance:
        raise HTTPException(status_code=404, detail="Instancia do WhatsApp Gateway nao encontrada.")
    return service.serialize_instance(instance)


@router.post("/instances/{instance_id}/connect", response_model=WhatsAppGatewayRuntimeCommandOut)
def connect_instance(instance_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    service = WhatsAppGatewayService(db)
    try:
        result = service.connect_instance(instance_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result


@router.get("/instances/{instance_id}/qrcode", response_model=WhatsAppGatewayRuntimeCommandOut)
def get_qr_code(instance_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    service = WhatsAppGatewayService(db)
    try:
        result = service.get_qr_code(instance_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result


@router.get("/instances/{instance_id}/status", response_model=WhatsAppGatewayRuntimeCommandOut)
def get_instance_status(instance_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    service = WhatsAppGatewayService(db)
    try:
        result = service.get_instance_status(instance_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result


@router.post("/instances/{instance_id}/disconnect", response_model=WhatsAppGatewayRuntimeCommandOut)
def disconnect_instance(instance_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    service = WhatsAppGatewayService(db)
    try:
        result = service.disconnect_instance(instance_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result


@router.post("/instances/{instance_id}/restart", response_model=WhatsAppGatewayRuntimeCommandOut)
def restart_instance(instance_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    service = WhatsAppGatewayService(db)
    try:
        result = service.restart_instance(instance_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result


@router.post("/runtime/events", response_model=WhatsAppGatewayRuntimeEventOut, include_in_schema=False)
def receive_runtime_event(
    body: WhatsAppGatewayRuntimeEventIn,
    x_whatsapp_gateway_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    expected = settings.WHATSAPP_GATEWAY_EVENT_TOKEN.strip()
    if expected and x_whatsapp_gateway_token != expected:
        raise HTTPException(status_code=401, detail="Token do runtime invalido.")
    result = WhatsAppGatewayService(db).process_runtime_event(body.model_dump())
    db.commit()
    return result


@router.get("/logs", response_model=list[WhatsAppGatewayLogOut])
def list_logs(
    instance_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = WhatsAppGatewayService(db)
    return [service.serialize_log(log) for log in service.list_logs(instance_id=instance_id, limit=limit)]

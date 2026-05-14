from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from backend.core.response import created, err_msg, ok
from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.routes.whatsapp_marketing import _load_whatsapp_verify_token
from backend.schemas.agente_whatsapp import (
    AgenteWhatsAppDashboardOut,
    AgenteWhatsAppInternalAlertOut,
    AgenteWhatsAppMessageCreate,
    AgenteWhatsAppMessageOut,
    AgenteWhatsAppOutboxAlertsOut,
    AgenteWhatsAppOutboxMetricsOut,
    AgenteWhatsAppOutboxOut,
    AgenteWhatsAppOutboxProcessIn,
    AgenteWhatsAppOutboxProcessOut,
    AgenteWhatsAppOutboxSummaryOut,
    AgenteWhatsAppProviderPauseIn,
    AgenteWhatsAppProviderStateOut,
    AgenteWhatsAppSessionCreate,
    AgenteWhatsAppSessionOut,
    AgenteWhatsAppSessionUpdate,
    AgenteWhatsAppToolCallIn,
    AgenteWhatsAppToolCallOut,
    AgenteWhatsAppToolOut,
)
from backend.services.agente_whatsapp_outbox_service import AgenteWhatsAppOutboxService
from backend.services.agente_whatsapp_service import AgenteWhatsAppService
from backend.services.agente_whatsapp_tools import AgenteWhatsAppToolService

router = APIRouter(prefix="/agente-whatsapp", tags=["agente-whatsapp"])


@router.get("/webhook/meta", include_in_schema=False)
def verify_meta_webhook(request: Request, db: Session = Depends(get_db)):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    expected = _load_whatsapp_verify_token(db)

    if mode == "subscribe" and expected and token == expected and challenge:
        return PlainTextResponse(challenge)
    return PlainTextResponse("Forbidden", status_code=403)


@router.post("/webhook/meta", include_in_schema=False)
async def receive_meta_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
    except Exception:
        return err_msg("Payload de webhook invalido.", code="AgenteWhatsAppWebhookInvalid", status_code=400)

    result = AgenteWhatsAppService(db).process_meta_webhook(payload)
    db.commit()
    return ok(result, "Webhook Meta processado.")


@router.post("/webhook/evolution", include_in_schema=False)
async def receive_evolution_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
    except Exception:
        return err_msg("Payload de webhook invalido.", code="AgenteWhatsAppWebhookInvalid", status_code=400)

    result = AgenteWhatsAppService(db).process_evolution_webhook(payload)
    db.commit()
    return ok(result, "Webhook Evolution processado.")


@router.get("/dashboard", response_model=AgenteWhatsAppDashboardOut)
def dashboard(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return AgenteWhatsAppService(db).dashboard()


@router.get("/tools", response_model=list[AgenteWhatsAppToolOut])
def list_tools(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return AgenteWhatsAppToolService(db).list_tools()


@router.post("/tools/execute", response_model=AgenteWhatsAppToolCallOut)
def execute_tool(
    body: AgenteWhatsAppToolCallIn,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = AgenteWhatsAppToolService(db).execute_tool(
        tool_name=body.tool_name,
        arguments=body.arguments,
        session_id=body.session_id,
        customer_id=body.customer_id,
    )
    db.commit()
    return result


@router.get("/outbox/summary", response_model=AgenteWhatsAppOutboxSummaryOut)
def outbox_summary(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return AgenteWhatsAppOutboxService(db).summary()


@router.get("/outbox/metrics", response_model=AgenteWhatsAppOutboxMetricsOut)
def outbox_metrics(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return AgenteWhatsAppOutboxService(db).metrics()


@router.get("/outbox/alerts", response_model=AgenteWhatsAppOutboxAlertsOut)
def outbox_alerts(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    payload = AgenteWhatsAppOutboxService(db).alerts()
    db.commit()
    return payload


@router.get("/outbox/providers", response_model=list[AgenteWhatsAppProviderStateOut])
def outbox_providers(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    service = AgenteWhatsAppOutboxService(db)
    states = service.provider_states()
    db.commit()
    return [service.serialize_provider_state(state) for state in states]


@router.get("/outbox/internal-alerts", response_model=list[AgenteWhatsAppInternalAlertOut])
def list_internal_alerts(
    status: str | None = Query(default="active"),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppOutboxService(db)
    alerts = service.list_internal_alerts(status=status, limit=limit)
    db.commit()
    return [service.serialize_internal_alert(alert) for alert in alerts]


@router.post("/outbox/internal-alerts/{alert_id}/ack", response_model=AgenteWhatsAppInternalAlertOut)
def acknowledge_internal_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppOutboxService(db)
    alert = service.acknowledge_internal_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alerta interno nao encontrado.")
    db.commit()
    db.refresh(alert)
    return service.serialize_internal_alert(alert)


@router.get("/outbox", response_model=list[AgenteWhatsAppOutboxOut])
def list_outbox(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppOutboxService(db)
    return [service.serialize_outbox(row) for row in service.list_outbox(status=status, limit=limit)]


@router.post("/outbox/enqueue")
def enqueue_outbox(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = AgenteWhatsAppOutboxService(db).enqueue_queued_messages(limit=limit)
    db.commit()
    return ok(result, "Mensagens queued enfileiradas.")


@router.post("/outbox/providers/{provider}/pause", response_model=AgenteWhatsAppProviderStateOut)
def pause_outbox_provider(
    provider: str,
    body: AgenteWhatsAppProviderPauseIn,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppOutboxService(db)
    state = service.pause_provider(provider, reason=body.reason, minutes=body.minutes)
    db.commit()
    db.refresh(state)
    return service.serialize_provider_state(state)


@router.post("/outbox/providers/{provider}/resume", response_model=AgenteWhatsAppProviderStateOut)
def resume_outbox_provider(
    provider: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppOutboxService(db)
    state = service.resume_provider(provider)
    db.commit()
    db.refresh(state)
    return service.serialize_provider_state(state)


@router.post("/outbox/process", response_model=AgenteWhatsAppOutboxProcessOut)
def process_outbox(
    body: AgenteWhatsAppOutboxProcessIn,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = AgenteWhatsAppOutboxService(db).process_pending(limit=body.limit)
    db.commit()
    return result


@router.post("/outbox/{outbox_id}/retry", response_model=AgenteWhatsAppOutboxOut)
def retry_outbox(
    outbox_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppOutboxService(db)
    item = service.retry(outbox_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item da fila nao encontrado.")
    db.commit()
    db.refresh(item)
    return service.serialize_outbox(item)


@router.get("/sessions", response_model=list[AgenteWhatsAppSessionOut])
def list_sessions(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppService(db)
    return [service.serialize_session(row) for row in service.list_sessions(status=status, limit=limit)]


@router.post("/sessions", status_code=201)
def create_session(
    body: AgenteWhatsAppSessionCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppService(db)
    try:
        session, was_created = service.get_or_create_session(
            phone=body.phone,
            customer_id=body.customer_id,
            provider=body.provider,
            provider_contact_id=body.provider_contact_id,
            origin=body.origin,
            ai_enabled=body.ai_enabled,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(session)
    payload = service.serialize_session(session)
    return created(payload, "Sessao do AGENTE WHATSAPP criada.") if was_created else ok(payload, "Sessao aberta reutilizada.")


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppService(db)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
    return ok(
        {
            "session": service.serialize_session(session),
            "messages": [service.serialize_message(message) for message in service.list_messages(session_id)],
        }
    )


@router.patch("/sessions/{session_id}", response_model=AgenteWhatsAppSessionOut)
def update_session(
    session_id: str,
    body: AgenteWhatsAppSessionUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppService(db)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
    session = service.update_session(session, body.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(session)
    return service.serialize_session(session)


@router.get("/sessions/{session_id}/messages", response_model=list[AgenteWhatsAppMessageOut])
def list_messages(
    session_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppService(db)
    if not service.get_session(session_id):
        raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
    return [service.serialize_message(message) for message in service.list_messages(session_id, limit=limit)]


@router.post("/sessions/{session_id}/messages", status_code=201, response_model=AgenteWhatsAppMessageOut)
def add_message(
    session_id: str,
    body: AgenteWhatsAppMessageCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppService(db)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
    message = service.add_message(
        session,
        direction=body.direction,
        sender_type=body.sender_type,
        message_type=body.message_type,
        body=body.body,
        media_url=body.media_url,
        provider_message_id=body.provider_message_id,
        provider_status=body.provider_status,
        raw_payload=body.raw_payload,
    )
    db.commit()
    db.refresh(message)
    return service.serialize_message(message)

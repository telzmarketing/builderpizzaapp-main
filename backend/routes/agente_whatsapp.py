from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from backend.core.response import created, err_msg, ok
from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.routes.whatsapp_marketing import _load_whatsapp_verify_token
from backend.schemas.agente_whatsapp import (
    AgenteWhatsAppAIGuardrailsOut,
    AgenteWhatsAppAIKeysUpdate,
    AgenteWhatsAppAIProviderStatusOut,
    AgenteWhatsAppAIRespondIn,
    AgenteWhatsAppAIRespondOut,
    AgenteWhatsAppAISettingsOut,
    AgenteWhatsAppAISettingsUpdate,
    AgenteWhatsAppAITestIn,
    AgenteWhatsAppAITestOut,
    AgenteWhatsAppCampaignCreate,
    AgenteWhatsAppCampaignDispatchOut,
    AgenteWhatsAppCampaignOut,
    AgenteWhatsAppCampaignTemplateOut,
    AgenteWhatsAppChannelSettingsOut,
    AgenteWhatsAppChannelSettingsUpdate,
    AgenteWhatsAppAutomationRunIn,
    AgenteWhatsAppAutomationRunOut,
    AgenteWhatsAppAutomationTemplateOut,
    AgenteWhatsAppConversationOut,
    AgenteWhatsAppDashboardOut,
    AgenteWhatsAppInternalAlertOut,
    AgenteWhatsAppMessageCreate,
    AgenteWhatsAppMessageOut,
    AgenteWhatsAppObservabilityOut,
    AgenteWhatsAppOperationalMetricsOut,
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
    AgenteWhatsAppStoryCreate,
    AgenteWhatsAppStoryOut,
    AgenteWhatsAppStoryPublishOut,
    AgenteWhatsAppStoryTemplateOut,
    AgenteWhatsAppStoryUpdate,
    AgenteWhatsAppToolCallIn,
    AgenteWhatsAppToolCallOut,
    AgenteWhatsAppToolOut,
)
from backend.models.agente_whatsapp import AgenteWhatsAppChannelSettings
from backend.services.agente_whatsapp_ai_service import AgenteWhatsAppAIService
from backend.services.agente_whatsapp_outbox_service import AgenteWhatsAppOutboxService
from backend.services.agente_whatsapp_service import AgenteWhatsAppService
from backend.services.agente_whatsapp_tools import AgenteWhatsAppToolService
from backend.services.whatsapp_gateway_service import WhatsAppGatewayService

router = APIRouter(prefix="/agente-whatsapp", tags=["agente-whatsapp"])


def _get_channel_settings(db: Session) -> AgenteWhatsAppChannelSettings:
    settings = (
        db.query(AgenteWhatsAppChannelSettings)
        .filter(AgenteWhatsAppChannelSettings.id == "default")
        .first()
    )
    if not settings:
        settings = AgenteWhatsAppChannelSettings(id="default", active_provider="official")
        db.add(settings)
        db.flush()
    return settings


def _serialize_channel_settings(settings: AgenteWhatsAppChannelSettings) -> dict:
    return {
        "id": settings.id,
        "active_provider": settings.active_provider,
        "whatsapp_gateway_instance_id": settings.whatsapp_gateway_instance_id,
        "updated_at": settings.updated_at,
    }


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


@router.get("/operational-metrics", response_model=AgenteWhatsAppOperationalMetricsOut)
def operational_metrics(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return AgenteWhatsAppService(db).operational_metrics()


@router.get("/conversations", response_model=list[AgenteWhatsAppConversationOut])
def list_conversations(
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    assigned_admin_id: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=80, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    normalized_status = None if status in (None, "", "all") else status
    return AgenteWhatsAppService(db).list_conversations(
        status=normalized_status,
        search=search,
        assigned_admin_id=assigned_admin_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )


@router.get("/automations/templates", response_model=list[AgenteWhatsAppAutomationTemplateOut])
def automation_templates(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return AgenteWhatsAppService(db).automation_templates()


@router.post("/automations/run", response_model=AgenteWhatsAppAutomationRunOut)
def run_commercial_automation(
    body: AgenteWhatsAppAutomationRunIn,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppService(db)
    try:
        result = service.run_commercial_automation(
            key=body.key,
            limit=body.limit,
            dry_run=body.dry_run,
            message_template=body.message_template,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return result


@router.post("/automations/run-due")
def run_due_commercial_automations(
    limit_per_automation: int = Query(default=30, ge=1, le=200),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = AgenteWhatsAppService(db).run_due_commercial_automations(limit_per_automation=limit_per_automation)
    db.commit()
    return ok(result, "Automacoes comerciais processadas.")


@router.get("/campaigns/templates", response_model=list[AgenteWhatsAppCampaignTemplateOut])
def campaign_templates(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return AgenteWhatsAppService(db).campaign_templates()


@router.get("/stories/templates", response_model=list[AgenteWhatsAppStoryTemplateOut])
def story_templates(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return AgenteWhatsAppService(db).story_templates()


@router.post("/stories/process-scheduled")
def process_scheduled_stories(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = AgenteWhatsAppService(db).process_scheduled_stories(limit=limit)
    db.commit()
    return ok(result, "Stories agendados processados.")


@router.get("/stories", response_model=list[AgenteWhatsAppStoryOut])
def list_stories(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppService(db)
    normalized_status = None if status in (None, "", "all") else status
    return [service.serialize_story(story) for story in service.list_stories(status=normalized_status, limit=limit)]


@router.post("/stories", response_model=AgenteWhatsAppStoryOut)
def create_story(
    body: AgenteWhatsAppStoryCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    service = AgenteWhatsAppService(db)
    story = service.create_story(body.model_dump(), created_by=getattr(admin, "email", None))
    db.commit()
    db.refresh(story)
    return service.serialize_story(story)


@router.patch("/stories/{story_id}", response_model=AgenteWhatsAppStoryOut)
def update_story(
    story_id: str,
    body: AgenteWhatsAppStoryUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppService(db)
    story = service.get_story(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story nao encontrado.")
    updated = service.update_story(story, body.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(updated)
    return service.serialize_story(updated)


@router.post("/stories/{story_id}/publish", response_model=AgenteWhatsAppStoryPublishOut)
def publish_story(
    story_id: str,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppService(db)
    story = service.get_story(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story nao encontrado.")
    result = service.publish_story(story, force=force)
    db.commit()
    return result


@router.post("/campaigns/process-scheduled")
def process_scheduled_campaigns(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = AgenteWhatsAppService(db).process_scheduled_campaigns(limit=limit)
    db.commit()
    return ok(result, "Campanhas agendadas processadas.")


@router.get("/campaigns", response_model=list[AgenteWhatsAppCampaignOut])
def list_campaigns(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppService(db)
    return [service.serialize_campaign(campaign) for campaign in service.list_campaigns(limit=limit)]


@router.post("/campaigns", response_model=AgenteWhatsAppCampaignOut)
def create_campaign(
    body: AgenteWhatsAppCampaignCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    service = AgenteWhatsAppService(db)
    try:
        campaign = service.create_campaign(body.model_dump(), created_by=getattr(admin, "email", None))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    db.refresh(campaign)
    return service.serialize_campaign(campaign)


@router.post("/campaigns/{campaign_id}/dispatch", response_model=AgenteWhatsAppCampaignDispatchOut)
def dispatch_campaign(
    campaign_id: str,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppService(db)
    campaign = service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada.")
    result = service.dispatch_campaign(campaign, force=force)
    db.commit()
    return result


@router.get("/tools", response_model=list[AgenteWhatsAppToolOut])
def list_tools(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return AgenteWhatsAppToolService(db).list_tools()


@router.get("/ai/settings", response_model=AgenteWhatsAppAISettingsOut)
def get_ai_settings(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    service = AgenteWhatsAppAIService(db)
    return service.serialize_settings(service.get_settings())


@router.put("/ai/settings", response_model=AgenteWhatsAppAISettingsOut)
def update_ai_settings(
    body: AgenteWhatsAppAISettingsUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    result = AgenteWhatsAppAIService(db).update_settings(body.model_dump(exclude_none=True))
    db.commit()
    return result


@router.get("/ai/settings/status", response_model=AgenteWhatsAppAIProviderStatusOut)
def ai_provider_status(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return AgenteWhatsAppAIService(db).provider_status()


@router.put("/ai/settings/keys", response_model=AgenteWhatsAppAIProviderStatusOut)
def update_ai_keys(
    body: AgenteWhatsAppAIKeysUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    try:
        result = AgenteWhatsAppAIService(db).update_ai_keys(
            openai_api_key=body.openai_api_key,
            anthropic_api_key=body.anthropic_api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return result


@router.post("/ai/settings/test", response_model=AgenteWhatsAppAITestOut)
def test_ai_settings(
    body: AgenteWhatsAppAITestIn,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    try:
        return AgenteWhatsAppAIService(db).test_ai_connection(message=body.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao chamar IA: {exc}")


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


@router.post("/sessions/{session_id}/ai/respond", response_model=AgenteWhatsAppAIRespondOut)
def ai_respond(
    session_id: str,
    body: AgenteWhatsAppAIRespondIn,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    try:
        result = AgenteWhatsAppAIService(db).respond(
            session_id=session_id,
            message=body.message,
            auto_queue=body.auto_queue,
            record_inbound=body.record_inbound,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return result


@router.get("/sessions/{session_id}/ai/guardrails", response_model=AgenteWhatsAppAIGuardrailsOut)
def ai_guardrails(
    session_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    try:
        return AgenteWhatsAppAIService(db).guardrails(session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/outbox/summary", response_model=AgenteWhatsAppOutboxSummaryOut)
def outbox_summary(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return AgenteWhatsAppOutboxService(db).summary()


@router.get("/outbox/metrics", response_model=AgenteWhatsAppOutboxMetricsOut)
def outbox_metrics(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return AgenteWhatsAppOutboxService(db).metrics()


@router.get("/observability", response_model=AgenteWhatsAppObservabilityOut)
def observability(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    service = AgenteWhatsAppOutboxService(db)
    payload = service.observability()
    db.commit()
    return payload


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


@router.get("/channel/settings", response_model=AgenteWhatsAppChannelSettingsOut)
def get_channel_settings(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    settings = _get_channel_settings(db)
    db.commit()
    db.refresh(settings)
    return _serialize_channel_settings(settings)


@router.put("/channel/settings", response_model=AgenteWhatsAppChannelSettingsOut)
def update_channel_settings(
    body: AgenteWhatsAppChannelSettingsUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    settings = _get_channel_settings(db)
    if body.active_provider is not None:
        settings.active_provider = body.active_provider
    if body.whatsapp_gateway_instance_id is not None:
        instance_id = body.whatsapp_gateway_instance_id.strip()
        if instance_id:
            instance = WhatsAppGatewayService(db).get_instance(instance_id)
            if not instance:
                raise HTTPException(status_code=404, detail="Instancia do WhatsApp Gateway nao encontrada.")
            settings.whatsapp_gateway_instance_id = instance_id
        else:
            settings.whatsapp_gateway_instance_id = None
    db.commit()
    db.refresh(settings)
    return _serialize_channel_settings(settings)


@router.get("/outbox/internal-alerts", response_model=list[AgenteWhatsAppInternalAlertOut])
def list_internal_alerts(
    status: str | None = Query(default="active"),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    service = AgenteWhatsAppOutboxService(db)
    normalized_status = None if status in (None, "", "all") else status
    alerts = service.list_internal_alerts(status=normalized_status, limit=limit)
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

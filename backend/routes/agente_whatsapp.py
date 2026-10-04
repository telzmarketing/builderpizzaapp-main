import hashlib
import hmac
import json
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.response import created, err_msg, ok
from backend.core.tenant_context import TenantContext, TenantSource
from backend.core.tenant_runtime import resolve_panel_tenant_context
from backend.core.wave6_tenant_context import panel_wave6_context
from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.routes.whatsapp_marketing import (
    _meta_connection_for_verify_token,
    _meta_connections_for_phone_ids,
)
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
    AgenteWhatsAppAgentResponseProcessOut,
    AgenteWhatsAppAudioMetricsOut,
    AgenteWhatsAppAudioProcessOut,
    AgenteWhatsAppAudioRetentionCleanupOut,
    AgenteWhatsAppAudioSettingsOut,
    AgenteWhatsAppAudioSettingsUpdate,
    AgenteWhatsAppAudioStateOut,
    AgenteWhatsAppCampaignContextOut,
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
    AgenteWhatsAppProcessingEnqueueOut,
    AgenteWhatsAppProcessingJobOut,
    AgenteWhatsAppProcessingSummaryOut,
    AgenteWhatsAppProductionReadinessOut,
    AgenteWhatsAppProviderPauseIn,
    AgenteWhatsAppProviderStateOut,
    AgenteWhatsAppRolloutSettingsOut,
    AgenteWhatsAppRolloutSettingsUpdate,
    AgenteWhatsAppSessionCreate,
    AgenteWhatsAppSessionOut,
    AgenteWhatsAppSessionUpdate,
    AgenteWhatsAppStoryCreate,
    AgenteWhatsAppStoryOut,
    AgenteWhatsAppStoryPublishOut,
    AgenteWhatsAppStoryTemplateOut,
    AgenteWhatsAppStoryUpdate,
    AgenteWhatsAppTTSProcessOut,
    AgenteWhatsAppTTSStateOut,
    AgenteWhatsAppToolCallIn,
    AgenteWhatsAppToolCallOut,
    AgenteWhatsAppToolOut,
)
from backend.models.agente_whatsapp import AgenteWhatsAppChannelSettings, AgenteWhatsAppMessage
from backend.services.agente_whatsapp_ai_service import AgenteWhatsAppAIService
from backend.services.agente_whatsapp_analytics_service import AgenteWhatsAppAnalyticsService
from backend.services.agente_whatsapp_audio_settings_service import AgenteWhatsAppAudioSettingsService
from backend.services.agente_whatsapp_audio_service import AgenteWhatsAppAudioService
from backend.services.agente_whatsapp_campaign_context_service import AgenteWhatsAppCampaignContextService
from backend.services.agente_whatsapp_outbox_service import AgenteWhatsAppOutboxService
from backend.services.agente_whatsapp_processing_service import AgenteWhatsAppProcessingService
from backend.services.agente_whatsapp_retention_service import AgenteWhatsAppRetentionService
from backend.services.agente_whatsapp_rollout_service import AgenteWhatsAppRolloutService
from backend.services.agente_whatsapp_service import AgenteWhatsAppService
from backend.services.agente_whatsapp_tools import AgenteWhatsAppToolService
from backend.services.whatsapp_gateway_service import WhatsAppGatewayService

router = APIRouter(prefix="/agente-whatsapp", tags=["agente-whatsapp"])
# Provider callbacks cannot have a panel-session dependency.  Keep them on a
# separate router so the admin surface remains guarded while the public
# boundary proves a tenant from provider credentials.
webhook_router = APIRouter(prefix="/agente-whatsapp", tags=["agente-whatsapp-webhook"])


def _get_channel_settings(db: Session, context: TenantContext | None) -> AgenteWhatsAppChannelSettings:
    tenant_id = context.tenant_id if context else "tenant-legacy-default"
    settings = (
        db.query(AgenteWhatsAppChannelSettings)
        .filter(
            AgenteWhatsAppChannelSettings.tenant_id == tenant_id,
        )
        .first()
    )
    if not settings:
        settings = AgenteWhatsAppChannelSettings(
            id=f"agente-whatsapp-channel-{tenant_id}",
            tenant_id=tenant_id,
            active_provider="official",
        )
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


def _trusted_process_context(tenant_id: str, request: Request) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id,
        source=TenantSource.WEBHOOK,
        correlation_id=getattr(request.state, "correlation_id", None),
    )


def _meta_phone_ids(payload: dict) -> set[str]:
    """Extract all phone ids relevant to a Meta event without trusting them."""
    phone_ids: set[str] = set()
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value") or {}
            if not ((value.get("messages") or []) or (value.get("statuses") or [])):
                continue
            phone_number_id = str(
                (value.get("metadata") or {}).get("phone_number_id") or ""
            ).strip()
            if not phone_number_id:
                raise ValueError("Webhook Meta sem phone_number_id.")
            phone_ids.add(phone_number_id)
    return phone_ids


def _meta_connections_for_callback(db: Session, phone_ids: set[str]) -> dict[str, dict]:
    """Resolve persisted Meta identities, not caller-provided tenant input.

    The shared resolver reads ``whatsapp_phone_number_id`` and the GET
    challenge is separately bound by ``whatsapp_webhook_verify_token_hash``.
    """
    return _meta_connections_for_phone_ids(db, phone_ids)


def _evolution_connection_for_instance(db: Session, instance: str, api_key: str) -> str:
    """Resolve one Evolution instance and verify its tenant-owned secret."""
    if not instance or not api_key:
        raise ValueError("Instancia ou segredo Evolution ausente.")
    matches = db.execute(
        # ``whatsapp_config`` is the tenant-owned source of the Evolution
        # configuration.  Do not fall back to a global/default config here.
        text(
            """
            SELECT tenant_id, evolution_api_key
            FROM whatsapp_config
            WHERE evolution_instance = :instance
              AND tenant_id IS NOT NULL
            """
        ),
        {"instance": instance},
    ).mappings().all()
    if len(matches) != 1:
        raise ValueError("Evolution nao configurado para este webhook.")
    configured_secret = str(matches[0]["evolution_api_key"] or "")
    if not configured_secret or not hmac.compare_digest(configured_secret, api_key):
        raise ValueError("Segredo Evolution invalido.")
    return str(matches[0]["tenant_id"])


@webhook_router.get("/webhook/meta", include_in_schema=False)
def verify_meta_webhook(request: Request, db: Session = Depends(get_db)):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and _meta_connection_for_verify_token(db, token) and challenge:
        return PlainTextResponse(challenge)
    return PlainTextResponse("Forbidden", status_code=403)


@webhook_router.post("/webhook/meta", include_in_schema=False)
async def receive_meta_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        raw_body = await request.body()
        payload = json.loads(raw_body)
    except Exception:
        return err_msg("Payload de webhook invalido.", code="AgenteWhatsAppWebhookInvalid", status_code=400)

    try:
        phone_ids = _meta_phone_ids(payload)
        connections = _meta_connections_for_callback(db, phone_ids)
    except ValueError as exc:
        return err_msg(str(exc), code="AgenteWhatsAppWebhookTenantInvalid", status_code=403)
    if not phone_ids:
        return err_msg("Webhook Meta sem evento identificavel.", code="AgenteWhatsAppWebhookTenantMissing", status_code=403)
    app_secrets = {str(item["credentials"]["app_secret"]) for item in connections.values()}
    signature = request.headers.get("X-Hub-Signature-256", "")
    if len(app_secrets) != 1 or not signature.startswith("sha256="):
        return err_msg("Assinatura Meta invalida.", code="AgenteWhatsAppWebhookSignatureInvalid", status_code=401)
    expected_signature = "sha256=" + hmac.new(
        next(iter(app_secrets)).encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return err_msg("Assinatura Meta invalida.", code="AgenteWhatsAppWebhookSignatureInvalid", status_code=401)
    tenant_ids = {str(item["tenant_id"]) for item in connections.values()}
    if len(tenant_ids) != 1:
        return err_msg("Webhook Meta cobre empresas diferentes.", code="AgenteWhatsAppWebhookTenantInvalid", status_code=403)
    tenant_context = _trusted_process_context(next(iter(tenant_ids)), request)
    result = AgenteWhatsAppService(db, tenant_context).process_meta_webhook(payload)
    db.commit()
    return ok(result, "Webhook Meta processado.")


@webhook_router.post("/webhook/evolution", include_in_schema=False)
async def receive_evolution_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
    except Exception:
        return err_msg("Payload de webhook invalido.", code="AgenteWhatsAppWebhookInvalid", status_code=400)

    instance = str(payload.get("instance") or "").strip()
    api_key = request.headers.get("apikey", "")
    try:
        tenant_id = _evolution_connection_for_instance(db, instance, api_key)
    except ValueError as exc:
        return err_msg(str(exc), code="AgenteWhatsAppWebhookTenantInvalid", status_code=403)
    tenant_context = _trusted_process_context(tenant_id, request)
    result = AgenteWhatsAppService(db, tenant_context).process_evolution_webhook(payload)
    db.commit()
    return ok(result, "Webhook Evolution processado.")


@router.get("/dashboard", response_model=AgenteWhatsAppDashboardOut)
def dashboard(
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    return AgenteWhatsAppService(db, context).dashboard()


@router.get("/operational-metrics", response_model=AgenteWhatsAppOperationalMetricsOut)
def operational_metrics(
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    return AgenteWhatsAppService(db, context).operational_metrics()


@router.get("/audio/metrics", response_model=AgenteWhatsAppAudioMetricsOut)
def audio_metrics(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    return AgenteWhatsAppAnalyticsService(db, context).audio_metrics(days=days)


@router.get("/audio/production-readiness", response_model=AgenteWhatsAppProductionReadinessOut)
def audio_production_readiness(
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    settings = get_settings()
    outbox_service = AgenteWhatsAppOutboxService(db, context)
    processing_summary = AgenteWhatsAppProcessingService(db, context).summary()
    outbox_metrics = outbox_service.metrics()
    audio_settings = AgenteWhatsAppAudioSettingsService(db, context).get_settings()
    rollout_status = AgenteWhatsAppRolloutService(db, context).status()

    checks = [
        {
            "code": "worker_enabled",
            "ok": bool(settings.AGENTE_WHATSAPP_WORKER_ENABLED),
            "message": "Worker do AGENTE WHATSAPP habilitado." if settings.AGENTE_WHATSAPP_WORKER_ENABLED else "Worker geral desativado.",
        },
        {
            "code": "audio_input",
            "ok": bool(settings.WHATSAPP_AUDIO_INPUT_ENABLED),
            "message": "Entrada de audio habilitada." if settings.WHATSAPP_AUDIO_INPUT_ENABLED else "Entrada de audio desativada.",
        },
        {
            "code": "auto_reply",
            "ok": bool(settings.WHATSAPP_AI_AUTO_REPLY_ENABLED),
            "message": "Resposta automatica habilitada." if settings.WHATSAPP_AI_AUTO_REPLY_ENABLED else "Resposta automatica desativada; atendimento texto/humano preservado.",
        },
        {
            "code": "audio_output",
            "ok": bool(audio_settings["enabled"] and settings.WHATSAPP_AUDIO_TTS_WORKER_ENABLED),
            "message": "Saida por voz habilitada." if audio_settings["enabled"] else "Saida por voz desativada.",
        },
        {
            "code": "outbox_dead",
            "ok": int(outbox_metrics.get("dead") or 0) == 0,
            "message": f"{int(outbox_metrics.get('dead') or 0)} item(ns) mortos na fila.",
        },
        {
            "code": "processing_dead",
            "ok": int(processing_summary.get("dead") or 0) == 0,
            "message": f"{int(processing_summary.get('dead') or 0)} job(s) mortos no processamento.",
        },
        {
            "code": "retention_cleanup",
            "ok": bool(settings.WHATSAPP_AUDIO_RETENTION_CLEANUP_ENABLED),
            "message": "Cleanup automatico de audio habilitado." if settings.WHATSAPP_AUDIO_RETENTION_CLEANUP_ENABLED else "Cleanup automatico desativado; usar dry-run antes de habilitar.",
        },
    ]
    blocking_codes = {"worker_enabled", "outbox_dead", "processing_dead"}
    status = "ready"
    if any(not item["ok"] and item["code"] in blocking_codes for item in checks):
        status = "blocked"
    elif any(not item["ok"] for item in checks):
        status = "degraded"

    return {
        "status": status,
        "flags": {
            "agente_whatsapp_worker_enabled": bool(settings.AGENTE_WHATSAPP_WORKER_ENABLED),
            "audio_input_enabled": bool(settings.WHATSAPP_AUDIO_INPUT_ENABLED),
            "audio_transcription_worker_enabled": bool(settings.WHATSAPP_AUDIO_TRANSCRIPTION_WORKER_ENABLED),
            "campaign_context_enabled": bool(settings.WHATSAPP_CAMPAIGN_CONTEXT_ENABLED),
            "ai_auto_reply_enabled": bool(settings.WHATSAPP_AI_AUTO_REPLY_ENABLED),
            "audio_output_enabled": bool(audio_settings["enabled"]),
            "audio_tts_worker_enabled": bool(settings.WHATSAPP_AUDIO_TTS_WORKER_ENABLED),
            "audio_text_fallback_enabled": bool(settings.WHATSAPP_AUDIO_TEXT_FALLBACK_ENABLED),
            "audio_low_confidence_handoff_enabled": bool(settings.WHATSAPP_AUDIO_LOW_CONFIDENCE_HANDOFF_ENABLED),
            "audio_retention_cleanup_enabled": bool(settings.WHATSAPP_AUDIO_RETENTION_CLEANUP_ENABLED),
            "gateway_audio_baileys_enabled": bool(settings.WHATSAPP_GATEWAY_AUDIO_BAILEYS_ENABLED),
            "audio_rollout_enabled": rollout_status["mode"] != "off",
        },
        "limits": {
            "audio_max_input_bytes": settings.WHATSAPP_AUDIO_MAX_INPUT_BYTES,
            "audio_retention_days": settings.WHATSAPP_AUDIO_RETENTION_DAYS,
            "audio_retention_batch_size": settings.WHATSAPP_AUDIO_RETENTION_BATCH_SIZE,
            "worker_interval_seconds": settings.AGENTE_WHATSAPP_WORKER_INTERVAL_SECONDS,
            "worker_batch_size": settings.AGENTE_WHATSAPP_WORKER_BATCH_SIZE,
            "rollout": rollout_status,
        },
        "rollout": [
            "Validar migrations/current/heads na VPS antes do restart.",
            "Habilitar audio input antes de audio output.",
            "Manter fallback textual ligado no piloto.",
            "Testar Android, iPhone, WhatsApp Web e Desktop antes da expansao.",
            "Rodar /audio/retention/cleanup em dry_run antes de habilitar cleanup automatico.",
        ],
        "rollback": [
            "Desligar WHATSAPP_AUDIO_INPUT_ENABLED para parar STT.",
            "Desligar WHATSAPP_AI_AUTO_REPLY_ENABLED para parar respostas automaticas.",
            "Desligar a saida por voz nas configuracoes do Agente para parar TTS.",
            "Desligar WHATSAPP_GATEWAY_AUDIO_BAILEYS_ENABLED para bloquear envio de audio pelo Gateway.",
            "Manter atendimento humano e texto funcionando.",
        ],
        "checks": checks,
        "generated_at": datetime.now(timezone.utc),
    }


@router.post("/audio/retention/cleanup", response_model=AgenteWhatsAppAudioRetentionCleanupOut)
def cleanup_audio_retention(
    dry_run: bool = Query(default=True),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    result = AgenteWhatsAppRetentionService(db, context).audio_cleanup(dry_run=dry_run, limit=limit)
    if not dry_run:
        db.commit()
    return result


@router.get("/conversations", response_model=list[AgenteWhatsAppConversationOut])
def list_conversations(
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
    assigned_admin_id: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=80, ge=1, le=200),
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    normalized_status = None if status in (None, "", "all") else status
    return AgenteWhatsAppService(db, context).list_conversations(
        status=normalized_status,
        search=search,
        assigned_admin_id=assigned_admin_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )


@router.get("/automations/templates", response_model=list[AgenteWhatsAppAutomationTemplateOut])
def automation_templates(db: Session = Depends(get_db), context: TenantContext | None = Depends(panel_wave6_context)):
    return AgenteWhatsAppService(db, context).automation_templates()


@router.post("/automations/run", response_model=AgenteWhatsAppAutomationRunOut)
def run_commercial_automation(
    body: AgenteWhatsAppAutomationRunIn,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppService(db, context)
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
    context: TenantContext | None = Depends(panel_wave6_context),
):
    result = AgenteWhatsAppService(db, context).run_due_commercial_automations(limit_per_automation=limit_per_automation)
    db.commit()
    return ok(result, "Automacoes comerciais processadas.")


@router.get("/campaigns/templates", response_model=list[AgenteWhatsAppCampaignTemplateOut])
def campaign_templates(db: Session = Depends(get_db), context: TenantContext | None = Depends(panel_wave6_context)):
    return AgenteWhatsAppService(db, context).campaign_templates()


@router.get("/stories/templates", response_model=list[AgenteWhatsAppStoryTemplateOut])
def story_templates(db: Session = Depends(get_db), context: TenantContext | None = Depends(panel_wave6_context)):
    return AgenteWhatsAppService(db, context).story_templates()


@router.post("/stories/process-scheduled")
def process_scheduled_stories(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    result = AgenteWhatsAppService(db, context).process_scheduled_stories(limit=limit)
    db.commit()
    return ok(result, "Stories agendados processados.")


@router.get("/stories", response_model=list[AgenteWhatsAppStoryOut])
def list_stories(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppService(db, context)
    normalized_status = None if status in (None, "", "all") else status
    return [service.serialize_story(story) for story in service.list_stories(status=normalized_status, limit=limit)]


@router.post("/stories", response_model=AgenteWhatsAppStoryOut)
def create_story(
    body: AgenteWhatsAppStoryCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppService(db, context)
    story = service.create_story(body.model_dump(), created_by=getattr(admin, "email", None))
    db.commit()
    db.refresh(story)
    return service.serialize_story(story)


@router.patch("/stories/{story_id}", response_model=AgenteWhatsAppStoryOut)
def update_story(
    story_id: str,
    body: AgenteWhatsAppStoryUpdate,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppService(db, context)
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
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppService(db, context)
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
    context: TenantContext | None = Depends(panel_wave6_context),
):
    result = AgenteWhatsAppService(db, context).process_scheduled_campaigns(limit=limit)
    db.commit()
    return ok(result, "Campanhas agendadas processadas.")


@router.get("/campaigns", response_model=list[AgenteWhatsAppCampaignOut])
def list_campaigns(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppService(db, context)
    return [service.serialize_campaign(campaign) for campaign in service.list_campaigns(limit=limit)]


@router.post("/campaigns", response_model=AgenteWhatsAppCampaignOut)
def create_campaign(
    body: AgenteWhatsAppCampaignCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppService(db, context)
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
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppService(db, context)
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
def get_ai_settings(
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppAIService(db, context)
    return service.serialize_settings(service.get_settings())


@router.put("/ai/settings", response_model=AgenteWhatsAppAISettingsOut)
def update_ai_settings(
    body: AgenteWhatsAppAISettingsUpdate,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    result = AgenteWhatsAppAIService(db, context).update_settings(body.model_dump(exclude_none=True))
    db.commit()
    return result


@router.get("/ai/settings/status", response_model=AgenteWhatsAppAIProviderStatusOut)
def ai_provider_status(
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    return AgenteWhatsAppAIService(db, context).provider_status()


@router.put("/ai/settings/keys", response_model=AgenteWhatsAppAIProviderStatusOut)
def update_ai_keys(
    body: AgenteWhatsAppAIKeysUpdate,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    try:
        result = AgenteWhatsAppAIService(db, context).update_ai_keys(
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
    context: TenantContext | None = Depends(panel_wave6_context),
):
    try:
        return AgenteWhatsAppAIService(db, context).test_ai_connection(message=body.message)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"Falha ao chamar IA: {exc}")


@router.post("/tools/execute", response_model=AgenteWhatsAppToolCallOut)
def execute_tool(
    body: AgenteWhatsAppToolCallIn,
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    context = resolve_panel_tenant_context(request, db, admin)
    result = AgenteWhatsAppToolService(db, context).execute_tool(
        tool_name=body.tool_name,
        arguments=body.arguments,
        session_id=body.session_id,
        customer_id=body.customer_id,
    )
    db.commit()
    return result


@router.get("/audio/settings", response_model=AgenteWhatsAppAudioSettingsOut)
def get_audio_settings(
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    return AgenteWhatsAppAudioSettingsService(db, context).get_settings()


@router.put("/audio/settings", response_model=AgenteWhatsAppAudioSettingsOut)
def update_audio_settings(
    body: AgenteWhatsAppAudioSettingsUpdate,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    result = AgenteWhatsAppAudioSettingsService(db, context).update_settings(body.model_dump(exclude_none=True))
    db.commit()
    return result


@router.get("/audio/rollout", response_model=AgenteWhatsAppRolloutSettingsOut)
def get_audio_rollout_settings(
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    return AgenteWhatsAppRolloutService(db, context).get_settings()


@router.put("/audio/rollout", response_model=AgenteWhatsAppRolloutSettingsOut)
def update_audio_rollout_settings(
    body: AgenteWhatsAppRolloutSettingsUpdate,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    result = AgenteWhatsAppRolloutService(db, context).update_settings(body.model_dump(exclude_none=True))
    db.commit()
    return result


@router.post("/sessions/{session_id}/ai/respond", response_model=AgenteWhatsAppAIRespondOut)
def ai_respond(
    session_id: str,
    body: AgenteWhatsAppAIRespondIn,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    try:
        result = AgenteWhatsAppAIService(db, context).respond(
            session_id=session_id,
            message=body.message,
            auto_queue=body.auto_queue,
            record_inbound=body.record_inbound,
            source_message_id=body.source_message_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.commit()
    return result


@router.get("/sessions/{session_id}/ai/guardrails", response_model=AgenteWhatsAppAIGuardrailsOut)
def ai_guardrails(
    session_id: str,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    try:
        return AgenteWhatsAppAIService(db, context).guardrails(session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/sessions/{session_id}/campaign-context", response_model=AgenteWhatsAppCampaignContextOut)
def get_session_campaign_context(
    session_id: str,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppService(db, context)
    if not service.get_session(session_id):
        raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
    payload = AgenteWhatsAppCampaignContextService(db, context).resolve_latest_for_session(session_id, persist=True)
    db.commit()
    return payload


@router.post("/messages/{message_id}/resolve-campaign-context", response_model=AgenteWhatsAppCampaignContextOut)
def resolve_message_campaign_context(
    message_id: str,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    try:
        payload = AgenteWhatsAppCampaignContextService(db, context).resolve_for_message(message_id, persist=True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return payload


@router.get("/outbox/summary", response_model=AgenteWhatsAppOutboxSummaryOut)
def outbox_summary(db: Session = Depends(get_db), context: TenantContext | None = Depends(panel_wave6_context)):
    return AgenteWhatsAppOutboxService(db, context).summary()


@router.get("/outbox/metrics", response_model=AgenteWhatsAppOutboxMetricsOut)
def outbox_metrics(db: Session = Depends(get_db), context: TenantContext | None = Depends(panel_wave6_context)):
    return AgenteWhatsAppOutboxService(db, context).metrics()


@router.get("/observability", response_model=AgenteWhatsAppObservabilityOut)
def observability(db: Session = Depends(get_db), context: TenantContext | None = Depends(panel_wave6_context)):
    service = AgenteWhatsAppOutboxService(db, context)
    payload = service.observability()
    db.commit()
    return payload


@router.get("/outbox/alerts", response_model=AgenteWhatsAppOutboxAlertsOut)
def outbox_alerts(db: Session = Depends(get_db), context: TenantContext | None = Depends(panel_wave6_context)):
    payload = AgenteWhatsAppOutboxService(db, context).alerts()
    db.commit()
    return payload


@router.get("/outbox/providers", response_model=list[AgenteWhatsAppProviderStateOut])
def outbox_providers(db: Session = Depends(get_db), context: TenantContext | None = Depends(panel_wave6_context)):
    service = AgenteWhatsAppOutboxService(db, context)
    states = service.provider_states()
    db.commit()
    return [service.serialize_provider_state(state) for state in states]


@router.get("/channel/settings", response_model=AgenteWhatsAppChannelSettingsOut)
def get_channel_settings(db: Session = Depends(get_db), context: TenantContext | None = Depends(panel_wave6_context)):
    settings = _get_channel_settings(db, context)
    db.commit()
    db.refresh(settings)
    return _serialize_channel_settings(settings)


@router.put("/channel/settings", response_model=AgenteWhatsAppChannelSettingsOut)
def update_channel_settings(
    body: AgenteWhatsAppChannelSettingsUpdate,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    settings = _get_channel_settings(db, context)
    if body.active_provider is not None:
        settings.active_provider = body.active_provider
    if body.whatsapp_gateway_instance_id is not None:
        instance_id = body.whatsapp_gateway_instance_id.strip()
        if instance_id:
            instance = WhatsAppGatewayService(db, tenant_context=context).get_instance(instance_id)
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
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppOutboxService(db, context)
    normalized_status = None if status in (None, "", "all") else status
    alerts = service.list_internal_alerts(status=normalized_status, limit=limit)
    db.commit()
    return [service.serialize_internal_alert(alert) for alert in alerts]


@router.post("/outbox/internal-alerts/{alert_id}/ack", response_model=AgenteWhatsAppInternalAlertOut)
def acknowledge_internal_alert(
    alert_id: str,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppOutboxService(db, context)
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
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppOutboxService(db, context)
    return [service.serialize_outbox(row) for row in service.list_outbox(status=status, limit=limit)]


@router.post("/outbox/enqueue")
def enqueue_outbox(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    result = AgenteWhatsAppOutboxService(db, context).enqueue_queued_messages(limit=limit)
    db.commit()
    return ok(result, "Mensagens queued enfileiradas.")


@router.post("/outbox/providers/{provider}/pause", response_model=AgenteWhatsAppProviderStateOut)
def pause_outbox_provider(
    provider: str,
    body: AgenteWhatsAppProviderPauseIn,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppOutboxService(db, context)
    state = service.pause_provider(provider, reason=body.reason, minutes=body.minutes)
    db.commit()
    db.refresh(state)
    return service.serialize_provider_state(state)


@router.post("/outbox/providers/{provider}/resume", response_model=AgenteWhatsAppProviderStateOut)
def resume_outbox_provider(
    provider: str,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppOutboxService(db, context)
    state = service.resume_provider(provider)
    db.commit()
    db.refresh(state)
    return service.serialize_provider_state(state)


@router.post("/outbox/process", response_model=AgenteWhatsAppOutboxProcessOut)
def process_outbox(
    body: AgenteWhatsAppOutboxProcessIn,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    result = AgenteWhatsAppOutboxService(db, context).process_pending(limit=body.limit)
    db.commit()
    return result


@router.get("/processing/summary", response_model=AgenteWhatsAppProcessingSummaryOut)
def processing_summary(db: Session = Depends(get_db), context: TenantContext | None = Depends(panel_wave6_context)):
    return AgenteWhatsAppProcessingService(db, context).summary()


@router.get("/processing/jobs", response_model=list[AgenteWhatsAppProcessingJobOut])
def list_processing_jobs(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppProcessingService(db, context)
    return [service.serialize_job(job) for job in service.list_jobs(status=status, limit=limit)]


@router.post("/processing/enqueue", response_model=AgenteWhatsAppProcessingEnqueueOut)
def enqueue_processing_jobs(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    result = AgenteWhatsAppProcessingService(db, context).enqueue_pending_inbound(limit=limit)
    db.commit()
    return result


@router.post("/processing/audio-transcriptions/process", response_model=AgenteWhatsAppAudioProcessOut)
def process_audio_transcriptions(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    result = AgenteWhatsAppProcessingService(db, context).process_audio_transcriptions(limit=limit)
    db.commit()
    return result


@router.post("/processing/agent-responses/process", response_model=AgenteWhatsAppAgentResponseProcessOut)
def process_agent_responses(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    result = AgenteWhatsAppProcessingService(db, context).process_agent_responses(limit=limit)
    db.commit()
    return result


@router.post("/processing/tts-generations/process", response_model=AgenteWhatsAppTTSProcessOut)
def process_tts_generations(
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    result = AgenteWhatsAppProcessingService(db, context).process_tts_generations(limit=limit)
    db.commit()
    return result


@router.post("/messages/{message_id}/retry-tts", response_model=AgenteWhatsAppTTSStateOut)
def retry_message_tts(
    message_id: str,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    try:
        result = AgenteWhatsAppAudioService(db, context).synthesize_response_audio(message_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    message_payload = result.get("message") if isinstance(result.get("message"), dict) else None
    generated_id = message_payload.get("id") if message_payload else None
    if generated_id:
        tenant_id = context.tenant_id if context else "tenant-legacy-default"
        generated = db.query(AgenteWhatsAppMessage).filter(
            AgenteWhatsAppMessage.id == generated_id,
            AgenteWhatsAppMessage.tenant_id == tenant_id,
        ).first()
        if generated:
            generated.provider_status = "queued"
            generated.error = None
    AgenteWhatsAppOutboxService(db, context).enqueue_queued_messages(limit=20)
    db.commit()
    return result


@router.post("/messages/{message_id}/retry-transcription", response_model=AgenteWhatsAppAudioStateOut)
def retry_message_transcription(
    message_id: str,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    try:
        result = AgenteWhatsAppAudioService(db, context).transcribe_message(message_id, force=True)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return result


@router.post("/outbox/{outbox_id}/retry", response_model=AgenteWhatsAppOutboxOut)
def retry_outbox(
    outbox_id: str,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppOutboxService(db, context)
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
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppService(db, context)
    return [service.serialize_session(row) for row in service.list_sessions(status=status, limit=limit)]


@router.post("/sessions", status_code=201)
def create_session(
    body: AgenteWhatsAppSessionCreate,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppService(db, context)
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
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppService(db, context)
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
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppService(db, context)
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
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppService(db, context)
    if not service.get_session(session_id):
        raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
    return [service.serialize_message(message) for message in service.list_messages(session_id, limit=limit)]


@router.post("/sessions/{session_id}/messages", status_code=201, response_model=AgenteWhatsAppMessageOut)
def add_message(
    session_id: str,
    body: AgenteWhatsAppMessageCreate,
    db: Session = Depends(get_db),
    context: TenantContext | None = Depends(panel_wave6_context),
):
    service = AgenteWhatsAppService(db, context)
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada.")
    message = service.add_message(
        session,
        direction=body.direction,
        sender_type=body.sender_type,
        provider=body.provider,
        message_type=body.message_type,
        body=body.body,
        media_url=body.media_url,
        media_storage_key=body.media_storage_key,
        media_mime_type=body.media_mime_type,
        media_duration_ms=body.media_duration_ms,
        media_size_bytes=body.media_size_bytes,
        provider_message_id=body.provider_message_id,
        quoted_provider_message_id=body.quoted_provider_message_id,
        response_to_message_id=body.response_to_message_id,
        campaign_id=body.campaign_id,
        campaign_delivery_id=body.campaign_delivery_id,
        provider_status=body.provider_status,
        raw_payload=body.raw_payload,
    )
    db.commit()
    db.refresh(message)
    return service.serialize_message(message)

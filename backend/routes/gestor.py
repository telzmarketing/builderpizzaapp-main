"""Protected administrative Gestor foundation routes and public Meta webhook.

This surface only records authorized contacts and confirmed operations. It does
not dispatch an AI tool or mutate commercial ERP data.
"""
import base64
import json
from fastapi import APIRouter, Depends, File, Header, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import err, err_msg
from backend.database import get_db
from backend.schemas.gestor import (
    GestorContactCreate, GestorContactOut, GestorContactUpdate,
    GestorOperationConfirmIn, GestorOperationOut, GestorOperationPreviewIn,
    GestorOperationPreviewOut,
    GestorToolCatalogItem, GestorToolExecuteIn, GestorToolExecuteOut,
    GestorAIPlanIn, GestorAIPlanOut, GestorAIProviderStatusOut, GestorAISettingsOut,
    GestorAISettingsUpdate,
    GestorWhatsAppChannelOut, GestorWhatsAppChannelUpdate, GestorWhatsAppWebhookOut,
    GestorWhatsAppMessageOut, GestorInboxProcessOut, GestorWhatsAppEnqueueIn,
    GestorWhatsAppEnqueueOut, GestorWhatsAppOutboxOut, GestorWhatsAppOutboxProcessOut,
    GestorWhatsAppOutboxRetryOut,
    GestorMultimodalIn, GestorMultimodalIngestOut, GestorMultimodalOut,
    GestorMultimodalReviewIn, GestorMultimodalAuditOut,
    GestorAutomationCreate, GestorAutomationUpdate, GestorAutomationOut,
    GestorAutomationSimulateIn, GestorAutomationSimulationOut,
    GestorAutomationProcessOut, GestorAutomationRunOut,
)
from backend.services.gestor_service import GestorService, GestorWhatsAppNotConfigured, GestorMultimodalInvalid

router = APIRouter(prefix="/gestor", tags=["gestor"])
view = require_rbac_permission("whatsapp", "view")
edit = require_rbac_permission("whatsapp", "edit")


def _service(db: Session, actor: AuthorizedTenantActor) -> GestorService:
    return GestorService(db, actor.tenant_id, actor.user_id, actor.tenant_context)


def _contact_out(item) -> GestorContactOut:
    return GestorContactOut.model_validate(item)


def _operation_out(item) -> GestorOperationOut:
    preview = dict(item.preview_json or {})
    preview.pop("_execution_result", None)
    return GestorOperationOut.model_validate({
        "id": item.id,
        "channel": item.channel,
        "phone": item.phone,
        "tool_name": item.tool_name,
        "risk_level": item.risk_level,
        "status": item.status,
        "arguments": item.arguments_json,
        "preview": preview,
        "idempotency_key": item.idempotency_key,
        "confirmation_expires_at": item.confirmation_expires_at,
        "executed_at": item.executed_at,
        "error": item.error,
        "result": GestorService._stored_result(item),
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    })


def _channel_out(item) -> GestorWhatsAppChannelOut | None:
    if item is None:
        return None
    return GestorWhatsAppChannelOut.model_validate({
        "id": item.id, "tenant_id": item.tenant_id, "enabled": item.enabled,
        "phone_number_id": GestorService._mask_identifier(item.phone_number_id),
        "business_account_id": GestorService._mask_identifier(item.business_account_id),
        "display_phone_number": item.display_phone_number,
        "app_secret_ref": GestorService._mask_identifier(item.app_secret_ref),
        "access_token_ref": GestorService._mask_identifier(item.access_token_ref),
        "integration_connection_id": item.integration_connection_id,
        "status": item.status, "last_error": item.last_error,
        "created_at": item.created_at, "updated_at": item.updated_at,
    })


def _multimodal_out(item) -> GestorMultimodalOut:
    return GestorMultimodalOut.model_validate({
        "id": item.id, "media_type": item.media_type, "mime_type": item.mime_type,
        "original_filename": item.original_filename, "size_bytes": item.size_bytes,
        "content_sha256": item.content_sha256, "storage_key": item.storage_key,
        "idempotency_key": item.idempotency_key, "status": item.status,
        "review_required": item.review_required, "review_reason": item.review_reason,
        "extracted_text": item.extracted_text, "confidence": item.confidence,
        "processor": item.processor, "source_message_id": item.source_message_id,
        "metadata_json": item.metadata_json or {}, "error": item.error,
        "created_at": item.created_at, "updated_at": item.updated_at,
        "processed_at": item.processed_at,
    })


def _automation_out(item) -> GestorAutomationOut:
    return GestorAutomationOut.model_validate(GestorService._automation_payload(item))


def _automation_run_out(item) -> GestorAutomationRunOut:
    return GestorAutomationRunOut.model_validate({
        "id": item.id, "automation_id": item.automation_id, "event_id": item.event_id,
        "status": item.status, "action_count": item.action_count, "cost_units": item.cost_units,
        "operation_ids": item.operation_ids_json or [], "details": item.details_json or {},
        "created_at": item.created_at, "updated_at": item.updated_at,
    })


def _public_whatsapp_error(exc: DomainError):
    status = 401 if exc.code == "GestorWhatsAppSignatureInvalid" else 403
    if exc.code == "GestorWhatsAppSecretUnavailable":
        status = 503
    return err_msg(exc.message, code=exc.code, status_code=status)


@router.get("/tools", response_model=list[GestorToolCatalogItem])
def list_tools(actor: AuthorizedTenantActor = Depends(view)):
    return GestorService.tool_catalog()


@router.get("/ai/settings", response_model=GestorAISettingsOut)
def get_ai_settings(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    return GestorAISettingsOut.model_validate(_service(db, actor).get_ai_settings())


@router.put("/ai/settings", response_model=GestorAISettingsOut)
def update_ai_settings(body: GestorAISettingsUpdate, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        return GestorAISettingsOut.model_validate(_service(db, actor).update_ai_settings(body))
    except DomainError as exc:
        return err(exc)


@router.get("/ai/status", response_model=GestorAIProviderStatusOut)
def ai_status(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    return _service(db, actor).ai_status()


@router.post("/ai/plan", response_model=GestorAIPlanOut)
def plan_ai(body: GestorAIPlanIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    try:
        return _service(db, actor).plan_ai(body)
    except DomainError as exc:
        return err(exc)


@router.post("/tools/execute", response_model=GestorToolExecuteOut)
def execute_tool(body: GestorToolExecuteIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    try:
        operation, result = _service(db, actor).execute_tool(body)
        return GestorToolExecuteOut(operation=_operation_out(operation), result=result)
    except DomainError as exc:
        return err(exc)


@router.get("/contacts", response_model=list[GestorContactOut])
def list_contacts(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    return [_contact_out(item) for item in _service(db, actor).list_contacts()]


@router.post("/contacts", response_model=GestorContactOut, status_code=201)
def create_contact(body: GestorContactCreate, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        return _contact_out(_service(db, actor).create_contact(body))
    except DomainError as exc:
        return err(exc)


@router.patch("/contacts/{contact_id}", response_model=GestorContactOut)
def update_contact(contact_id: str, body: GestorContactUpdate, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        return _contact_out(_service(db, actor).update_contact(contact_id, body))
    except DomainError as exc:
        return err(exc)


@router.post("/operations/preview", response_model=GestorOperationPreviewOut, status_code=201)
def preview_operation(body: GestorOperationPreviewIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        operation, token = _service(db, actor).create_operation(body)
        return GestorOperationPreviewOut(
            operation=_operation_out(operation),
            confirmation_token=token,
            execution_note=(
                "Confirmada apenas a intencao. A execucao exige confirmacao e uma chamada separada "
                "com operation_id; nenhuma confirmacao implicita sera aceita."
            ),
        )
    except DomainError as exc:
        return err(exc)


@router.post("/operations/{operation_id}/confirm", response_model=GestorOperationOut)
def confirm_operation(operation_id: str, body: GestorOperationConfirmIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        return _operation_out(_service(db, actor).confirm_operation(operation_id, body.confirmation_token))
    except DomainError as exc:
        return err(exc)


@router.get("/operations", response_model=list[GestorOperationOut])
def list_operations(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    return [_operation_out(item) for item in _service(db, actor).list_operations(limit)]


@router.get("/whatsapp/channel", response_model=GestorWhatsAppChannelOut | None)
def get_whatsapp_channel(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    return _channel_out(_service(db, actor).get_whatsapp_channel())


@router.put("/whatsapp/channel", response_model=GestorWhatsAppChannelOut)
def update_whatsapp_channel(body: GestorWhatsAppChannelUpdate, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        return _channel_out(_service(db, actor).update_whatsapp_channel(body))
    except DomainError as exc:
        return err(exc)


@router.get("/whatsapp/webhook/meta", include_in_schema=False)
def verify_gestor_meta_webhook(request: Request, db: Session = Depends(get_db)):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and challenge and GestorService.verify_gestor_meta_challenge(db, token):
        return PlainTextResponse(challenge)
    return PlainTextResponse("Forbidden", status_code=403)


@router.post("/whatsapp/webhook/meta", response_model=GestorWhatsAppWebhookOut, include_in_schema=False)
async def receive_gestor_meta_webhook(request: Request, db: Session = Depends(get_db)):
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body)
    except Exception:
        return err_msg("Payload de webhook invalido.", code="GestorWhatsAppPayloadInvalid", status_code=400)
    if not isinstance(payload, dict):
        return err_msg("Payload de webhook invalido.", code="GestorWhatsAppPayloadInvalid", status_code=400)
    try:
        result = GestorService.receive_gestor_meta_webhook(
            db, payload, raw_body, request.headers.get("X-Hub-Signature-256", "")
        )
        db.commit()
        return result
    except DomainError as exc:
        db.rollback()
        return _public_whatsapp_error(exc)


@router.post("/whatsapp/inbox/process", response_model=GestorInboxProcessOut)
def process_gestor_inbox(limit: int = Query(default=20, ge=1, le=50), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        result = _service(db, actor).process_gestor_inbox(limit)
        db.commit()
        return result
    except DomainError as exc:
        db.rollback()
        return err(exc)


@router.get("/whatsapp/inbox", response_model=list[GestorWhatsAppMessageOut])
def list_gestor_inbox(status: str | None = Query(default=None, min_length=1, max_length=24), limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    return [GestorWhatsAppMessageOut.model_validate(item) for item in _service(db, actor).list_gestor_inbox(status, limit)]


@router.post("/whatsapp/outbox/enqueue", response_model=GestorWhatsAppEnqueueOut)
def enqueue_gestor_whatsapp_message(body: GestorWhatsAppEnqueueIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        item, replay, policy = _service(db, actor).enqueue_whatsapp_message(str(body.operation_id))
        db.commit()
        return GestorWhatsAppEnqueueOut(
            outbox=GestorWhatsAppOutboxOut.model_validate(GestorService.serialize_whatsapp_outbox(item)),
            idempotent_replay=replay, policy=policy,
        )
    except DomainError as exc:
        db.rollback()
        return err(exc)


@router.get("/whatsapp/outbox", response_model=list[GestorWhatsAppOutboxOut])
def list_gestor_whatsapp_outbox(
    status: str | None = Query(default=None, min_length=1, max_length=20),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view),
):
    return [
        GestorWhatsAppOutboxOut.model_validate(GestorService.serialize_whatsapp_outbox(item))
        for item in _service(db, actor).list_whatsapp_outbox(status, limit)
    ]


@router.post("/whatsapp/outbox/process", response_model=GestorWhatsAppOutboxProcessOut)
def process_gestor_whatsapp_outbox(
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit),
):
    try:
        result = _service(db, actor).process_whatsapp_outbox(limit)
        db.commit()
        return result
    except DomainError as exc:
        db.rollback()
        return err(exc)


@router.post("/whatsapp/outbox/{outbox_id}/retry", response_model=GestorWhatsAppOutboxRetryOut)
def retry_gestor_whatsapp_outbox(outbox_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        item = _service(db, actor).retry_whatsapp_outbox(outbox_id)
        db.commit()
        return GestorWhatsAppOutboxRetryOut(
            outbox=GestorWhatsAppOutboxOut.model_validate(GestorService.serialize_whatsapp_outbox(item))
        )
    except DomainError as exc:
        db.rollback()
        return err(exc)


@router.post("/multimodal/ingest", response_model=GestorMultimodalIngestOut, status_code=201)
def ingest_gestor_multimodal(body: GestorMultimodalIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        artifact, replay = _service(db, actor).ingest_multimodal(body)
        db.commit()
        return GestorMultimodalIngestOut(artifact=_multimodal_out(artifact), idempotent_replay=replay)
    except DomainError as exc:
        db.rollback()
        return err(exc)


@router.post("/multimodal/upload", response_model=GestorMultimodalIngestOut, status_code=201)
async def upload_gestor_multimodal(
    file: UploadFile = File(...),
    media_type: str = Query(..., pattern="^(text|image|audio|document)$"),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=220),
    db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit),
):
    raw = await file.read()
    body = GestorMultimodalIn(
        media_type=media_type, mime_type=file.content_type, filename=file.filename,
        content_base64=base64.b64encode(raw).decode("ascii"), idempotency_key=idempotency_key,
    )
    try:
        artifact, replay = _service(db, actor).ingest_multimodal(body)
        db.commit()
        return GestorMultimodalIngestOut(artifact=_multimodal_out(artifact), idempotent_replay=replay)
    except DomainError as exc:
        db.rollback()
        return err(exc)


@router.get("/multimodal", response_model=list[GestorMultimodalOut])
def list_gestor_multimodal(
    status: str | None = Query(default=None, min_length=1, max_length=30),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view),
):
    return [_multimodal_out(item) for item in _service(db, actor).list_multimodal(status, limit)]


@router.post("/multimodal/{artifact_id}/review", response_model=GestorMultimodalOut)
def review_gestor_multimodal(
    artifact_id: str, body: GestorMultimodalReviewIn,
    db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit),
):
    try:
        item = _service(db, actor).review_multimodal(artifact_id, body)
        db.commit()
        return _multimodal_out(item)
    except DomainError as exc:
        db.rollback()
        return err(exc)


@router.get("/multimodal/{artifact_id}/audit", response_model=list[GestorMultimodalAuditOut])
def audit_gestor_multimodal(
    artifact_id: str, limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view),
):
    return [GestorMultimodalAuditOut.model_validate(item) for item in _service(db, actor).list_multimodal_audit(artifact_id, limit)]


@router.get("/automations", response_model=list[GestorAutomationOut])
def list_gestor_automations(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view),
):
    return [_automation_out(item) for item in _service(db, actor).list_automations(limit)]


@router.post("/automations", response_model=GestorAutomationOut, status_code=201)
def create_gestor_automation(
    body: GestorAutomationCreate, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit),
):
    try:
        item = _service(db, actor).create_automation(body)
        db.commit()
        return _automation_out(item)
    except DomainError as exc:
        db.rollback()
        return err(exc)


@router.patch("/automations/{automation_id}", response_model=GestorAutomationOut)
def update_gestor_automation(
    automation_id: str, body: GestorAutomationUpdate,
    db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit),
):
    try:
        item = _service(db, actor).update_automation(automation_id, body)
        db.commit()
        return _automation_out(item)
    except DomainError as exc:
        db.rollback()
        return err(exc)


@router.delete("/automations/{automation_id}", response_model=GestorAutomationOut)
def delete_gestor_automation(
    automation_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit),
):
    try:
        item = _service(db, actor).delete_automation(automation_id)
        db.commit()
        return _automation_out(item)
    except DomainError as exc:
        db.rollback()
        return err(exc)


@router.post("/automations/{automation_id}/simulate", response_model=GestorAutomationSimulationOut)
def simulate_gestor_automation(
    automation_id: str, body: GestorAutomationSimulateIn,
    db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view),
):
    try:
        return GestorAutomationSimulationOut.model_validate(_service(db, actor).simulate_automation(automation_id, body))
    except DomainError as exc:
        return err(exc)


@router.post("/automations/events/process", response_model=GestorAutomationProcessOut)
def process_gestor_automation_events(
    limit: int = Query(default=25, ge=1, le=100),
    worker_id: str | None = Query(default=None, max_length=120),
    db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit),
):
    try:
        result = _service(db, actor).process_gestor_automation_events(limit, worker_id)
        db.commit()
        result["runs"] = [_automation_run_out(item) for item in result["runs"]]
        return GestorAutomationProcessOut.model_validate(result)
    except DomainError as exc:
        db.rollback()
        return err(exc)

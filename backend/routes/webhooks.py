from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import err, err_msg, ok
from backend.database import get_db
from backend.schemas.payment import WebhookPayload
from backend.services.payment_service import PaymentService
from backend.config import get_settings
from backend.services.payment_webhook_tenant_resolver import PaymentWebhookTenantResolver

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

def _tenant_payment_service(db: Session, endpoint_key: str, provider: str) -> PaymentService:
    settings = get_settings()
    binding = PaymentWebhookTenantResolver(db, settings.TENANT_PAYMENT_WEBHOOK_ENDPOINTS).resolve(endpoint_key, provider)
    return PaymentService(db, tenant_id=binding.tenant_id)


def _payload_from_query(query_params: dict[str, str]) -> dict:
    data_id = query_params.get("data.id")
    if not data_id:
        return {}
    return {
        "type": query_params.get("type") or "payment",
        "action": query_params.get("action"),
        "data": {"id": data_id},
    }


@router.post("/mercadopago")
async def mercadopago_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_signature: str | None = Header(default=None),
    x_request_id: str | None = Header(default=None),
):
    if get_settings().TENANT_PAYMENT_WEBHOOKS_ENABLED:
        return err_msg("Webhook global desabilitado no modo multiempresa.", code="AmbiguousWebhookEndpoint", status_code=404)
    raw_body = await request.body()
    query_params = dict(request.query_params)

    try:
        body = await request.json() if raw_body else {}
    except Exception:
        body = {}
    body = body or _payload_from_query(query_params)

    try:
        payload = WebhookPayload.model_validate(body)
    except Exception:
        return err_msg("Payload de webhook invalido ou malformado.", code="WebhookParseError")

    try:
        result = PaymentService(db).process_webhook(
            payload,
            raw_body,
            x_signature,
            x_request_id,
            query_params,
        )
        return ok(result)
    except DomainError as exc:
        return err(exc)


@router.post("/asaas")
async def asaas_webhook(
    request: Request,
    db: Session = Depends(get_db),
    asaas_access_token: str | None = Header(default=None),
):
    if get_settings().TENANT_PAYMENT_WEBHOOKS_ENABLED:
        return err_msg("Webhook global desabilitado no modo multiempresa.", code="AmbiguousWebhookEndpoint", status_code=404)
    raw_body = await request.body()
    try:
        body = await request.json() if raw_body else {}
    except Exception:
        return err_msg("Payload de webhook invalido ou malformado.", code="WebhookParseError")

    if not isinstance(body, dict):
        return err_msg("Payload de webhook invalido ou malformado.", code="WebhookParseError")

    try:
        result = PaymentService(db).process_asaas_webhook(body, raw_body, asaas_access_token)
        return ok(result)
    except DomainError as exc:
        return err(exc)

@router.post("/mercadopago/{endpoint_key}")
async def tenant_mercadopago_webhook(endpoint_key: str, request: Request, db: Session = Depends(get_db),
                                     x_signature: str | None = Header(default=None),
                                     x_request_id: str | None = Header(default=None)):
    if not get_settings().TENANT_PAYMENT_WEBHOOKS_ENABLED:
        return err_msg("Endpoint multiempresa desabilitado.", code="TenantWebhookDisabled", status_code=404)
    raw_body = await request.body()
    query_params = dict(request.query_params)
    try:
        body = await request.json() if raw_body else {}
    except Exception:
        body = {}
    body = body or _payload_from_query(query_params)
    try:
        payload = WebhookPayload.model_validate(body)
        service = _tenant_payment_service(db, endpoint_key, "mercado_pago")
        return ok(service.process_webhook(payload, raw_body, x_signature, x_request_id, query_params))
    except DomainError as exc:
        return err(exc)
    except Exception:
        return err_msg("Payload de webhook invalido ou malformado.", code="WebhookParseError")

@router.post("/asaas/{endpoint_key}")
async def tenant_asaas_webhook(endpoint_key: str, request: Request, db: Session = Depends(get_db),
                               asaas_access_token: str | None = Header(default=None)):
    if not get_settings().TENANT_PAYMENT_WEBHOOKS_ENABLED:
        return err_msg("Endpoint multiempresa desabilitado.", code="TenantWebhookDisabled", status_code=404)
    raw_body = await request.body()
    try:
        body = await request.json() if raw_body else {}
    except Exception:
        return err_msg("Payload de webhook invalido ou malformado.", code="WebhookParseError")
    if not isinstance(body, dict):
        return err_msg("Payload de webhook invalido ou malformado.", code="WebhookParseError")
    try:
        service = _tenant_payment_service(db, endpoint_key, "asaas")
        return ok(service.process_asaas_webhook(body, raw_body, asaas_access_token))
    except DomainError as exc:
        return err(exc)

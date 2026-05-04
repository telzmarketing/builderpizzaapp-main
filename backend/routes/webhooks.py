from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import err, err_msg, ok
from backend.database import get_db
from backend.schemas.payment import WebhookPayload
from backend.services.payment_service import PaymentService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


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

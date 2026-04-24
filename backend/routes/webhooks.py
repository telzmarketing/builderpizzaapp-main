from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import err, err_msg, ok
from backend.database import get_db
from backend.schemas.payment import WebhookPayload
from backend.services.payment_service import PaymentService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/mercadopago")
async def mercadopago_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_signature: str | None = Header(default=None),
    x_request_id: str | None = Header(default=None),
):
    raw_body = await request.body()
    try:
        payload = WebhookPayload.model_validate(await request.json())
    except Exception:
        return err_msg("Payload de webhook inválido ou malformado.", code="WebhookParseError")

    try:
        result = PaymentService(db).process_webhook(payload, raw_body, x_signature, x_request_id)
        return ok(result)
    except DomainError as exc:
        return err(exc)

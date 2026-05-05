"""
Payment endpoints shared by loja online and ERP.

All business logic lives in PaymentService.
"""
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import created, err, err_msg, ok
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.models.order import Order
from backend.routes.admin_auth import get_current_admin
from backend.routes.order_access import require_order_or_admin
from backend.schemas.payment import PaymentCreate, WebhookPayload
from backend.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])


def _payload_from_query(query_params: dict[str, str]) -> dict:
    data_id = query_params.get("data.id")
    if not data_id:
        return {}
    return {
        "type": query_params.get("type") or "payment",
        "action": query_params.get("action"),
        "data": {"id": data_id},
    }


@router.post("/create", status_code=201)
def create_payment(body: PaymentCreate, request: Request, db: Session = Depends(get_db)):
    try:
        order = db.query(Order).filter(Order.id == body.order_id).first()
        if order:
            require_order_or_admin(
                order,
                db,
                request.headers.get("authorization"),
                request.headers.get("x-customer-phone"),
                request.headers.get("x-customer-email"),
            )
        payment = PaymentService(db).create(body)
        return created(payment, "Pagamento iniciado. Aguardando confirmacao.")
    except DomainError as exc:
        return err(exc)


@router.get("/public-key")
def get_public_key(db: Session = Depends(get_db)):
    return ok(PaymentService(db).public_key())


@router.get("/methods")
def get_payment_methods(db: Session = Depends(get_db)):
    return ok(PaymentService(db).accepted_methods())


@router.get("/{order_id}")
def get_payment(order_id: str, request: Request, db: Session = Depends(get_db)):
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order:
            require_order_or_admin(
                order,
                db,
                request.headers.get("authorization"),
                request.headers.get("x-customer-phone"),
                request.headers.get("x-customer-email"),
            )
        return ok(PaymentService(db).get_by_order(order_id))
    except DomainError as exc:
        return err(exc)


@router.post("/preference/{order_id}", status_code=201)
def create_preference(order_id: str, request: Request, db: Session = Depends(get_db)):
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order:
            require_order_or_admin(
                order,
                db,
                request.headers.get("authorization"),
                request.headers.get("x-customer-phone"),
                request.headers.get("x-customer-email"),
            )
        result = PaymentService(db).create_preference(order_id)
        return created(result, "Preferencia de pagamento criada.")
    except DomainError as exc:
        return err(exc)


@router.post("/cash/{order_id}")
def confirm_cash(
    order_id: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    try:
        payment = PaymentService(db).confirm_cash(order_id)
        return ok(payment, "Pagamento em dinheiro confirmado.")
    except DomainError as exc:
        return err(exc)


@router.post("/webhook")
async def payment_webhook(
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

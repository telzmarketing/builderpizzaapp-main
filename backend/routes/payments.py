"""
Payment endpoints — shared by loja online and ERP.

All business logic lives in PaymentService.

Endpoints:
  POST /payments/create          → initiate payment (generates PIX / checkout link)
  GET  /payments/{order_id}      → get payment status for an order
  POST /payments/cash/{order_id} → ERP/cashier: confirm cash payment
  POST /payments/webhook         → gateway callback (Mercado Pago, Stripe, etc.)

State machine flow triggered here:
  create()       → order: pending      → waiting_payment
  confirm()      → order: waiting_payment → paid
  confirm_cash() → order: pending      → waiting_payment → paid  (atomic)
"""
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import ok, created, err, err_msg
from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.routes.order_access import require_order_or_admin
from backend.models.admin import AdminUser
from backend.models.order import Order
from backend.schemas.payment import PaymentCreate, WebhookPayload
from backend.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])


# ── Create payment ────────────────────────────────────────────────────────────

@router.post("/create", status_code=201)
def create_payment(body: PaymentCreate, request: Request, db: Session = Depends(get_db)):
    """
    Initiate a payment for a pending order.

    - Validates order exists and is in 'pending' status
    - Prevents duplicate payments (idempotency)
    - Validates amount == order.total (±R$0,01)
    - Calls the configured gateway (Mercado Pago / Stripe / mock)
    - Advances order status to **waiting_payment**

    Response includes:
      - PIX: qr_code (base64 image), qr_code_text (copy & paste)
      - Card: payment_url (checkout link)
    """
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
        return created(payment, "Pagamento iniciado. Aguardando confirmação.")
    except DomainError as exc:
        return err(exc)


@router.get("/public-key")
def get_public_key(db: Session = Depends(get_db)):
    return ok(PaymentService(db).public_key())


# ── Get payment ───────────────────────────────────────────────────────────────

@router.get("/{order_id}")
def get_payment(order_id: str, request: Request, db: Session = Depends(get_db)):
    """Return the payment record associated with an order."""
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


# ── Cash confirmation (ERP / cashier) ────────────────────────────────────────

@router.post("/cash/{order_id}")
def confirm_cash(
    order_id: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    """
    ERP / cashier: mark a cash-on-delivery order as paid.

    Creates a payment record (method=cash) if none exists.
    Transitions: pending → waiting_payment → paid atomically.
    Used for in-store pickup or cash delivery confirmation.
    """
    try:
        payment = PaymentService(db).confirm_cash(order_id)
        return ok(payment, "Pagamento em dinheiro confirmado.")
    except DomainError as exc:
        return err(exc)


# ── Webhook ───────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def payment_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_signature: str | None = Header(default=None),
    x_request_id: str | None = Header(default=None),
):
    """
    Receive payment gateway callbacks (Mercado Pago, Stripe, PagSeguro).

    Security:
      - Validates HMAC signature (x-signature header for MP)
      - Re-fetches payment status from gateway API — never trusts the payload alone

    On confirmed payment:
      - payment.status → paid
      - order.status   → paid   (via state machine)
      - Publishes PaymentConfirmed event → ERP (NF-e emission) + push notification

    Returns 200 even for ignored events (no transaction_id, already processed).
    Returning non-2xx would cause the gateway to retry indefinitely.
    """
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

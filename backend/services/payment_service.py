"""
PaymentService — all payment operations are centralized here.

RULE: no route or ERP integration may change payment.status directly.
      Every change goes through PaymentService which enforces the payment
      state machine and keeps the order status in sync atomically.
"""
from __future__ import annotations

import hashlib
import hmac
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.core.exceptions import (
    OrderNotFound, PaymentAlreadyExists, PaymentAmountMismatch,
    PaymentNotFound, PaymentOrderNotEligible,
    GatewayError, GatewayNotConfigured, WebhookSignatureInvalid,
)
from backend.core.state_machine import payment_sm, order_sm
from backend.core.events import (
    bus, PaymentCreated, PaymentConfirmed, PaymentFailed,
)
from backend.models.payment import Payment, PaymentMethod, PaymentStatus
from backend.models.payment_config import PaymentGatewayConfig
from backend.models.order import Order, OrderStatus
from backend.schemas.payment import PaymentCreate, PaymentOut, WebhookPayload
from backend.config import get_settings

settings = get_settings()


# ── Gateway interface ─────────────────────────────────────────────────────────

class GatewayInterface(ABC):

    @abstractmethod
    def create_payment(self, payment: Payment, config: PaymentGatewayConfig) -> dict:
        """Return fields to persist on the Payment model (transaction_id, qr_code, etc.)."""
        ...

    @abstractmethod
    def verify_webhook(
        self, payload: dict, signature: str | None, config: PaymentGatewayConfig
    ) -> bool:
        """Validate the webhook signature. Return True if authentic."""
        ...

    def fetch_status(self, transaction_id: str, config: PaymentGatewayConfig) -> str:
        """
        Query the gateway for the current payment status.
        Override in real gateways to avoid trusting the webhook body alone.
        Returns a normalized status: "paid" | "pending" | "failed".
        """
        return "pending"


# ── Mock gateway ──────────────────────────────────────────────────────────────

class MockGateway(GatewayInterface):
    """Development / testing — never charges real money."""

    def create_payment(self, payment: Payment, config: PaymentGatewayConfig) -> dict:
        tid = f"MOCK-{uuid.uuid4().hex[:12].upper()}"
        if payment.method == PaymentMethod.pix:
            code = hashlib.md5(tid.encode()).hexdigest()
            name = (config.pix_beneficiary_name or "PizzaApp")[:25]
            city = (config.pix_beneficiary_city or "SAO PAULO")[:15]
            return {
                "transaction_id": tid,
                "qr_code": f"data:image/png;base64,MOCK_QR_{code}",
                "qr_code_text": (
                    f"00020126330014BR.GOV.BCB.PIX0111{code}"
                    f"5204000053039865802BR5913{name}6009{city}"
                    f"62070503***6304{code[:4].upper()}"
                ),
            }
        return {
            "transaction_id": tid,
            "payment_url": f"https://pay.mock.dev/checkout/{tid}",
        }

    def verify_webhook(self, payload: dict, signature: str | None, config: PaymentGatewayConfig) -> bool:
        return True

    def fetch_status(self, transaction_id: str, config: PaymentGatewayConfig) -> str:
        return "paid"   # mock always succeeds


# ── Mercado Pago ──────────────────────────────────────────────────────────────

class MercadoPagoGateway(GatewayInterface):

    def _sdk(self, config: PaymentGatewayConfig):
        import mercadopago
        if not config.mp_access_token:
            raise GatewayNotConfigured("mercadopago", "mp_access_token")
        return mercadopago.SDK(config.mp_access_token)

    def create_payment(self, payment: Payment, config: PaymentGatewayConfig) -> dict:
        sdk = self._sdk(config)
        if payment.method == PaymentMethod.pix:
            body = {
                "transaction_amount": round(payment.amount, 2),
                "payment_method_id": "pix",
                "description": f"Pedido #{payment.order_id}",
                "payer": {"email": "cliente@pizzaapp.com"},
            }
            result = sdk.payment().create(body)
            response = result.get("response", {})
            _mp_raise_if_error(result, response)
            poi = response.get("point_of_interaction", {})
            tx = poi.get("transaction_data", {})
            return {
                "transaction_id": str(response["id"]),
                "qr_code": tx.get("qr_code_base64", ""),
                "qr_code_text": tx.get("qr_code", ""),
            }
        # Checkout Pro (card / other methods)
        result = sdk.preference().create({
            "items": [{
                "id": payment.order_id,
                "title": f"Pedido #{payment.order_id}",
                "quantity": 1,
                "unit_price": round(payment.amount, 2),
                "currency_id": "BRL",
            }],
            "external_reference": payment.order_id,
            "notification_url": "https://seudominio.com/payments/webhook",
            "back_urls": {
                "success": "https://seudominio.com/order-tracking",
                "failure": "https://seudominio.com/cart",
                "pending": "https://seudominio.com/order-tracking",
            },
            "auto_return": "approved",
        })
        response = result.get("response", {})
        _mp_raise_if_error(result, response)
        url_key = "sandbox_init_point" if config.sandbox else "init_point"
        return {
            "transaction_id": response.get("id", ""),
            "payment_url": response.get(url_key, response.get("init_point", "")),
        }

    def verify_webhook(self, payload: dict, signature: str | None, config: PaymentGatewayConfig) -> bool:
        if not config.mp_webhook_secret or not signature:
            return True
        try:
            parts = dict(p.split("=", 1) for p in signature.split(","))
            ts, v1 = parts.get("ts", ""), parts.get("v1", "")
            data_id = payload.get("data", {}).get("id", "")
            request_id = payload.get("id", "")
            manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
            expected = hmac.new(
                config.mp_webhook_secret.encode(),
                manifest.encode(),
                hashlib.sha256,
            ).hexdigest()
            return hmac.compare_digest(expected, v1)
        except Exception:
            return False

    def fetch_status(self, transaction_id: str, config: PaymentGatewayConfig) -> str:
        try:
            sdk = self._sdk(config)
            result = sdk.payment().get(transaction_id)
            mp_status = result.get("response", {}).get("status", "pending")
            return _normalize_mp_status(mp_status)
        except Exception:
            return "pending"


# ── Stripe (structure ready) ──────────────────────────────────────────────────

class StripeGateway(GatewayInterface):

    def create_payment(self, payment: Payment, config: PaymentGatewayConfig) -> dict:
        if not config.stripe_secret_key:
            raise GatewayNotConfigured("stripe", "stripe_secret_key")
        # import stripe
        # stripe.api_key = config.stripe_secret_key
        # intent = stripe.PaymentIntent.create(
        #     amount=int(payment.amount * 100),
        #     currency="brl",
        #     metadata={"order_id": payment.order_id},
        # )
        # return {"transaction_id": intent.id, "client_secret": intent.client_secret}
        raise GatewayError("stripe", "SDK não instalado. Execute: pip install stripe")

    def verify_webhook(self, payload: dict, signature: str | None, config: PaymentGatewayConfig) -> bool:
        if not config.stripe_webhook_secret or not signature:
            return True
        # import stripe
        # stripe.Webhook.construct_event(payload, signature, config.stripe_webhook_secret)
        return True


# ── PagSeguro (structure ready) ───────────────────────────────────────────────

class PagSeguroGateway(GatewayInterface):

    def create_payment(self, payment: Payment, config: PaymentGatewayConfig) -> dict:
        if not config.pagseguro_token:
            raise GatewayNotConfigured("pagseguro", "pagseguro_token")
        raise GatewayError("pagseguro", "Implementação REST pendente.")

    def verify_webhook(self, payload: dict, signature: str | None, config: PaymentGatewayConfig) -> bool:
        return True


# ── Factory ───────────────────────────────────────────────────────────────────

_GATEWAYS: dict[str, type[GatewayInterface]] = {
    "mock":        MockGateway,
    "mercadopago": MercadoPagoGateway,
    "stripe":      StripeGateway,
    "pagseguro":   PagSeguroGateway,
}


def _get_gateway(config: PaymentGatewayConfig) -> GatewayInterface:
    cls = _GATEWAYS.get(config.gateway, MockGateway)
    return cls()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mp_raise_if_error(result: dict, response: dict) -> None:
    status = result.get("status")
    if status and int(status) >= 400:
        error = response.get("message") or response.get("error") or f"HTTP {status}"
        cause = response.get("cause", [])
        detail = cause[0].get("description", "") if cause else ""
        raise GatewayError("mercadopago", f"{error}. {detail}".strip(" ."))


def _normalize_mp_status(mp_status: str) -> str:
    mapping = {
        "approved": "paid", "authorized": "paid",
        "in_process": "pending", "pending": "pending", "in_mediation": "pending",
        "rejected": "failed", "cancelled": "failed", "refunded": "failed",
        "charged_back": "failed",
    }
    return mapping.get(mp_status.lower(), "pending")


def _load_config(db: Session) -> PaymentGatewayConfig:
    config = db.query(PaymentGatewayConfig).filter(
        PaymentGatewayConfig.id == "default"
    ).first()
    if not config:
        config = PaymentGatewayConfig(id="default")
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


# ── PaymentService ────────────────────────────────────────────────────────────

class PaymentService:
    """
    Single authority for payment creation, confirmation and refunds.

    Both the loja REST API and the ERP use this class.
    Status changes are validated by the payment state machine
    and automatically propagate to the order state machine.
    """

    def __init__(self, db: Session):
        self._db = db
        self._config: PaymentGatewayConfig | None = None

    def _cfg(self) -> PaymentGatewayConfig:
        if not self._config:
            self._config = _load_config(self._db)
        return self._config

    def _get_payment_by_order(self, order_id: str) -> Payment:
        p = self._db.query(Payment).filter(Payment.order_id == order_id).first()
        if not p:
            raise PaymentNotFound(order_id)
        return p

    # ── Create ────────────────────────────────────────────────────────────────

    def create(self, payload: PaymentCreate) -> PaymentOut:
        """
        Create a payment for an existing order in 'pending' status.

        Flow:
          1. Validate order exists, is in 'pending', has no payment yet, amount matches.
          2. Call gateway → obtain transaction_id / QR code / payment_url.
          3. Advance order:  pending → waiting_payment  (via state machine).
          4. Persist Payment + order status atomically.
          5. Publish PaymentCreated event.
        """
        order: Order | None = self._db.query(Order).filter(
            Order.id == payload.order_id
        ).first()
        if not order:
            raise OrderNotFound(payload.order_id)

        # Idempotency guard: block if payment already exists
        if order.payment:
            raise PaymentAlreadyExists(payload.order_id)

        # Order must be in 'pending' to start a payment
        if order.status != OrderStatus.pending:
            raise PaymentOrderNotEligible(payload.order_id, order.status.value)

        if abs(order.total - payload.amount) > 0.01:
            raise PaymentAmountMismatch(order.total, payload.amount)

        cfg = self._cfg()
        payment = Payment(
            id=str(uuid.uuid4()),
            order_id=order.id,
            method=PaymentMethod(payload.payment_method),
            status=PaymentStatus.pending,
            amount=payload.amount,
            gateway=cfg.gateway,
        )
        self._db.add(payment)
        self._db.flush()

        gateway = _get_gateway(cfg)
        try:
            gw_data = gateway.create_payment(payment, cfg)
        except (GatewayError, GatewayNotConfigured):
            self._db.rollback()
            raise
        except Exception as exc:
            self._db.rollback()
            raise GatewayError(cfg.gateway, str(exc)) from exc

        for key, value in gw_data.items():
            setattr(payment, key, value)

        # Advance order: pending → waiting_payment
        # This signals the payment window is open; order cannot be modified.
        order_sm.transition(order.id, order.status.value, "waiting_payment")
        order.status = OrderStatus.waiting_payment

        self._db.commit()
        self._db.refresh(payment)

        bus.publish(PaymentCreated(
            payment_id=payment.id,
            order_id=payment.order_id,
            method=payment.method.value,
            amount=payment.amount,
            gateway=payment.gateway,
        ))

        return PaymentOut.model_validate(payment)

    # ── Confirm (used by webhook AND manual ERP confirmation) ─────────────────

    def confirm(self, payment: Payment, *, transaction_id: str | None = None) -> None:
        """
        Mark a payment as paid. Updates order status via order state machine.
        Can be called from webhook handler OR from ERP (e.g. cash payment).
        """
        current = payment.status.value
        payment_sm.transition(payment.id, current, "paid")

        payment.status = PaymentStatus.paid
        payment.paid_at = datetime.now(timezone.utc)
        if transaction_id:
            payment.transaction_id = transaction_id

        # Propagate to order — go through order state machine
        order: Order = self._db.query(Order).filter(
            Order.id == payment.order_id
        ).first()
        if order:
            order_sm.transition(order.id, order.status.value, "paid")
            order.status = OrderStatus.paid

        self._db.commit()

        bus.publish(PaymentConfirmed(
            payment_id=payment.id,
            order_id=payment.order_id,
            amount=payment.amount,
            gateway=payment.gateway,
            transaction_id=payment.transaction_id or "",
        ))

    def fail(self, payment: Payment, *, reason: str = "") -> None:
        """Mark a payment as failed. Order remains in 'pending'."""
        current = payment.status.value
        payment_sm.transition(payment.id, current, "failed")
        payment.status = PaymentStatus.failed
        self._db.commit()

        bus.publish(PaymentFailed(
            payment_id=payment.id,
            order_id=payment.order_id,
            reason=reason,
        ))

    # ── Webhook ───────────────────────────────────────────────────────────────

    def process_webhook(
        self,
        payload: WebhookPayload,
        raw_body: bytes,
        signature: str | None,
    ) -> dict:
        """
        Receive, validate and process gateway callback.
        This is the only entry point for external payment notifications.
        """
        cfg = self._cfg()
        gateway = _get_gateway(cfg)

        if not gateway.verify_webhook(payload.model_dump(), signature, cfg):
            raise WebhookSignatureInvalid()

        # Normalize MP format: data.id → transaction_id
        transaction_id = payload.transaction_id
        if payload.data and not transaction_id:
            transaction_id = str(payload.data.get("id", ""))

        if not transaction_id:
            return {"status": "ignored", "reason": "no transaction_id"}

        payment = self._db.query(Payment).filter(
            Payment.transaction_id == transaction_id
        ).first()
        if not payment:
            return {"status": "ignored", "reason": f"transaction '{transaction_id}' not found"}

        # Re-fetch status from gateway (do not trust webhook payload alone)
        confirmed_status = gateway.fetch_status(transaction_id, cfg)

        if confirmed_status == "paid" and payment.status != PaymentStatus.paid:
            self.confirm(payment, transaction_id=transaction_id)
        elif confirmed_status == "failed" and payment.status == PaymentStatus.pending:
            self.fail(payment, reason="Gateway reported failure")

        return {"status": "ok", "payment_status": confirmed_status}

    # ── ERP: manual cash confirmation ─────────────────────────────────────────

    def confirm_cash(self, order_id: str) -> PaymentOut:
        """
        Used by ERP / cashier to mark a cash-on-delivery payment as paid.
        Creates a payment record if none exists.

        Respects the full state machine flow:
          pending → waiting_payment → paid
        Both transitions happen atomically within this call.
        """
        order = self._db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise OrderNotFound(order_id)

        if not order.payment:
            payment = Payment(
                id=str(uuid.uuid4()),
                order_id=order.id,
                method=PaymentMethod.cash,
                status=PaymentStatus.pending,
                amount=order.total,
                gateway="cash",
                transaction_id=f"CASH-{uuid.uuid4().hex[:8].upper()}",
            )
            self._db.add(payment)
            self._db.flush()

            # Cash payments start from 'pending' → advance to waiting_payment first
            if order.status == OrderStatus.pending:
                order_sm.transition(order.id, "pending", "waiting_payment")
                order.status = OrderStatus.waiting_payment
                self._db.flush()
        else:
            payment = order.payment

        self.confirm(payment)
        self._db.refresh(payment)
        return PaymentOut.model_validate(payment)

    def get_by_order(self, order_id: str) -> PaymentOut:
        payment = self._get_payment_by_order(order_id)
        return PaymentOut.model_validate(payment)


# ── Module-level helpers (backward compat with existing routes) ───────────────

def create_payment(payload: PaymentCreate, db: Session) -> PaymentOut:
    return PaymentService(db).create(payload)


def process_webhook(
    payload: WebhookPayload, raw_body: bytes, signature: str | None, db: Session
) -> dict:
    return PaymentService(db).process_webhook(payload, raw_body, signature)

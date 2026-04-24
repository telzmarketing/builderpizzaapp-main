"""
PaymentService - Mercado Pago Payment Brick flow.

Rules:
- The frontend never marks an order as paid.
- Payment approval is applied only after webhook processing re-fetches the
  payment from Mercado Pago.
- Existing cash/manual flow remains available for ERP/backoffice use.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.events import bus, PaymentConfirmed, PaymentCreated, PaymentFailed
from backend.core.exceptions import (
    GatewayError,
    GatewayNotConfigured,
    OrderNotFound,
    PaymentAmountMismatch,
    PaymentNotFound,
    PaymentOrderNotEligible,
    WebhookSignatureInvalid,
)
from backend.core.state_machine import order_sm, payment_sm
from backend.models.order import Order, OrderStatus
from backend.models.payment import Payment, PaymentEvent, PaymentMethod, PaymentStatus
from backend.models.payment_config import PaymentGatewayConfig
from backend.schemas.payment import PaymentCreate, PaymentOut, WebhookPayload
from backend.services.saipos_service import sendOrderToSaipos

settings = get_settings()
MP_API_BASE = "https://api.mercadopago.com"


def _provider_name(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw in {"mercado_pago", "mercadopago", "mp"}:
        return "mercado_pago"
    return raw or "mock"


def _load_config(db: Session) -> PaymentGatewayConfig:
    config = db.query(PaymentGatewayConfig).filter(PaymentGatewayConfig.id == "default").first()
    if not config:
        config = PaymentGatewayConfig(id="default")
        db.add(config)
        db.flush()

    provider = _provider_name(settings.PAYMENT_PROVIDER or settings.PAYMENT_GATEWAY or config.gateway)
    if provider == "mercado_pago":
        config.gateway = "mercadopago"
        config.mp_access_token = settings.MERCADO_PAGO_ACCESS_TOKEN or config.mp_access_token
        config.mp_public_key = settings.MERCADO_PAGO_PUBLIC_KEY or config.mp_public_key
        config.mp_webhook_secret = settings.MERCADO_PAGO_WEBHOOK_SECRET or config.mp_webhook_secret

    db.commit()
    db.refresh(config)
    return config


def _mp_token(config: PaymentGatewayConfig) -> str:
    token = settings.MERCADO_PAGO_ACCESS_TOKEN or config.mp_access_token
    if not token:
        raise GatewayNotConfigured("mercado_pago", "MERCADO_PAGO_ACCESS_TOKEN")
    return token


def _mp_request(method: str, path: str, token: str, body: dict[str, Any] | None = None, *, idempotency_key: str | None = None) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if idempotency_key:
        headers["X-Idempotency-Key"] = idempotency_key

    req = Request(f"{MP_API_BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload) if payload else {}
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise GatewayError("mercado_pago", detail or f"HTTP {exc.code}") from exc
    except URLError as exc:
        raise GatewayError("mercado_pago", str(exc.reason)) from exc


def _payment_method(form_data: dict[str, Any], fallback: PaymentMethod | None) -> PaymentMethod:
    if fallback:
        return fallback
    method_id = str(form_data.get("payment_method_id") or "")
    type_id = str(form_data.get("payment_type_id") or "")
    if method_id == "pix":
        return PaymentMethod.pix
    if type_id == "debit_card":
        return PaymentMethod.debit_card
    return PaymentMethod.credit_card


def _mp_status_to_payment(mp_status: str, status_detail: str | None = None) -> PaymentStatus:
    status = (mp_status or "").lower()
    detail = (status_detail or "").lower()
    if status == "approved":
        return PaymentStatus.approved
    if status in {"rejected", "charged_back"}:
        return PaymentStatus.rejected
    if status in {"cancelled", "canceled"}:
        return PaymentStatus.cancelled
    if status == "expired" or "expired" in detail:
        return PaymentStatus.expired
    if status == "refunded":
        return PaymentStatus.refunded
    return PaymentStatus.pending


def _order_status_for_payment(status: PaymentStatus) -> OrderStatus | None:
    if status == PaymentStatus.approved:
        return OrderStatus.pago
    if status == PaymentStatus.rejected:
        return OrderStatus.pagamento_recusado
    if status in {PaymentStatus.cancelled, PaymentStatus.expired}:
        return OrderStatus.pagamento_expirado
    return None


def _allowed_order_transition(order: Order, to_status: OrderStatus) -> bool:
    current = order.status.value if hasattr(order.status, "value") else str(order.status)
    return order_sm.can_transition(current, to_status.value)


class PaymentService:
    def __init__(self, db: Session):
        self._db = db
        self._config: PaymentGatewayConfig | None = None

    def _cfg(self) -> PaymentGatewayConfig:
        if self._config is None:
            self._config = _load_config(self._db)
        return self._config

    def public_key(self) -> dict[str, str]:
        cfg = self._cfg()
        return {"public_key": settings.MERCADO_PAGO_PUBLIC_KEY or cfg.mp_public_key or ""}

    def _get_order(self, order_id: str) -> Order:
        order = self._db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise OrderNotFound(order_id)
        return order

    def _get_payment_by_order(self, order_id: str) -> Payment:
        payment = self._db.query(Payment).filter(Payment.order_id == order_id).first()
        if not payment:
            raise PaymentNotFound(order_id)
        return payment

    def _pending_payment(self, order: Order, payload: PaymentCreate, amount: float, method: PaymentMethod, provider: str) -> Payment:
        payment = order.payment
        if payment and payment.status == PaymentStatus.approved:
            return payment
        if not payment:
            payment = Payment(
                id=str(uuid.uuid4()),
                order_id=order.id,
                method=method,
                status=PaymentStatus.pending,
                amount=amount,
                gateway="mercadopago" if provider == "mercado_pago" else provider,
                provider=provider,
                external_reference=order.external_reference or order.id,
            )
            self._db.add(payment)
            self._db.flush()
        else:
            payment.method = method
            payment.status = PaymentStatus.pending
            payment.amount = amount
            payment.provider = provider
            payment.gateway = "mercadopago" if provider == "mercado_pago" else provider
            payment.external_reference = order.external_reference or order.id
        return payment

    def create(self, payload: PaymentCreate) -> PaymentOut:
        order = self._get_order(payload.order_id)
        current_order_status = order.status.value if hasattr(order.status, "value") else str(order.status)
        if current_order_status not in {"pending", "waiting_payment", "aguardando_pagamento", "pagamento_recusado", "pagamento_expirado"}:
            raise PaymentOrderNotEligible(order.id, current_order_status)

        form_data = payload.form_data or payload.model_dump(exclude_none=True)
        amount = float(payload.amount or form_data.get("transaction_amount") or form_data.get("amount") or order.total)
        if abs(order.total - amount) > 0.01:
            raise PaymentAmountMismatch(order.total, amount)

        cfg = self._cfg()
        provider = _provider_name(settings.PAYMENT_PROVIDER or cfg.gateway)
        method = _payment_method(form_data, payload.payment_method)
        if provider != "mercado_pago":
            provider = "mock"

        if not order.external_reference:
            order.external_reference = f"order-{order.id}"

        if current_order_status == "pending":
            order_sm.transition(order.id, current_order_status, "aguardando_pagamento")
            order.status = OrderStatus.aguardando_pagamento
            self._db.flush()

        payment = self._pending_payment(order, payload, amount, method, provider)

        if provider == "mock":
            payment.transaction_id = payment.transaction_id or f"MOCK-{uuid.uuid4().hex[:12].upper()}"
            self._db.commit()
            self._db.refresh(payment)
            return PaymentOut.model_validate(payment)

        body = self._build_mp_payment_body(order, payment, form_data, amount)
        idempotency_key = hashlib.sha256(f"{order.id}:{method.value}:{amount}:{json.dumps(form_data, sort_keys=True, default=str)}".encode()).hexdigest()
        response = _mp_request("POST", "/v1/payments", _mp_token(cfg), body, idempotency_key=idempotency_key)

        mp_id = str(response.get("id", ""))
        payment.mercado_pago_payment_id = mp_id or payment.mercado_pago_payment_id
        payment.transaction_id = mp_id or payment.transaction_id
        payment.external_reference = response.get("external_reference") or payment.external_reference
        payment.raw_response = json.dumps(response, ensure_ascii=False)
        payment.webhook_data = payment.raw_response
        response_status = _mp_status_to_payment(response.get("status", ""), response.get("status_detail"))

        # Approved payments are only finalized by webhook. Immediate failures can be shown to the customer.
        if response_status in {PaymentStatus.rejected, PaymentStatus.cancelled, PaymentStatus.expired}:
            self._apply_status(payment, response_status, source="create_response")
        else:
            payment.status = PaymentStatus.pending
            self._db.commit()

        self._db.refresh(payment)
        bus.publish(PaymentCreated(payment_id=payment.id, order_id=payment.order_id, method=payment.method.value, amount=payment.amount, gateway=payment.gateway))
        return PaymentOut.model_validate(payment)

    def _build_mp_payment_body(self, order: Order, payment: Payment, form_data: dict[str, Any], amount: float) -> dict[str, Any]:
        payer = form_data.get("payer") or {}
        email = payer.get("email") or form_data.get("payer_email") or "cliente@moschettieri.local"
        body: dict[str, Any] = {
            "transaction_amount": round(amount, 2),
            "description": f"Pedido #{order.id}",
            "payment_method_id": form_data.get("payment_method_id") or ("pix" if payment.method == PaymentMethod.pix else None),
            "payer": {"email": email},
            "external_reference": order.external_reference or order.id,
            "metadata": {"order_id": order.id, "payment_id": payment.id},
        }
        if form_data.get("token"):
            body["token"] = form_data["token"]
        if form_data.get("installments"):
            body["installments"] = int(form_data["installments"])
        if form_data.get("issuer_id"):
            body["issuer_id"] = str(form_data["issuer_id"])
        if payer.get("identification"):
            body["payer"]["identification"] = payer["identification"]
        return {k: v for k, v in body.items() if v is not None}

    def _apply_status(self, payment: Payment, status: PaymentStatus, *, source: str) -> bool:
        if payment.status == status:
            return False

        previous = payment.status
        if payment_sm.can_transition(previous.value, status.value):
            payment_sm.transition(payment.id, previous.value, status.value)
        payment.status = status
        payment.updated_at = datetime.now(timezone.utc)
        if status == PaymentStatus.approved:
            payment.paid_at = datetime.now(timezone.utc)

        order = self._db.query(Order).filter(Order.id == payment.order_id).first()
        target_order_status = _order_status_for_payment(status)
        if order and target_order_status and order.status != target_order_status:
            if _allowed_order_transition(order, target_order_status):
                order_sm.transition(order.id, order.status.value, target_order_status.value)
            order.status = target_order_status
            order.updated_at = datetime.now(timezone.utc)

        self._db.commit()

        if status == PaymentStatus.approved and previous != PaymentStatus.approved:
            sendOrderToSaipos(payment.order_id)
            bus.publish(PaymentConfirmed(payment_id=payment.id, order_id=payment.order_id, amount=payment.amount, gateway=payment.gateway, transaction_id=payment.transaction_id or ""))
        elif status in {PaymentStatus.rejected, PaymentStatus.cancelled, PaymentStatus.expired}:
            bus.publish(PaymentFailed(payment_id=payment.id, order_id=payment.order_id, reason=f"{source}:{status.value}"))
        return True

    def process_webhook(self, payload: WebhookPayload, raw_body: bytes, signature: str | None, request_id: str | None = None) -> dict:
        cfg = self._cfg()
        body = payload.model_dump()
        if not self._verify_mercado_pago_signature(body, signature, request_id, cfg):
            raise WebhookSignatureInvalid()

        mp_payment_id = payload.transaction_id or (str(payload.data.get("id")) if payload.data else "")
        event = PaymentEvent(
            id=str(uuid.uuid4()),
            provider="mercado_pago",
            event_type=payload.action or payload.type or "payment",
            mercado_pago_payment_id=mp_payment_id or None,
            raw_payload=raw_body.decode("utf-8", errors="replace"),
        )
        self._db.add(event)
        self._db.flush()

        if not mp_payment_id:
            event.processed_at = datetime.now(timezone.utc)
            self._db.commit()
            return {"status": "ignored", "reason": "no mercado_pago_payment_id"}

        response = _mp_request("GET", f"/v1/payments/{mp_payment_id}", _mp_token(cfg))
        external_reference = response.get("external_reference")
        event.external_reference = external_reference

        payment = (
            self._db.query(Payment).filter(Payment.mercado_pago_payment_id == mp_payment_id).first()
            or self._db.query(Payment).filter(Payment.transaction_id == mp_payment_id).first()
        )
        if not payment and external_reference:
            order = self._db.query(Order).filter(Order.external_reference == external_reference).first()
            if order:
                payment = order.payment
        if not payment:
            event.processed_at = datetime.now(timezone.utc)
            self._db.commit()
            return {"status": "ignored", "reason": f"payment '{mp_payment_id}' not found"}

        payment.mercado_pago_payment_id = mp_payment_id
        payment.transaction_id = mp_payment_id
        payment.external_reference = external_reference or payment.external_reference
        payment.raw_response = json.dumps(response, ensure_ascii=False)
        payment.webhook_data = event.raw_payload

        new_status = _mp_status_to_payment(response.get("status", ""), response.get("status_detail"))
        changed = self._apply_status(payment, new_status, source="webhook")
        event.processed_at = datetime.now(timezone.utc)
        self._db.commit()
        return {"status": "ok", "payment_status": new_status.value, "changed": changed}

    def _verify_mercado_pago_signature(self, payload: dict[str, Any], signature: str | None, request_id: str | None, config: PaymentGatewayConfig) -> bool:
        secret = settings.MERCADO_PAGO_WEBHOOK_SECRET or config.mp_webhook_secret
        if not secret:
            return True
        if not signature:
            return False
        try:
            parts = dict(part.split("=", 1) for part in signature.split(","))
            ts = parts.get("ts", "")
            v1 = parts.get("v1", "")
            data_id = str((payload.get("data") or {}).get("id", ""))
            manifest = f"id:{data_id};request-id:{request_id or ''};ts:{ts};"
            expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, v1)
        except Exception:
            return False

    def confirm_cash(self, order_id: str) -> PaymentOut:
        order = self._get_order(order_id)
        payment = order.payment or Payment(
            id=str(uuid.uuid4()),
            order_id=order.id,
            method=PaymentMethod.cash,
            status=PaymentStatus.pending,
            amount=order.total,
            gateway="cash",
            provider="cash",
            transaction_id=f"CASH-{uuid.uuid4().hex[:8].upper()}",
            external_reference=order.external_reference or order.id,
        )
        self._db.add(payment)
        self._db.flush()
        self._apply_status(payment, PaymentStatus.approved, source="cash")
        self._db.refresh(payment)
        return PaymentOut.model_validate(payment)

    def get_by_order(self, order_id: str) -> PaymentOut:
        return PaymentOut.model_validate(self._get_payment_by_order(order_id))

    def payment_status(self, order_id: str) -> dict:
        order = self._get_order(order_id)
        payment = order.payment
        return {
            "order_id": order.id,
            "pedido_status": order.status.value,
            "payment_status": payment.status.value if payment else "pending",
            "mercado_pago_payment_id": payment.mercado_pago_payment_id if payment else None,
            "external_reference": order.external_reference,
        }


def create_payment(payload: PaymentCreate, db: Session) -> PaymentOut:
    return PaymentService(db).create(payload)


def process_webhook(payload: WebhookPayload, raw_body: bytes, signature: str | None, db: Session) -> dict:
    return PaymentService(db).process_webhook(payload, raw_body, signature)

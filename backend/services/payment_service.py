"""
PaymentService - Mercado Pago hybrid flow.

Rules:
- Mercado Pago is the only active gateway for customer checkout.
- PIX is generated directly by the backend so the checkout can show QR Code
  and copia-e-cola without using the Payment Brick.
- Card payments keep using Mercado Pago Payment Brick.
- The frontend never marks an order as paid.
- Payment approval is applied only after webhook processing re-fetches the
  payment from Mercado Pago.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.events import bus, PaymentConfirmed, PaymentCreated, PaymentFailed
from backend.core.exceptions import (
    DomainError,
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
from backend.services.customer_metrics_service import sync_customer_order_metrics
from backend.services.saipos_service import sendOrderToSaipos

settings = get_settings()
MP_API_BASE = "https://api.mercadopago.com"
_logger = logging.getLogger(__name__)


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
    if provider == "mock":
        provider = "mercado_pago"
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


def _mp_request(
    method: str,
    path: str,
    token: str,
    body: dict[str, Any] | None = None,
    *,
    idempotency_key: str | None = None,
    _max_retries: int = 2,
) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if idempotency_key:
        headers["X-Idempotency-Key"] = idempotency_key

    req = Request(f"{MP_API_BASE}{path}", data=data, headers=headers, method=method)
    last_url_error: URLError | None = None
    for attempt in range(_max_retries + 1):
        try:
            with urlopen(req, timeout=30) as response:
                payload = response.read().decode("utf-8")
                return json.loads(payload) if payload else {}
        except HTTPError as exc:
            # HTTP errors from MP (4xx/5xx) are deterministic — do not retry.
            detail = exc.read().decode("utf-8", errors="replace")
            _logger.error("Mercado Pago HTTP error %s %s → %s: %s", method, path, exc.code, detail[:500])
            raise GatewayError("mercado_pago", detail or f"HTTP {exc.code}") from exc
        except URLError as exc:
            last_url_error = exc
            if attempt < _max_retries:
                wait = min(2 ** attempt + random.random(), 8)
                _logger.warning(
                    "Mercado Pago rede inacessível (tentativa %d/%d) %s %s: %s. Aguardando %.1fs...",
                    attempt + 1, _max_retries + 1, method, path, exc.reason, wait,
                )
                time.sleep(wait)
            else:
                _logger.error("Mercado Pago rede inacessível após %d tentativas %s %s: %s", _max_retries + 1, method, path, exc.reason)
    raise GatewayError("mercado_pago", str(last_url_error.reason) if last_url_error else "network error") from last_url_error


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
        return OrderStatus.paid
    if status == PaymentStatus.rejected:
        return OrderStatus.pagamento_recusado
    if status in {PaymentStatus.cancelled, PaymentStatus.expired}:
        return OrderStatus.pagamento_expirado
    return None


def _allowed_order_transition(order: Order, to_status: OrderStatus) -> bool:
    current = order.status.value if hasattr(order.status, "value") else str(order.status)
    return order_sm.can_transition(current, to_status.value)


def _ensure_method_enabled(config: PaymentGatewayConfig, method: PaymentMethod) -> None:
    enabled_by_method = {
        PaymentMethod.pix: config.accept_pix,
        PaymentMethod.credit_card: config.accept_credit_card,
        PaymentMethod.debit_card: config.accept_debit_card,
    }
    if method == PaymentMethod.cash or not enabled_by_method.get(method, False):
        raise DomainError(
            "Forma de pagamento indisponivel. Configure os metodos aceitos em Admin > Pagamentos.",
            code="PaymentMethodDisabled",
        )


def _store_mp_payment_data(payment: Payment, response: dict[str, Any]) -> None:
    transaction_data = ((response.get("point_of_interaction") or {}).get("transaction_data") or {})
    qr_code_text = transaction_data.get("qr_code")
    qr_code_base64 = transaction_data.get("qr_code_base64")
    ticket_url = transaction_data.get("ticket_url")

    if qr_code_text:
        payment.qr_code_text = qr_code_text
    if qr_code_base64:
        qr_code = str(qr_code_base64)
        payment.qr_code = qr_code if qr_code.startswith("data:image") else f"data:image/png;base64,{qr_code}"
    if ticket_url:
        payment.payment_url = ticket_url


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

    def accepted_methods(self) -> dict[str, bool | str]:
        cfg = self._cfg()
        return {
            "gateway": "mercadopago",
            "accept_pix": bool(cfg.accept_pix),
            "accept_credit_card": bool(cfg.accept_credit_card),
            "accept_debit_card": bool(cfg.accept_debit_card),
            "accept_cash": False,
        }

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
        provider = _provider_name(settings.PAYMENT_PROVIDER or settings.PAYMENT_GATEWAY or cfg.gateway)
        if provider != "mercado_pago":
            provider = "mercado_pago"
        method = _payment_method(form_data, payload.payment_method)
        _ensure_method_enabled(cfg, method)

        if order.payment and order.payment.mercado_pago_payment_id:
            if order.payment.status == PaymentStatus.approved:
                raise DomainError(
                    "Este pedido ja foi pago. Acesse o acompanhamento do pedido.",
                    code="PaymentAlreadyApproved",
                )
            if order.payment.status == PaymentStatus.pending:
                same_attempt = (
                    order.payment.provider == "mercado_pago"
                    and order.payment.method == method
                    and abs(order.payment.amount - amount) <= 0.01
                )
                if same_attempt:
                    return PaymentOut.model_validate(order.payment)
                raise DomainError(
                    "Este pedido ja possui um pagamento Mercado Pago em andamento. Aguarde a confirmacao ou crie um novo pedido.",
                    code="PaymentAlreadyInProgress",
                )

        if not order.external_reference:
            order.external_reference = f"order-{order.id}"

        if current_order_status == "pending":
            order_sm.transition(order.id, current_order_status, "aguardando_pagamento")
            order.status = OrderStatus.aguardando_pagamento
            self._db.flush()

        payment = self._pending_payment(order, payload, amount, method, provider)

        body = self._build_mp_payment_body(order, payment, form_data, amount)
        idempotency_key = hashlib.sha256(f"{order.id}:{method.value}:{amount}:{json.dumps(form_data, sort_keys=True, default=str)}".encode()).hexdigest()
        _logger.info("Criando pagamento MP: order_id=%s method=%s amount=%.2f idempotency_key=%s", order.id, method.value, amount, idempotency_key[:16])
        response = _mp_request("POST", "/v1/payments", _mp_token(cfg), body, idempotency_key=idempotency_key)

        mp_id = str(response.get("id", ""))
        _logger.info("Resposta MP: mp_payment_id=%s status=%s order_id=%s", mp_id, response.get("status"), order.id)
        payment.mercado_pago_payment_id = mp_id or payment.mercado_pago_payment_id
        payment.transaction_id = mp_id or payment.transaction_id
        payment.external_reference = response.get("external_reference") or payment.external_reference
        payment.raw_response = json.dumps(response, ensure_ascii=False)
        payment.webhook_data = payment.raw_response
        _store_mp_payment_data(payment, response)
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
        email = payer.get("email") or form_data.get("payer_email") or f"cliente.{order.id[:8].lower()}@delivery.moschettieri.com.br"
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
        previous = payment.status
        now = datetime.now(timezone.utc)
        status_changed = previous != status
        if status_changed:
            if not payment_sm.can_transition(previous.value, status.value):
                return False
            payment_sm.transition(payment.id, previous.value, status.value)
            payment.status = status
            payment.updated_at = now
            if status == PaymentStatus.approved:
                payment.paid_at = payment.paid_at or now
        elif status != PaymentStatus.approved:
            return False
        else:
            payment.updated_at = now
            payment.paid_at = payment.paid_at or now

        order = self._db.query(Order).filter(Order.id == payment.order_id).first()
        target_order_status = _order_status_for_payment(status)
        if order and target_order_status and order.status != target_order_status:
            current_order_status = order.status.value if hasattr(order.status, "value") else str(order.status)
            already_paid_flow = current_order_status in {"paid", "pago", "preparing", "ready_for_pickup", "on_the_way", "delivered"}
            if status == PaymentStatus.approved and already_paid_flow:
                order.paid_at = order.paid_at or now
                order.updated_at = now
            elif _allowed_order_transition(order, target_order_status):
                order_sm.transition(order.id, current_order_status, target_order_status.value)
                order.status = target_order_status
                order.updated_at = now
                if status == PaymentStatus.approved:
                    order.paid_at = order.paid_at or now
            else:
                order.updated_at = now
        elif order and status == PaymentStatus.approved:
            order.paid_at = order.paid_at or now
            order.updated_at = now

        if order:
            self._db.flush()
            sync_customer_order_metrics(self._db, order.customer_id)

        self._db.commit()

        if status == PaymentStatus.approved and status_changed:
            _logger.info(
                "Pagamento aprovado: payment_id=%s order_id=%s amount=%.2f gateway=%s source=%s",
                payment.id, payment.order_id, payment.amount, payment.gateway, source,
            )
            if order and order.session_id:
                try:
                    from backend.schemas.paid_traffic import TrackingEventIn
                    from backend.services.paid_traffic_service import PaidTrafficService

                    PaidTrafficService(self._db).record_event(TrackingEventIn(
                        session_id=order.session_id,
                        campaign_id=order.campaign_id,
                        event_type="order_paid",
                        value=order.total,
                        path=order.landing_page,
                        landing_page=order.landing_page,
                        referrer=order.referrer,
                        utm_source=order.utm_source,
                        utm_medium=order.utm_medium,
                        utm_campaign=order.utm_campaign,
                        utm_content=order.utm_content,
                        utm_term=order.utm_term,
                        metadata={"order_id": order.id, "payment_id": payment.id},
                    ))
                except Exception as exc:
                    _logger.warning("Falha ao registrar evento de tráfego pago: order_id=%s error=%s", payment.order_id, exc)
            try:
                sendOrderToSaipos(payment.order_id)
            except Exception as exc:
                _logger.error("Falha ao enviar pedido ao SaiPOS: order_id=%s error=%s", payment.order_id, exc)
            try:
                bus.publish(PaymentConfirmed(payment_id=payment.id, order_id=payment.order_id, amount=payment.amount, gateway=payment.gateway, transaction_id=payment.transaction_id or ""))
            except Exception as exc:
                _logger.warning("Falha ao publicar evento PaymentConfirmed: payment_id=%s error=%s", payment.id, exc)
        elif status in {PaymentStatus.rejected, PaymentStatus.cancelled, PaymentStatus.expired}:
            _logger.info(
                "Pagamento %s: payment_id=%s order_id=%s source=%s",
                status.value, payment.id, payment.order_id, source,
            )
            try:
                bus.publish(PaymentFailed(payment_id=payment.id, order_id=payment.order_id, reason=f"{source}:{status.value}"))
            except Exception as exc:
                _logger.warning("Falha ao publicar evento PaymentFailed: payment_id=%s error=%s", payment.id, exc)
        return True

    def _sync_pending_mercado_pago_payment(self, payment: Payment, *, source: str) -> bool:
        if not payment.mercado_pago_payment_id:
            return False
        if payment.provider != "mercado_pago" and payment.gateway != "mercadopago":
            return False
        if payment.status not in {PaymentStatus.pending, PaymentStatus.approved}:
            return False
        if payment.status == PaymentStatus.approved:
            order = self._db.query(Order).filter(Order.id == payment.order_id).first()
            current_order_status = order.status.value if order and hasattr(order.status, "value") else str(order.status) if order else ""
            if current_order_status in {"paid", "pago", "preparing", "ready_for_pickup", "on_the_way", "delivered"}:
                return False

        try:
            response = _mp_request("GET", f"/v1/payments/{payment.mercado_pago_payment_id}", _mp_token(self._cfg()))
        except DomainError as exc:
            _logger.warning(
                "Nao foi possivel sincronizar pagamento Mercado Pago: payment_id=%s mp_payment_id=%s error=%s",
                payment.id, payment.mercado_pago_payment_id, exc,
            )
            return False
        except Exception as exc:
            _logger.warning(
                "Falha inesperada ao sincronizar pagamento Mercado Pago: payment_id=%s mp_payment_id=%s error=%s",
                payment.id, payment.mercado_pago_payment_id, exc,
            )
            return False

        mp_payment_id = str(response.get("id") or payment.mercado_pago_payment_id)
        payment.mercado_pago_payment_id = mp_payment_id
        payment.transaction_id = mp_payment_id
        payment.external_reference = response.get("external_reference") or payment.external_reference
        payment.raw_response = json.dumps(response, ensure_ascii=False)
        _store_mp_payment_data(payment, response)

        new_status = _mp_status_to_payment(response.get("status", ""), response.get("status_detail"))
        changed = self._apply_status(payment, new_status, source=source)
        if not changed:
            payment.updated_at = datetime.now(timezone.utc)
            self._db.commit()
        return changed

    def process_webhook(
        self,
        payload: WebhookPayload,
        raw_body: bytes,
        signature: str | None,
        request_id: str | None = None,
        query_params: dict[str, str] | None = None,
    ) -> dict:
        cfg = self._cfg()
        body = payload.model_dump()
        query_params = query_params or {}
        if not self._verify_mercado_pago_signature(body, signature, request_id, cfg, query_params):
            raise WebhookSignatureInvalid()

        event_type = payload.type or query_params.get("type") or "payment"
        action = payload.action or ""
        if event_type != "payment" and "payment" not in action:
            event = PaymentEvent(
                id=str(uuid.uuid4()),
                provider="mercado_pago",
                event_type=action or event_type,
                mercado_pago_payment_id=None,
                raw_payload=raw_body.decode("utf-8", errors="replace"),
            )
            event.processed_at = datetime.now(timezone.utc)
            self._db.add(event)
            self._db.commit()
            return {"status": "ignored", "reason": f"unsupported_topic:{event_type}"}

        mp_payment_id = (
            payload.transaction_id
            or query_params.get("data.id")
            or (str(payload.data.get("id")) if payload.data else "")
        )
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
            _logger.warning("Webhook MP: pagamento não encontrado no banco — mp_payment_id=%s external_reference=%s", mp_payment_id, external_reference)
            event.processed_at = datetime.now(timezone.utc)
            self._db.commit()
            return {"status": "ignored", "reason": f"payment '{mp_payment_id}' not found"}

        # Validate that the amount from MP matches what we have stored.
        mp_amount = response.get("transaction_amount")
        if mp_amount is not None and abs(float(mp_amount) - payment.amount) > 0.05:
            _logger.error(
                "ALERTA: Discrepância de valor no webhook — payment_id=%s payment.amount=%.2f mp_amount=%.2f mp_payment_id=%s",
                payment.id, payment.amount, mp_amount, mp_payment_id,
            )

        payment.mercado_pago_payment_id = mp_payment_id
        payment.transaction_id = mp_payment_id
        payment.external_reference = external_reference or payment.external_reference
        payment.raw_response = json.dumps(response, ensure_ascii=False)
        payment.webhook_data = event.raw_payload
        _store_mp_payment_data(payment, response)

        new_status = _mp_status_to_payment(response.get("status", ""), response.get("status_detail"))
        changed = self._apply_status(payment, new_status, source="webhook")
        event.processed_at = datetime.now(timezone.utc)
        self._db.commit()
        return {"status": "ok", "payment_status": new_status.value, "changed": changed}

    def _verify_mercado_pago_signature(
        self,
        payload: dict[str, Any],
        signature: str | None,
        request_id: str | None,
        config: PaymentGatewayConfig,
        query_params: dict[str, str] | None = None,
    ) -> bool:
        secret = settings.MERCADO_PAGO_WEBHOOK_SECRET or config.mp_webhook_secret
        if not secret:
            if settings.DEBUG:
                _logger.warning(
                    "MERCADO_PAGO_WEBHOOK_SECRET não configurado — aceitando webhook sem validação de assinatura (somente em modo DEBUG)"
                )
                return True
            _logger.error(
                "MERCADO_PAGO_WEBHOOK_SECRET não configurado em modo produção — webhook rejeitado por segurança. "
                "Configure a variável de ambiente MERCADO_PAGO_WEBHOOK_SECRET."
            )
            return False
        if not signature:
            return False
        try:
            parts = {
                key.strip(): value.strip()
                for part in signature.split(",")
                if "=" in part
                for key, value in [part.split("=", 1)]
            }
            ts = parts.get("ts", "")
            v1 = parts.get("v1", "")
            if not ts or not v1 or not request_id:
                return False

            query_params = query_params or {}
            raw_data_ids = [
                query_params.get("data.id"),
                str((payload.get("data") or {}).get("id", "")),
            ]
            data_id_candidates: list[str] = []
            for raw_data_id in raw_data_ids:
                if not raw_data_id:
                    continue
                data_id = str(raw_data_id)
                data_id_candidates.extend([data_id, data_id.lower()])

            for data_id in dict.fromkeys(data_id_candidates):
                manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
                expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
                if hmac.compare_digest(expected, v1):
                    return True
            if not data_id_candidates:
                manifest = f"request-id:{request_id};ts:{ts};"
                expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
                if hmac.compare_digest(expected, v1):
                    return True
            return False
        except Exception:
            return False

    def confirm_cash(self, order_id: str) -> PaymentOut:
        if not self._cfg().accept_cash:
            raise DomainError("Pagamento em dinheiro esta desativado no painel de pagamentos.", code="PaymentMethodDisabled")
        order = self._get_order(order_id)
        if order.payment and order.payment.method != PaymentMethod.cash:
            raise DomainError("Este pedido ja possui pagamento Mercado Pago vinculado.", code="PaymentMethodMismatch")
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
        payment = self._get_payment_by_order(order_id)
        self._sync_pending_mercado_pago_payment(payment, source="status_poll")
        self._db.refresh(payment)
        return PaymentOut.model_validate(payment)

    def payment_status(self, order_id: str) -> dict:
        order = self._get_order(order_id)
        payment = order.payment
        if payment:
            self._sync_pending_mercado_pago_payment(payment, source="status_poll")
            self._db.refresh(order)
            payment = order.payment
        # Checkout is locked when a payment was submitted to MP and is still active (pending or approved).
        # Rejected/cancelled/expired payments allow a retry, so they don't lock.
        blocking_statuses = {PaymentStatus.pending, PaymentStatus.approved}
        checkout_locked = bool(
            payment
            and payment.mercado_pago_payment_id
            and payment.status in blocking_statuses
        )
        return {
            "order_id": order.id,
            "pedido_status": order.status.value,
            "payment_status": payment.status.value if payment else "pending",
            "mercado_pago_payment_id": payment.mercado_pago_payment_id if payment else None,
            "external_reference": order.external_reference,
            "qr_code": payment.qr_code if payment else None,
            "qr_code_text": payment.qr_code_text if payment else None,
            "payment_url": payment.payment_url if payment else None,
            "checkout_locked": checkout_locked,
            "payment_method": payment.method.value if payment else None,
        }


def create_payment(payload: PaymentCreate, db: Session) -> PaymentOut:
    return PaymentService(db).create(payload)


def process_webhook(
    payload: WebhookPayload,
    raw_body: bytes,
    signature: str | None,
    db: Session,
    request_id: str | None = None,
    query_params: dict[str, str] | None = None,
) -> dict:
    return PaymentService(db).process_webhook(payload, raw_body, signature, request_id, query_params)

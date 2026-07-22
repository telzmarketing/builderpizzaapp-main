"""
PaymentService - multi-gateway payment flow.

Rules:
- The payment provider is resolved server-side from PaymentGatewayConfig.
- PIX is generated directly by the backend so the checkout can show QR Code
  and copia-e-cola without using a card SDK.
- Card payments use Mercado Pago token flow or the dedicated ASAAS card route.
- The frontend never marks an order as paid.
- Payment approval is applied only after trusted backend/webhook processing.
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

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.events import bus, PaymentConfirmed, PaymentCreated, PaymentFailed, PaymentReversed
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
from backend.schemas.payment import (
    AsaasCreditCardPaymentCreate,
    PaymentCreate,
    PaymentOut,
    PayOnDeliverySwitch,
    WebhookPayload,
)
from backend.services.asaas_client import sanitize_asaas_payload
from backend.services.asaas_gateway import AsaasGateway
from backend.services.customer_metrics_service import sync_customer_order_metrics
from backend.services.payment_gateway_resolver import (
    ASAAS_CARD_SAFETY_REASON,
    PROVIDER_ASAAS,
    PROVIDER_MERCADO_PAGO,
    PaymentGatewayResolver,
    normalize_payment_provider,
)

settings = get_settings()
MP_API_BASE = "https://api.mercadopago.com"
_logger = logging.getLogger(__name__)


def _provider_name(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw in {"mercado_pago", "mercadopago", "mp"}:
        return "mercado_pago"
    return raw or "mock"


def _load_config(db: Session, tenant_id: str | None = None) -> PaymentGatewayConfig:
    if tenant_id:
        from backend.services.tenant_credential_service import TenantCredentialService
        return TenantCredentialService(db).payment_gateway(tenant_id)
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
    config.asaas_api_key = settings.ASAAS_API_KEY or config.asaas_api_key
    config.asaas_webhook_token = settings.ASAAS_WEBHOOK_TOKEN or config.asaas_webhook_token

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


def _payer_document(form_data: dict[str, Any]) -> str | None:
    payer = form_data.get("payer") or {}
    identification = payer.get("identification") if isinstance(payer, dict) else {}
    candidates = [
        identification.get("number") if isinstance(identification, dict) else None,
        payer.get("cpf_cnpj") if isinstance(payer, dict) else None,
        payer.get("cpfCnpj") if isinstance(payer, dict) else None,
        form_data.get("cpf_cnpj"),
        form_data.get("cpfCnpj"),
        form_data.get("document"),
        form_data.get("identification_number"),
    ]
    for candidate in candidates:
        digits = "".join(ch for ch in str(candidate or "") if ch.isdigit())
        if digits:
            return digits
    return None


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


def _asaas_status_to_payment(asaas_status: str | None, event_type: str | None = None) -> PaymentStatus:
    status = (asaas_status or "").strip().upper()
    event = (event_type or "").strip().upper()
    if status in {"RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"} or event in {"PAYMENT_RECEIVED", "PAYMENT_CONFIRMED"}:
        return PaymentStatus.approved
    if status == "REFUNDED" or event in {"PAYMENT_REFUNDED", "PAYMENT_PARTIALLY_REFUNDED"}:
        return PaymentStatus.refunded
    if status in {"DELETED", "CANCELLED", "CANCELED"} or event in {"PAYMENT_DELETED", "PAYMENT_BANK_SLIP_CANCELLED"}:
        return PaymentStatus.cancelled
    if status == "OVERDUE" or event == "PAYMENT_OVERDUE":
        return PaymentStatus.expired
    if event in {"PAYMENT_CREDIT_CARD_CAPTURE_REFUSED", "PAYMENT_REPROVED_BY_RISK_ANALYSIS"}:
        return PaymentStatus.rejected
    return PaymentStatus.pending


def _order_status_for_payment(status: PaymentStatus) -> OrderStatus | None:
    if status == PaymentStatus.approved:
        return OrderStatus.paid
    if status == PaymentStatus.refunded:
        return OrderStatus.refunded
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
        PaymentMethod.cash: config.accept_cash,
    }
    if not enabled_by_method.get(method, False):
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
        payment.pix_payload = qr_code_text
    if qr_code_base64:
        qr_code = str(qr_code_base64)
        payment.qr_code = qr_code if qr_code.startswith("data:image") else f"data:image/png;base64,{qr_code}"
        payment.pix_qr_code = payment.qr_code
    if ticket_url:
        payment.payment_url = ticket_url


class PaymentService:
    def __init__(self, db: Session, tenant_id: str | None = None):
        self._db = db
        self._tenant_id = tenant_id
        self._config: PaymentGatewayConfig | None = None

    def _cfg(self) -> PaymentGatewayConfig:
        if self._config is None:
            self._config = _load_config(self._db, self._tenant_id)
        return self._config

    def _resolver(self) -> PaymentGatewayResolver:
        return PaymentGatewayResolver(self._cfg())

    def public_key(self) -> dict[str, str]:
        cfg = self._cfg()
        return {"public_key": settings.MERCADO_PAGO_PUBLIC_KEY or cfg.mp_public_key or ""}

    def accepted_methods(self) -> dict[str, Any]:
        cfg = self._cfg()
        public_methods = self._resolver().public_config()["methods"]
        return {
            "gateway": "mercadopago",
            "accept_pix": bool(public_methods["pix"]["enabled"]),
            "accept_credit_card": bool(public_methods["credit_card"]["enabled"]),
            "accept_debit_card": bool(public_methods["debit_card"]["enabled"]),
            "accept_cash": bool(cfg.accept_cash),
            "pix_provider": cfg.pix_provider or PROVIDER_MERCADO_PAGO,
            "credit_card_provider": cfg.credit_card_provider or PROVIDER_MERCADO_PAGO,
        }

    def public_config(self) -> dict[str, Any]:
        return self._resolver().public_config()

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
                currency="BRL",
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
            payment.currency = payment.currency or "BRL"
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

        method = _payment_method(form_data, payload.payment_method)
        cfg = self._cfg()
        _ensure_method_enabled(cfg, method)
        if method == PaymentMethod.cash:
            raise DomainError(
                "Pagamento na entrega deve ser criado junto com o pedido.",
                code="PaymentMethodDisabled",
            )
        resolved_gateway = self._resolver().resolve(method)
        if not resolved_gateway.enabled:
            raise DomainError(
                resolved_gateway.reason or "Forma de pagamento indisponivel.",
                code="PaymentMethodDisabled",
            )
        provider = resolved_gateway.provider
        if provider == PROVIDER_ASAAS:
            if method != PaymentMethod.pix:
                raise DomainError(
                    ASAAS_CARD_SAFETY_REASON,
                    code="PaymentGatewayNotImplemented",
                )
            return self._create_asaas_pix_payment(
                order,
                payload,
                form_data,
                amount,
                current_order_status,
            )
        if provider != PROVIDER_MERCADO_PAGO:
            raise DomainError(
                "Provedor de pagamento indisponivel para checkout.",
                code="PaymentGatewayNotImplemented",
            )

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
        payment.provider_payment_id = mp_id or payment.provider_payment_id
        payment.provider_status = response.get("status") or payment.provider_status
        payment.transaction_id = mp_id or payment.transaction_id
        payment.external_reference = response.get("external_reference") or payment.external_reference
        payment.currency = "BRL"
        if form_data.get("installments"):
            payment.installments = int(form_data["installments"])
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

    def _create_asaas_pix_payment(
        self,
        order: Order,
        payload: PaymentCreate,
        form_data: dict[str, Any],
        amount: float,
        current_order_status: str,
    ) -> PaymentOut:
        if order.payment:
            if order.payment.status == PaymentStatus.approved:
                raise DomainError(
                    "Este pedido ja foi pago. Acesse o acompanhamento do pedido.",
                    code="PaymentAlreadyApproved",
                )
            if order.payment.status == PaymentStatus.pending:
                same_asaas_attempt = (
                    order.payment.provider == PROVIDER_ASAAS
                    and order.payment.method == PaymentMethod.pix
                    and abs(order.payment.amount - amount) <= 0.01
                )
                if same_asaas_attempt and order.payment.provider_payment_id and (
                    order.payment.qr_code_text or order.payment.pix_payload
                ):
                    return PaymentOut.model_validate(order.payment)
                if order.payment.mercado_pago_payment_id:
                    raise DomainError(
                        "Este pedido ja possui um pagamento Mercado Pago em andamento. Aguarde a confirmacao ou crie um novo pedido.",
                        code="PaymentAlreadyInProgress",
                    )

        cpf_cnpj = _payer_document(form_data)
        if not cpf_cnpj:
            raise DomainError(
                "CPF/CNPJ do cliente e obrigatorio para gerar Pix ASAAS.",
                code="AsaasCustomerDocumentRequired",
            )

        if not order.external_reference:
            order.external_reference = f"order-{order.id}"

        if current_order_status == "pending":
            order_sm.transition(order.id, current_order_status, "aguardando_pagamento")
            order.status = OrderStatus.aguardando_pagamento
            self._db.flush()

        payment = self._pending_payment(order, payload, amount, PaymentMethod.pix, PROVIDER_ASAAS)
        payment.mercado_pago_payment_id = None
        payment.pay_on_delivery = False
        payment.method = PaymentMethod.pix
        payment.status = PaymentStatus.pending

        AsaasGateway(self._db).create_pix_payment(
            order=order,
            payment=payment,
            amount=amount,
            cpf_cnpj=cpf_cnpj,
        )
        self._db.commit()
        self._db.refresh(payment)
        bus.publish(PaymentCreated(payment_id=payment.id, order_id=payment.order_id, method=payment.method.value, amount=payment.amount, gateway=payment.gateway))
        return PaymentOut.model_validate(payment)

    def create_asaas_credit_card(self, payload: AsaasCreditCardPaymentCreate, *, client_ip: str | None) -> PaymentOut:
        order = self._get_order(payload.order_id)
        current_order_status = order.status.value if hasattr(order.status, "value") else str(order.status)
        if current_order_status not in {"pending", "waiting_payment", "aguardando_pagamento", "pagamento_recusado", "pagamento_expirado"}:
            raise PaymentOrderNotEligible(order.id, current_order_status)

        if not client_ip:
            raise DomainError(
                "Nao foi possivel identificar o IP do comprador para processar cartao ASAAS.",
                code="BuyerIpRequired",
            )

        amount = float(payload.amount or order.total)
        if abs(order.total - amount) > 0.01:
            raise PaymentAmountMismatch(order.total, amount)

        cfg = self._cfg()
        _ensure_method_enabled(cfg, PaymentMethod.credit_card)
        resolved_gateway = self._resolver().resolve(PaymentMethod.credit_card)
        if not resolved_gateway.enabled:
            raise DomainError(
                resolved_gateway.reason or "Cartao indisponivel.",
                code="PaymentMethodDisabled",
            )
        if resolved_gateway.provider != PROVIDER_ASAAS:
            raise DomainError(
                "Cartao ASAAS nao esta selecionado no painel de pagamentos.",
                code="PaymentGatewayNotSelected",
            )

        if order.payment:
            if order.payment.status == PaymentStatus.approved:
                raise DomainError(
                    "Este pedido ja foi pago. Acesse o acompanhamento do pedido.",
                    code="PaymentAlreadyApproved",
                )
            if order.payment.status == PaymentStatus.pending:
                same_asaas_card_attempt = (
                    order.payment.provider == PROVIDER_ASAAS
                    and order.payment.method == PaymentMethod.credit_card
                    and abs(order.payment.amount - amount) <= 0.01
                )
                if same_asaas_card_attempt and order.payment.provider_payment_id:
                    return PaymentOut.model_validate(order.payment)
                if order.payment.provider_payment_id or order.payment.mercado_pago_payment_id or order.payment.qr_code_text:
                    raise DomainError(
                        "Este pedido ja possui um pagamento em andamento. Aguarde a confirmacao ou crie um novo pedido.",
                        code="PaymentAlreadyInProgress",
                    )

        if not order.external_reference:
            order.external_reference = f"order-{order.id}"

        if current_order_status == "pending":
            order_sm.transition(order.id, current_order_status, "aguardando_pagamento")
            order.status = OrderStatus.aguardando_pagamento
            self._db.flush()

        payment = self._pending_payment(order, PaymentCreate(order_id=order.id, amount=amount), amount, PaymentMethod.credit_card, PROVIDER_ASAAS)
        payment.mercado_pago_payment_id = None
        payment.pay_on_delivery = False
        payment.method = PaymentMethod.credit_card
        payment.status = PaymentStatus.pending
        payment.provider_error_code = None
        payment.provider_error_message = None

        AsaasGateway(self._db).create_credit_card_payment(
            order=order,
            payment=payment,
            amount=amount,
            card_payload=payload,
            remote_ip=client_ip,
        )

        response_status = _asaas_status_to_payment(payment.provider_status, None)
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

    def switch_to_pay_on_delivery(self, order_id: str, payload: PayOnDeliverySwitch) -> PaymentOut:
        cfg = self._cfg()
        if not cfg.accept_cash:
            raise DomainError("Pagamento na entrega esta indisponivel no momento.", code="PaymentMethodDisabled")
        order = self._get_order(order_id)
        current_order_status = order.status.value if hasattr(order.status, "value") else str(order.status)
        if current_order_status not in {"pending", "waiting_payment", "aguardando_pagamento", "pagamento_recusado", "pagamento_expirado"}:
            raise PaymentOrderNotEligible(order.id, current_order_status)

        delivery_payment_method = (payload.delivery_payment_method or "").strip().lower()
        if delivery_payment_method not in {"cash", "card"}:
            raise DomainError("Escolha se o pagamento na entrega sera em cartao ou dinheiro.", code="InvalidDeliveryPaymentMethod")
        cash_needs_change = bool(payload.cash_needs_change) if delivery_payment_method == "cash" else None
        cash_change_for = float(payload.cash_change_for or 0) if cash_needs_change else None
        if cash_change_for is not None and cash_change_for <= float(order.total):
            raise DomainError("O valor para troco deve ser maior que o total do pedido.", code="InvalidCashChange")

        is_new_payment = order.payment is None
        payment = order.payment or Payment(id=str(uuid.uuid4()), order_id=order.id)
        previous_payment_status = payment.status if not is_new_payment else PaymentStatus.pending
        if previous_payment_status == PaymentStatus.approved:
            raise DomainError("Este pedido ja foi pago. Acesse o acompanhamento do pedido.", code="PaymentAlreadyApproved")
        if not is_new_payment and previous_payment_status != PaymentStatus.pending:
            payment_sm.transition(payment.id, previous_payment_status.value, PaymentStatus.pending.value)

        payment.method = PaymentMethod.cash
        payment.status = PaymentStatus.pending
        payment.amount = float(order.total)
        payment.gateway = "on_delivery"
        payment.provider = "on_delivery"
        payment.mercado_pago_payment_id = None
        payment.payment_url = None
        payment.qr_code = None
        payment.qr_code_text = None
        payment.client_secret = None
        payment.pay_on_delivery = True
        payment.delivery_payment_method = delivery_payment_method
        payment.cash_needs_change = cash_needs_change
        payment.cash_change_for = cash_change_for
        payment.transaction_id = payment.transaction_id or f"DELIVERY-{uuid.uuid4().hex[:8].upper()}"
        payment.external_reference = order.external_reference or order.id
        payment.currency = payment.currency or "BRL"
        payment.updated_at = datetime.now(timezone.utc)
        self._db.add(payment)

        if current_order_status in {"pagamento_recusado", "pagamento_expirado"}:
            order_sm.transition(order.id, current_order_status, "aguardando_pagamento")
            current_order_status = "aguardando_pagamento"
        if current_order_status != OrderStatus.paid.value:
            order_sm.transition(order.id, current_order_status, OrderStatus.paid.value)
            order.status = OrderStatus.paid
        order.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        from backend.services.inventory_service import InventoryService

        InventoryService(self._db).consume_order_sale(order.id)
        sync_customer_order_metrics(self._db, order.customer_id)
        self._db.commit()
        self._db.refresh(payment)
        return PaymentOut.model_validate(payment)

    def _apply_status(self, payment: Payment, status: PaymentStatus, *, source: str) -> bool:
        previous = payment.status
        requested_status = status
        if status == PaymentStatus.cancelled and previous in {PaymentStatus.approved, PaymentStatus.paid}:
            status = PaymentStatus.refunded
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
            if status == PaymentStatus.cancelled:
                payment.cancelled_at = payment.cancelled_at or now
            if status == PaymentStatus.refunded:
                payment.refunded_at = payment.refunded_at or now
        elif status != PaymentStatus.approved:
            return False
        else:
            payment.updated_at = now
            payment.paid_at = payment.paid_at or now

        order = self._db.query(Order).filter(Order.id == payment.order_id, *self._tenant_order_filter()).first()
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
                # Trigger: PIX expirado → auto-cancelar com rastreamento
                if status in {PaymentStatus.expired, PaymentStatus.cancelled} and not order.cancelled_by:
                    if _allowed_order_transition(order, OrderStatus.cancelled):
                        order_sm.transition(order.id, target_order_status.value, "cancelled")
                        order.status = OrderStatus.cancelled
                        is_admin_cancel = source.startswith("admin_cancel")
                        order.cancelled_by = "admin" if is_admin_cancel else "system"
                        order.cancellation_reason = (
                            "Cobranca cancelada pelo administrador"
                            if is_admin_cancel
                            else "PIX nao pago - expirado pelo gateway de pagamento"
                        )
                        order.cancelled_at = now
            else:
                order.updated_at = now
        elif order and status == PaymentStatus.approved:
            order.paid_at = order.paid_at or now
            order.updated_at = now

        if order:
            self._db.flush()
            inventory_service = None
            if status == PaymentStatus.approved:
                from backend.services.inventory_service import InventoryService

                inventory_service = InventoryService(self._db)
                inventory_service.consume_order_sale(order.id)
            current_order_status = order.status.value if hasattr(order.status, "value") else str(order.status)
            if current_order_status in {"cancelled", "refunded"}:
                if inventory_service is None:
                    from backend.services.inventory_service import InventoryService

                    inventory_service = InventoryService(self._db)
                inventory_service.reverse_order_sale(order.id)
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
        elif status == PaymentStatus.refunded and status_changed:
            _logger.info(
                "Pagamento estornado: payment_id=%s order_id=%s source=%s",
                payment.id, payment.order_id, source,
            )
            try:
                bus.publish(PaymentReversed(
                    payment_id=payment.id,
                    order_id=payment.order_id,
                    amount=payment.amount,
                    gateway=payment.gateway,
                    transaction_id=payment.transaction_id or "",
                    reason=f"{source}:{requested_status.value}",
                ))
            except Exception as exc:
                _logger.warning("Falha ao publicar evento PaymentReversed: payment_id=%s error=%s", payment.id, exc)
        return True

    def _sync_pending_mercado_pago_payment(self, payment: Payment, *, source: str) -> bool:
        if not payment.mercado_pago_payment_id:
            return False
        if payment.provider != "mercado_pago" and payment.gateway != "mercadopago":
            return False
        if payment.status not in {PaymentStatus.pending, PaymentStatus.approved}:
            return False
        if payment.status == PaymentStatus.approved:
            order = self._db.query(Order).filter(Order.id == payment.order_id, *self._tenant_order_filter()).first()
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
        payment.provider_payment_id = mp_payment_id
        payment.provider_status = response.get("status") or payment.provider_status
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

    def _payment_provider(self, payment: Payment) -> str:
        provider = normalize_payment_provider(payment.provider or payment.gateway)
        if provider == "mercadopago":
            return PROVIDER_MERCADO_PAGO
        return provider

    def _sync_provider_payment(self, payment: Payment, *, source: str) -> bool:
        provider = self._payment_provider(payment)
        if provider == PROVIDER_MERCADO_PAGO:
            return self._sync_pending_mercado_pago_payment(payment, source=source)
        if provider == PROVIDER_ASAAS:
            return self._sync_asaas_payment(payment, source=source)
        return False

    def _sync_asaas_payment(self, payment: Payment, *, source: str) -> bool:
        provider_payment_id = payment.provider_payment_id or payment.transaction_id
        if not provider_payment_id:
            return False
        if payment.status in {PaymentStatus.cancelled, PaymentStatus.expired, PaymentStatus.refunded}:
            return False

        try:
            response = AsaasGateway(self._db).retrieve_payment(str(provider_payment_id))
        except DomainError as exc:
            _logger.warning(
                "Nao foi possivel sincronizar pagamento ASAAS: payment_id=%s asaas_payment_id=%s error=%s",
                payment.id,
                provider_payment_id,
                exc,
            )
            return False
        except Exception as exc:
            _logger.warning(
                "Falha inesperada ao sincronizar pagamento ASAAS: payment_id=%s asaas_payment_id=%s error=%s",
                payment.id,
                provider_payment_id,
                exc,
            )
            return False

        asaas_payment_id = str(response.get("id") or provider_payment_id)
        payment.provider = PROVIDER_ASAAS
        payment.gateway = PROVIDER_ASAAS
        payment.provider_payment_id = asaas_payment_id
        payment.provider_status = response.get("status") or payment.provider_status
        payment.transaction_id = asaas_payment_id
        payment.external_reference = response.get("externalReference") or payment.external_reference
        payment.currency = "BRL"
        payment.raw_response = json.dumps(sanitize_asaas_payload(response), ensure_ascii=False)

        new_status = _asaas_status_to_payment(response.get("status"), None)
        changed = self._apply_status(payment, new_status, source=source)
        if not changed:
            payment.updated_at = datetime.now(timezone.utc)
            self._db.commit()
        return changed

    def _find_payment_event(self, provider: str, provider_event_id: str | None, payload_hash: str | None) -> PaymentEvent | None:
        tenant_filter = (PaymentEvent.tenant_id == self._tenant_id,) if self._tenant_id else ()
        if provider_event_id:
            event = (
                self._db.query(PaymentEvent)
                .filter(PaymentEvent.provider == provider, PaymentEvent.provider_event_id == provider_event_id, *tenant_filter)
                .first()
            )
            if event:
                return event
        if payload_hash:
            return (
                self._db.query(PaymentEvent)
                .filter(
                    PaymentEvent.provider == provider,
                    PaymentEvent.provider_event_id.is_(None),
                    PaymentEvent.payload_hash == payload_hash,
                    *tenant_filter,
                )
                .first()
            )
        return None

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
        normalized_payload = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        payload_hash = hashlib.sha256(normalized_payload.encode("utf-8")).hexdigest()
        provider_event_id = payload.id
        existing_event = self._find_payment_event("mercado_pago", provider_event_id, payload_hash)
        if existing_event:
            return {"status": "duplicate", "event_id": existing_event.id, "changed": False}

        if event_type != "payment" and "payment" not in action:
            event = PaymentEvent(
                id=str(uuid.uuid4()),
                provider="mercado_pago",
                event_type=action or event_type,
                provider_event_id=provider_event_id,
                payload_hash=payload_hash,
                processing_status="ignored",
                mercado_pago_payment_id=None,
                raw_payload=raw_body.decode("utf-8", errors="replace"),
                tenant_id=self._tenant_id,
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
            provider_event_id=provider_event_id,
            provider_payment_id=mp_payment_id or None,
            payload_hash=payload_hash,
            processing_status="received",
            mercado_pago_payment_id=mp_payment_id or None,
            raw_payload=raw_body.decode("utf-8", errors="replace"),
            tenant_id=self._tenant_id,
        )
        self._db.add(event)
        self._db.flush()

        if not mp_payment_id:
            event.processed_at = datetime.now(timezone.utc)
            event.processing_status = "ignored"
            self._db.commit()
            return {"status": "ignored", "reason": "no mercado_pago_payment_id"}

        mp_token = cfg.mp_access_token if self._tenant_id else _mp_token(cfg)
        if not mp_token:
            raise GatewayNotConfigured("mercado_pago", "tenant mp_access_token")
        response = _mp_request("GET", f"/v1/payments/{mp_payment_id}", mp_token)
        external_reference = response.get("external_reference")
        event.external_reference = external_reference

        payment = (
            self._db.query(Payment).filter(Payment.mercado_pago_payment_id == mp_payment_id, *self._tenant_payment_filter()).first()
            or self._db.query(Payment).filter(Payment.transaction_id == mp_payment_id, *self._tenant_payment_filter()).first()
        )
        if not payment and external_reference:
            order = self._db.query(Order).filter(Order.external_reference == external_reference, *self._tenant_order_filter()).first()
            if order:
                payment = order.payment
        if not payment:
            _logger.warning("Webhook MP: pagamento não encontrado no banco — mp_payment_id=%s external_reference=%s", mp_payment_id, external_reference)
            event.processed_at = datetime.now(timezone.utc)
            event.processing_status = "ignored"
            self._db.commit()
            return {"status": "ignored", "reason": f"payment '{mp_payment_id}' not found"}
        if payment.provider != "mercado_pago" and payment.gateway != "mercadopago":
            event.processed_at = datetime.now(timezone.utc)
            event.processing_status = "ignored"
            self._db.commit()
            return {"status": "ignored", "reason": "stale_webhook_payment_switched_provider"}
        if payment.mercado_pago_payment_id and str(payment.mercado_pago_payment_id) != str(mp_payment_id):
            event.processed_at = datetime.now(timezone.utc)
            event.processing_status = "ignored"
            self._db.commit()
            return {"status": "ignored", "reason": "stale_webhook_payment_replaced"}

        # Validate that the amount from MP matches what we have stored.
        mp_amount = response.get("transaction_amount")
        if mp_amount is not None and abs(float(mp_amount) - payment.amount) > 0.05:
            _logger.error(
                "ALERTA: Discrepância de valor no webhook — payment_id=%s payment.amount=%.2f mp_amount=%.2f mp_payment_id=%s",
                payment.id, payment.amount, mp_amount, mp_payment_id,
            )

        payment.mercado_pago_payment_id = mp_payment_id
        payment.provider_payment_id = mp_payment_id
        payment.provider_status = response.get("status") or payment.provider_status
        payment.transaction_id = mp_payment_id
        payment.external_reference = external_reference or payment.external_reference
        payment.raw_response = json.dumps(response, ensure_ascii=False)
        payment.webhook_data = event.raw_payload
        _store_mp_payment_data(payment, response)

        new_status = _mp_status_to_payment(response.get("status", ""), response.get("status_detail"))
        changed = self._apply_status(payment, new_status, source="webhook")
        event.processed_at = datetime.now(timezone.utc)
        event.processing_status = "processed"
        self._db.commit()
        return {"status": "ok", "payment_status": new_status.value, "changed": changed}

    def process_asaas_webhook(self, payload: dict[str, Any], raw_body: bytes, access_token: str | None) -> dict:
        cfg = self._cfg()
        if not self._verify_asaas_access_token(access_token, cfg):
            raise WebhookSignatureInvalid()

        event_type = str(payload.get("event") or "").strip()
        payment_payload = payload.get("payment") if isinstance(payload.get("payment"), dict) else {}
        provider_event_id = str(payload.get("id") or "").strip() or None
        normalized_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        payload_hash = hashlib.sha256(normalized_payload.encode("utf-8")).hexdigest()

        existing_event = self._find_payment_event(PROVIDER_ASAAS, provider_event_id, payload_hash)
        if existing_event:
            return {"status": "duplicate", "event_id": existing_event.id, "changed": False}

        provider_payment_id = str(
            payment_payload.get("id")
            or payload.get("paymentId")
            or payload.get("payment_id")
            or ""
        ).strip()
        event = PaymentEvent(
            id=str(uuid.uuid4()),
            provider=PROVIDER_ASAAS,
            event_type=event_type or "unknown",
            provider_event_id=provider_event_id,
            provider_payment_id=provider_payment_id or None,
            payload_hash=payload_hash,
            processing_status="received",
            raw_payload=json.dumps(sanitize_asaas_payload(payload), ensure_ascii=False),
            tenant_id=self._tenant_id,
        )
        self._db.add(event)
        try:
            self._db.flush()
        except IntegrityError:
            self._db.rollback()
            existing_event = self._find_payment_event(PROVIDER_ASAAS, provider_event_id, payload_hash)
            if existing_event:
                return {"status": "duplicate", "event_id": existing_event.id, "changed": False}
            raise

        if not event_type.startswith("PAYMENT_"):
            event.processed_at = datetime.now(timezone.utc)
            event.processing_status = "ignored"
            self._db.commit()
            return {"status": "ignored", "reason": f"unsupported_event:{event_type or 'unknown'}"}

        if not provider_payment_id:
            event.processed_at = datetime.now(timezone.utc)
            event.processing_status = "ignored"
            self._db.commit()
            return {"status": "ignored", "reason": "no asaas_payment_id"}

        asaas_client = None
        if self._tenant_id:
            from backend.services.asaas_client import AsaasClient
            asaas_client = AsaasClient(cfg.asaas_api_key, environment=cfg.asaas_environment)
        response = AsaasGateway(self._db, client=asaas_client).retrieve_payment(provider_payment_id)
        external_reference = response.get("externalReference") or payment_payload.get("externalReference")
        event.external_reference = external_reference

        payment = (
            self._db.query(Payment)
            .filter(Payment.provider == PROVIDER_ASAAS, Payment.provider_payment_id == provider_payment_id, *self._tenant_payment_filter())
            .first()
            or self._db.query(Payment)
            .filter(Payment.provider == PROVIDER_ASAAS, Payment.transaction_id == provider_payment_id, *self._tenant_payment_filter())
            .first()
        )
        if not payment and external_reference:
            order = self._db.query(Order).filter(Order.external_reference == external_reference, *self._tenant_order_filter()).first()
            if order and order.payment and order.payment.provider == PROVIDER_ASAAS:
                payment = order.payment
        if not payment:
            _logger.warning("Webhook ASAAS: pagamento nao encontrado no banco - asaas_payment_id=%s external_reference=%s", provider_payment_id, external_reference)
            event.processed_at = datetime.now(timezone.utc)
            event.processing_status = "ignored"
            self._db.commit()
            return {"status": "ignored", "reason": f"payment '{provider_payment_id}' not found"}

        if payment.provider_payment_id and str(payment.provider_payment_id) != provider_payment_id:
            event.processed_at = datetime.now(timezone.utc)
            event.processing_status = "ignored"
            self._db.commit()
            return {"status": "ignored", "reason": "stale_webhook_payment_replaced"}

        asaas_amount = response.get("value")
        if asaas_amount is not None and abs(float(asaas_amount) - payment.amount) > 0.05:
            _logger.error(
                "ALERTA: Discrepancia de valor no webhook ASAAS - payment_id=%s payment.amount=%.2f asaas_amount=%.2f asaas_payment_id=%s",
                payment.id,
                payment.amount,
                float(asaas_amount),
                provider_payment_id,
            )

        payment.provider = PROVIDER_ASAAS
        payment.gateway = PROVIDER_ASAAS
        payment.provider_payment_id = provider_payment_id
        payment.provider_status = response.get("status") or payment.provider_status
        payment.transaction_id = provider_payment_id
        payment.external_reference = external_reference or payment.external_reference
        payment.currency = "BRL"
        payment.raw_response = json.dumps(sanitize_asaas_payload(response), ensure_ascii=False)
        payment.webhook_data = event.raw_payload

        new_status = _asaas_status_to_payment(response.get("status"), event_type)
        event.processed_at = datetime.now(timezone.utc)
        event.processing_status = "processed"
        changed = self._apply_status(payment, new_status, source="webhook_asaas")
        if not changed:
            payment.updated_at = datetime.now(timezone.utc)
            self._db.commit()
        return {"status": "ok", "payment_status": new_status.value, "changed": changed}

    def _tenant_payment_filter(self) -> tuple:
        return (Payment.tenant_id == self._tenant_id,) if self._tenant_id else ()

    def _tenant_order_filter(self) -> tuple:
        return (Order.tenant_id == self._tenant_id,) if self._tenant_id else ()

    def _verify_asaas_access_token(self, access_token: str | None, config: PaymentGatewayConfig) -> bool:
        expected = ((config.asaas_webhook_token if self._tenant_id else settings.ASAAS_WEBHOOK_TOKEN or config.asaas_webhook_token) or "").strip()
        received = (access_token or "").strip()
        if not expected or not received:
            return False
        return hmac.compare_digest(expected, received)

    def _verify_mercado_pago_signature(
        self,
        payload: dict[str, Any],
        signature: str | None,
        request_id: str | None,
        config: PaymentGatewayConfig,
        query_params: dict[str, str] | None = None,
    ) -> bool:
        secret = config.mp_webhook_secret if self._tenant_id else settings.MERCADO_PAGO_WEBHOOK_SECRET or config.mp_webhook_secret
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

    def create_preference(self, order_id: str) -> dict:
        order = self._get_order(order_id)
        cfg = self._cfg()
        if not (cfg.accept_credit_card or cfg.accept_debit_card):
            raise DomainError(
                "Forma de pagamento indisponivel. Configure os metodos aceitos em Admin > Pagamentos.",
                code="PaymentMethodDisabled",
            )

        current_order_status = order.status.value if hasattr(order.status, "value") else str(order.status)
        if current_order_status not in {"pending", "waiting_payment", "aguardando_pagamento", "pagamento_recusado", "pagamento_expirado"}:
            raise PaymentOrderNotEligible(order.id, current_order_status)

        if not order.external_reference:
            order.external_reference = f"order-{order.id}"

        method = PaymentMethod.credit_card if cfg.accept_credit_card else PaymentMethod.debit_card
        resolved_gateway = self._resolver().resolve(method)
        if not resolved_gateway.enabled:
            raise DomainError(
                resolved_gateway.reason or "Forma de pagamento indisponivel.",
                code="PaymentMethodDisabled",
            )
        if resolved_gateway.provider == PROVIDER_ASAAS:
            raise DomainError(
                ASAAS_CARD_SAFETY_REASON,
                code="PaymentGatewayNotImplemented",
            )
        if resolved_gateway.provider != PROVIDER_MERCADO_PAGO:
            raise DomainError(
                "Provedor de pagamento indisponivel para checkout.",
                code="PaymentGatewayNotImplemented",
            )
        token = _mp_token(cfg)
        payment = self._pending_payment(
            order,
            PaymentCreate(order_id=order.id, amount=order.total, payment_method=method),
            float(order.total),
            method,
            resolved_gateway.provider,
        )

        if current_order_status == "pending":
            order_sm.transition(order.id, current_order_status, "aguardando_pagamento")
            order.status = OrderStatus.aguardando_pagamento

        self._db.flush()

        excluded_payment_types = [{"id": "bank_transfer"}, {"id": "ticket"}]
        if not cfg.accept_credit_card:
            excluded_payment_types.append({"id": "credit_card"})
        if not cfg.accept_debit_card:
            excluded_payment_types.append({"id": "debit_card"})

        base_url = "https://delivery.moschettieri.com.br"
        body = {
            "items": [{
                "title": f"Moschettieri - Pedido #{order.id[:8].upper()}",
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": round(float(order.total), 2),
            }],
            "payer": {
                "name": order.delivery_name or "Cliente",
                "email": (order.customer.email if order.customer else None) or f"cliente.{order.id[:8].lower()}@delivery.moschettieri.com.br",
            },
            "payment_methods": {
                "excluded_payment_types": excluded_payment_types,
                "installments": 6,
            },
            "back_urls": {
                "success": f"{base_url}/order-tracking?orderId={order.id}",
                "failure": f"{base_url}/order-tracking?orderId={order.id}",
                "pending": f"{base_url}/order-tracking?orderId={order.id}",
            },
            "notification_url": f"{base_url}/api/payments/webhook",
            "external_reference": order.external_reference or order.id,
            "auto_return": "all",
            "metadata": {"order_id": order.id, "payment_id": payment.id},
        }

        response = _mp_request("POST", "/checkout/preferences", token, body)
        init_point = response.get("init_point") or response.get("sandbox_init_point")
        if not init_point:
            raise GatewayError("mercado_pago", "Mercado Pago nao retornou link de pagamento para cartao.")

        payment.payment_url = init_point
        payment.raw_response = json.dumps(response, ensure_ascii=False)
        payment.webhook_data = payment.raw_response
        payment.external_reference = order.external_reference or order.id
        payment.status = PaymentStatus.pending
        self._db.commit()
        self._db.refresh(payment)
        bus.publish(PaymentCreated(payment_id=payment.id, order_id=payment.order_id, method=payment.method.value, amount=payment.amount, gateway=payment.gateway))

        return {
            "preference_id": response.get("id"),
            "init_point": init_point,
        }

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
            currency="BRL",
        )
        self._db.add(payment)
        self._db.flush()
        self._apply_status(payment, PaymentStatus.approved, source="cash")
        self._db.refresh(payment)
        return PaymentOut.model_validate(payment)

    def approve_manual(self, order_id: str) -> PaymentOut:
        order = self._get_order(order_id)
        current_order_status = order.status.value if hasattr(order.status, "value") else str(order.status)
        if current_order_status not in {"pending", "waiting_payment", "aguardando_pagamento"}:
            raise PaymentOrderNotEligible(order.id, current_order_status)

        payment = order.payment or Payment(
            id=str(uuid.uuid4()),
            order_id=order.id,
            method=PaymentMethod.cash,
            status=PaymentStatus.pending,
            amount=order.total,
            gateway="manual",
            provider="manual",
            external_reference=order.external_reference or order.id,
            currency="BRL",
        )
        if payment.status in {PaymentStatus.approved, PaymentStatus.paid}:
            return PaymentOut.model_validate(payment)
        if payment.status != PaymentStatus.pending:
            raise DomainError("Somente pagamentos pendentes podem ser aprovados manualmente.", code="PaymentNotPending")

        if not payment.transaction_id:
            payment.transaction_id = f"MANUAL-{uuid.uuid4().hex[:8].upper()}"
        self._db.add(payment)
        self._db.flush()
        self._apply_status(payment, PaymentStatus.approved, source="admin_manual")
        self._db.refresh(payment)
        return PaymentOut.model_validate(payment)

    def reconcile(self, order_id: str) -> PaymentOut:
        payment = self._get_payment_by_order(order_id)
        self._sync_provider_payment(payment, source="admin_reconcile")
        self._db.refresh(payment)
        return PaymentOut.model_validate(payment)

    def cancel_payment(self, order_id: str, *, reason: str | None = None) -> PaymentOut:
        payment = self._get_payment_by_order(order_id)
        if payment.status in {PaymentStatus.cancelled, PaymentStatus.expired}:
            return PaymentOut.model_validate(payment)
        if payment.status in {PaymentStatus.approved, PaymentStatus.paid, PaymentStatus.refunded}:
            raise DomainError(
                "Pagamento aprovado nao pode ser cancelado; use estorno.",
                code="PaymentCancelRequiresRefund",
            )

        provider = self._payment_provider(payment)
        provider_payment_id = payment.provider_payment_id or payment.mercado_pago_payment_id or payment.transaction_id
        if provider not in {PROVIDER_MERCADO_PAGO, PROVIDER_ASAAS} or not provider_payment_id:
            raise DomainError("Pagamento nao possui cobranca remota cancelavel.", code="PaymentOperationUnsupported")

        if provider == PROVIDER_MERCADO_PAGO:
            response = _mp_request(
                "PUT",
                f"/v1/payments/{provider_payment_id}",
                _mp_token(self._cfg()),
                {"status": "cancelled"},
                idempotency_key=hashlib.sha256(f"{payment.id}:cancel:{reason or ''}".encode()).hexdigest(),
            )
            payment.mercado_pago_payment_id = str(response.get("id") or provider_payment_id)
            payment.provider_payment_id = payment.mercado_pago_payment_id
            payment.provider_status = response.get("status") or payment.provider_status
            payment.transaction_id = payment.mercado_pago_payment_id
            payment.raw_response = json.dumps(response, ensure_ascii=False)
            _store_mp_payment_data(payment, response)
            status = _mp_status_to_payment(response.get("status", "cancelled"), response.get("status_detail"))
        else:
            response = AsaasGateway(self._db).delete_payment(str(provider_payment_id))
            payment.provider = PROVIDER_ASAAS
            payment.gateway = PROVIDER_ASAAS
            payment.provider_payment_id = str(response.get("id") or provider_payment_id)
            payment.provider_status = response.get("status") or "DELETED"
            payment.transaction_id = payment.provider_payment_id
            payment.raw_response = json.dumps(sanitize_asaas_payload(response), ensure_ascii=False)
            status = _asaas_status_to_payment(payment.provider_status, "PAYMENT_DELETED")

        self._apply_status(payment, status, source="admin_cancel")
        self._db.refresh(payment)
        return PaymentOut.model_validate(payment)

    def refund_payment(self, order_id: str, *, reason: str | None = None, value: float | None = None) -> PaymentOut:
        payment = self._get_payment_by_order(order_id)
        if payment.status == PaymentStatus.refunded:
            return PaymentOut.model_validate(payment)
        if payment.status not in {PaymentStatus.approved, PaymentStatus.paid}:
            raise DomainError("Somente pagamentos aprovados podem ser estornados.", code="PaymentRefundNotAllowed")

        refund_value = float(value or payment.amount)
        if abs(refund_value - float(payment.amount)) > 0.01:
            raise DomainError(
                "Estorno parcial ainda nao e suportado por este fluxo operacional.",
                code="PartialRefundNotSupported",
            )

        provider = self._payment_provider(payment)
        provider_payment_id = payment.provider_payment_id or payment.mercado_pago_payment_id or payment.transaction_id
        if provider not in {PROVIDER_MERCADO_PAGO, PROVIDER_ASAAS} or not provider_payment_id:
            raise DomainError("Pagamento nao possui cobranca remota estornavel.", code="PaymentOperationUnsupported")

        if provider == PROVIDER_MERCADO_PAGO:
            refund_response = _mp_request(
                "POST",
                f"/v1/payments/{provider_payment_id}/refunds",
                _mp_token(self._cfg()),
                {},
                idempotency_key=hashlib.sha256(f"{payment.id}:refund:{refund_value:.2f}".encode()).hexdigest(),
            )
            try:
                payment_response = _mp_request("GET", f"/v1/payments/{provider_payment_id}", _mp_token(self._cfg()))
            except DomainError:
                payment_response = {}
            payment.provider_status = payment_response.get("status") or "refunded"
            payment.raw_response = json.dumps(
                {"refund": refund_response, "payment": payment_response},
                ensure_ascii=False,
            )
            if payment_response:
                _store_mp_payment_data(payment, payment_response)
            status = _mp_status_to_payment(payment.provider_status, payment_response.get("status_detail"))
        else:
            refund_response = AsaasGateway(self._db).refund_payment(
                str(provider_payment_id),
                description=reason or "Estorno solicitado pelo administrador",
            )
            try:
                payment_response = AsaasGateway(self._db).retrieve_payment(str(provider_payment_id))
            except DomainError:
                payment_response = {}
            payment.provider = PROVIDER_ASAAS
            payment.gateway = PROVIDER_ASAAS
            payment.provider_payment_id = str(payment_response.get("id") or provider_payment_id)
            payment.provider_status = payment_response.get("status") or refund_response.get("status") or "REFUNDED"
            payment.transaction_id = payment.provider_payment_id
            payment.raw_response = json.dumps(
                sanitize_asaas_payload({"refund": refund_response, "payment": payment_response}),
                ensure_ascii=False,
            )
            status = _asaas_status_to_payment(payment.provider_status, "PAYMENT_REFUNDED")

        if status != PaymentStatus.refunded:
            status = PaymentStatus.refunded
        self._apply_status(payment, status, source="admin_refund")
        self._db.refresh(payment)
        return PaymentOut.model_validate(payment)

    def confirm_pay_on_delivery(self, order_id: str, *, source: str = "pay_on_delivery") -> PaymentOut:
        order = self._get_order(order_id)
        payment = order.payment
        if not payment:
            raise PaymentNotFound(order_id)
        if not payment.pay_on_delivery:
            raise DomainError("Este pedido nao e pagamento na entrega.", code="PaymentMethodMismatch")
        if payment.status in {PaymentStatus.approved, PaymentStatus.paid}:
            return PaymentOut.model_validate(payment)
        if payment.status != PaymentStatus.pending:
            raise DomainError("Somente pagamentos pendentes podem ser confirmados.", code="PaymentNotPending")

        if not payment.transaction_id:
            payment.transaction_id = f"DELIVERY-{uuid.uuid4().hex[:8].upper()}"
        self._db.add(payment)
        self._db.flush()
        self._apply_status(payment, PaymentStatus.approved, source=source)
        self._db.refresh(payment)
        return PaymentOut.model_validate(payment)

    def get_by_order(self, order_id: str) -> PaymentOut:
        payment = self._get_payment_by_order(order_id)
        self._sync_provider_payment(payment, source="status_poll")
        self._db.refresh(payment)
        return PaymentOut.model_validate(payment)

    def payment_status(self, order_id: str) -> dict:
        order = self._get_order(order_id)
        payment = order.payment
        if payment:
            self._sync_provider_payment(payment, source="status_poll")
            self._db.refresh(order)
            payment = order.payment
        # Checkout is locked when a payment was submitted to MP and is still active (pending or approved).
        # Rejected/cancelled/expired payments allow a retry, so they don't lock.
        blocking_statuses = {PaymentStatus.pending, PaymentStatus.approved}
        checkout_locked = bool(
            payment
            and (payment.provider_payment_id or payment.mercado_pago_payment_id or payment.payment_url or payment.qr_code_text)
            and payment.status in blocking_statuses
        )
        return {
            "order_id": order.id,
            "pedido_status": order.status.value,
            "payment_status": payment.status.value if payment else "pending",
            "mercado_pago_payment_id": payment.mercado_pago_payment_id if payment else None,
            "provider_payment_id": payment.provider_payment_id if payment else None,
            "provider_status": payment.provider_status if payment else None,
            "external_reference": order.external_reference,
            "qr_code": payment.qr_code if payment else None,
            "qr_code_text": payment.qr_code_text if payment else None,
            "pix_payload": payment.pix_payload if payment else None,
            "pix_qr_code": payment.pix_qr_code if payment else None,
            "pix_expires_at": payment.pix_expires_at if payment else None,
            "payment_url": payment.payment_url if payment else None,
            "checkout_locked": checkout_locked,
            "payment_method": payment.method.value if payment else None,
            "payment_provider": payment.provider if payment else None,
            "pay_on_delivery": bool(payment.pay_on_delivery) if payment else False,
            "delivery_payment_method": payment.delivery_payment_method if payment else None,
            "cash_needs_change": payment.cash_needs_change if payment else None,
            "cash_change_for": payment.cash_change_for if payment else None,
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

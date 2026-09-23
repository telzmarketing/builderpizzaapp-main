from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from backend.core.exceptions import DomainError
from backend.models.order import Order
from backend.models.payment import Payment, PaymentMethod
from backend.models.payment_config import PaymentGatewayConfig
from backend.services.pagarme_client import PagarmeClient, sanitize_pagarme_payload


class PagarmeGateway:
    provider = "pagarme"

    def __init__(self, config: PaymentGatewayConfig, client: PagarmeClient | None = None):
        self.config = config
        self.client = client or PagarmeClient(config.pagarme_secret_key, environment=config.pagarme_environment)

    def create(self, order: Order, payment: Payment, *, token: str | None, installments: int, document: str | None) -> dict[str, Any]:
        if payment.method == PaymentMethod.credit_card and not token:
            raise DomainError("Token de cartao Pagar.me obrigatorio.", code="PagarmeCardTokenRequired")
        if not order.customer:
            raise DomainError("Cliente do pedido e obrigatorio para Pagar.me.", code="PagarmeCustomerRequired")
        payload = self._order_payload(order, payment, token=token, installments=installments, document=document)
        key = hashlib.sha256(f"{order.tenant_id}:{order.id}:{payment.method.value}:{payment.amount:.2f}".encode()).hexdigest()
        return self.client.create_order(payload, idempotency_key=key)

    def retrieve(self, provider_order_id: str) -> dict[str, Any]:
        return self.client.get_order(provider_order_id)

    def cancel_or_refund(self, charge_id: str, *, amount: float | None = None) -> dict[str, Any]:
        cents = int(round(amount * 100)) if amount is not None else None
        return self.client.cancel_charge(charge_id, amount_cents=cents)

    def _order_payload(self, order: Order, payment: Payment, *, token: str | None, installments: int, document: str | None) -> dict[str, Any]:
        customer = order.customer
        customer_payload: dict[str, Any] = {
            "name": customer.name,
            "email": customer.email,
            "type": "company" if document and len(document) == 14 else "individual",
        }
        if document:
            customer_payload["document"] = document
        phone = re_digits(getattr(customer, "phone", None) or getattr(order, "delivery_phone", None))
        if len(phone) >= 10:
            customer_payload["phones"] = {"mobile_phone": {"country_code": "55", "area_code": phone[-11:-9], "number": phone[-9:]}}
        payment_node: dict[str, Any] = {"payment_method": payment.method.value}
        if payment.method == PaymentMethod.pix:
            payment_node["pix"] = {"expires_in": 3600}
        else:
            payment_node["credit_card"] = {
                "installments": max(1, installments),
                "operation_type": "auth_and_capture",
                "card_token": token,
            }
        cents = int(round(payment.amount * 100))
        return {
            "code": order.id[:52],
            "items": [{"amount": cents, "description": f"Pedido {order.id}"[:256], "quantity": 1}],
            "customer": customer_payload,
            "payments": [payment_node],
            "closed": True,
            "metadata": {"tenant_id": order.tenant_id, "local_order_id": order.id},
        }


def re_digits(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def first_charge(response: dict[str, Any]) -> dict[str, Any]:
    charges = response.get("charges") or []
    return charges[0] if isinstance(charges, list) and charges else {}


def store_pagarme_response(payment: Payment, response: dict[str, Any]) -> None:
    import json
    charge = first_charge(response)
    transaction = charge.get("last_transaction") if isinstance(charge.get("last_transaction"), dict) else {}
    payment.provider = "pagarme"
    payment.gateway = "pagarme"
    payment.provider_payment_id = str(response.get("id") or payment.provider_payment_id or "") or None
    payment.transaction_id = str(charge.get("id") or payment.transaction_id or "") or None
    payment.provider_status = charge.get("status") or response.get("status") or payment.provider_status
    payment.external_reference = response.get("code") or payment.external_reference
    payment.currency = response.get("currency") or "BRL"
    payment.qr_code_text = transaction.get("qr_code") or payment.qr_code_text
    payment.pix_payload = transaction.get("qr_code") or payment.pix_payload
    payment.pix_qr_code = transaction.get("qr_code_url") or payment.pix_qr_code
    expires_at = transaction.get("expires_at")
    if expires_at:
        try:
            payment.pix_expires_at = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
        except ValueError:
            pass
    payment.raw_response = json.dumps(sanitize_pagarme_payload(response), ensure_ascii=False)

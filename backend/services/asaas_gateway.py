from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.exceptions import DomainError
from backend.models.customer import Customer
from backend.models.order import Order
from backend.models.payment import Payment, PaymentProviderCustomer
from backend.models.payment_config import PaymentGatewayConfig
from backend.schemas.payment import AsaasCreditCardPaymentCreate
from backend.services.asaas_client import AsaasClient, sanitize_asaas_payload

settings = get_settings()


def _digits(value: str | None) -> str:
    return re.sub(r"\D+", "", value or "")


class AsaasGateway:
    provider = "asaas"

    def __init__(self, db: Session, client: AsaasClient | None = None):
        self._db = db
        self._client = client

    def create_pix_payment(
        self,
        *,
        order: Order,
        payment: Payment,
        amount: float,
        cpf_cnpj: str | None,
    ) -> Payment:
        if not order.customer:
            raise DomainError(
                "Cliente do pedido e obrigatorio para criar pagamento ASAAS.",
                code="AsaasCustomerRequired",
            )

        customer_link = self.ensure_customer(order.customer, cpf_cnpj=cpf_cnpj, order=order)
        external_reference = order.external_reference or f"order-{order.id}"
        asaas_payment = self._find_remote_payment(external_reference)
        if not asaas_payment:
            asaas_payment = self._client_or_default().create_payment(
                self._build_pix_payment_payload(
                    provider_customer_id=customer_link.provider_customer_id,
                    order=order,
                    amount=amount,
                    external_reference=external_reference,
                )
            )

        provider_payment_id = str(asaas_payment.get("id") or "").strip()
        if not provider_payment_id:
            raise DomainError(
                "ASAAS nao retornou identificador da cobranca Pix.",
                code="AsaasPaymentInvalidResponse",
            )

        qr_code = self._client_or_default().get_pix_qr_code(provider_payment_id)
        self._store_pix_payment_data(payment, asaas_payment, qr_code, customer_link.provider_customer_id)
        return payment

    def create_credit_card_payment(
        self,
        *,
        order: Order,
        payment: Payment,
        amount: float,
        card_payload: AsaasCreditCardPaymentCreate,
        remote_ip: str,
    ) -> Payment:
        if not order.customer:
            raise DomainError(
                "Cliente do pedido e obrigatorio para criar pagamento ASAAS.",
                code="AsaasCustomerRequired",
            )

        holder_info = card_payload.credit_card_holder_info
        customer_link = self.ensure_customer(order.customer, cpf_cnpj=holder_info.cpf_cnpj, order=order)
        external_reference = order.external_reference or f"order-{order.id}"
        asaas_payment = self._find_remote_payment(external_reference, billing_type="CREDIT_CARD")
        if not asaas_payment:
            asaas_payment = self._client_or_default().create_payment(
                self._build_credit_card_payment_payload(
                    provider_customer_id=customer_link.provider_customer_id,
                    order=order,
                    amount=amount,
                    external_reference=external_reference,
                    card_payload=card_payload,
                    remote_ip=remote_ip,
                )
            )

        provider_payment_id = str(asaas_payment.get("id") or "").strip()
        if not provider_payment_id:
            raise DomainError(
                "ASAAS nao retornou identificador da cobranca de cartao.",
                code="AsaasPaymentInvalidResponse",
            )

        self._store_credit_card_payment_data(
            payment,
            asaas_payment,
            customer_link.provider_customer_id,
            installments=card_payload.installments,
        )
        return payment

    def retrieve_payment(self, payment_id: str) -> dict[str, Any]:
        return self._client_or_default().get_payment(payment_id)

    def delete_payment(self, payment_id: str) -> dict[str, Any]:
        return self._client_or_default().delete_payment(payment_id)

    def refund_payment(
        self,
        payment_id: str,
        *,
        value: float | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        return self._client_or_default().refund_payment(
            payment_id,
            value=value,
            description=description,
        )

    def ensure_customer(
        self,
        customer: Customer,
        *,
        cpf_cnpj: str | None = None,
        order: Order | None = None,
    ) -> PaymentProviderCustomer:
        existing = (
            self._db.query(PaymentProviderCustomer)
            .filter(
                PaymentProviderCustomer.customer_id == customer.id,
                PaymentProviderCustomer.provider == self.provider,
            )
            .first()
        )
        if existing and existing.provider_customer_id:
            return existing

        document = _digits(cpf_cnpj)
        if not document:
            raise DomainError(
                "CPF/CNPJ do cliente e obrigatorio para criar cliente ASAAS.",
                code="AsaasCustomerDocumentRequired",
            )

        external_reference = self._external_reference(customer)
        asaas_customer = self._find_remote_customer(external_reference=external_reference, cpf_cnpj=document)
        if not asaas_customer:
            asaas_customer = self._client_or_default().create_customer(
                self._build_customer_payload(customer, document, external_reference, order)
            )

        provider_customer_id = str(asaas_customer.get("id") or "").strip()
        if not provider_customer_id:
            raise DomainError(
                "ASAAS nao retornou identificador do cliente criado.",
                code="AsaasCustomerInvalidResponse",
            )

        record = existing or PaymentProviderCustomer(
            id=f"ppc-{uuid.uuid4().hex[:12]}",
            customer_id=customer.id,
            provider=self.provider,
        )
        record.provider_customer_id = provider_customer_id
        record.external_reference = external_reference
        record.raw_response_sanitized = json.dumps(sanitize_asaas_payload(asaas_customer), ensure_ascii=False)
        self._db.add(record)
        self._db.flush()
        return record

    def _client_or_default(self) -> AsaasClient:
        if self._client:
            return self._client
        config = self._config()
        return AsaasClient(
            settings.ASAAS_API_KEY or config.asaas_api_key,
            environment=config.asaas_environment,
        )

    def _config(self) -> PaymentGatewayConfig:
        config = self._db.query(PaymentGatewayConfig).filter(PaymentGatewayConfig.id == "default").first()
        if not config:
            config = PaymentGatewayConfig(id="default")
            self._db.add(config)
            self._db.flush()
        return config

    def _find_remote_customer(self, *, external_reference: str, cpf_cnpj: str) -> dict[str, Any] | None:
        for query in (
            {"external_reference": external_reference},
            {"cpf_cnpj": cpf_cnpj},
        ):
            response = self._client_or_default().list_customers(**query, limit=1)
            data = response.get("data") if isinstance(response, dict) else None
            if isinstance(data, list) and data:
                return data[0]
        return None

    def _find_remote_payment(self, external_reference: str, *, billing_type: str = "PIX") -> dict[str, Any] | None:
        response = self._client_or_default().list_payments(
            external_reference=external_reference,
            billing_type=billing_type,
            limit=1,
        )
        data = response.get("data") if isinstance(response, dict) else None
        if isinstance(data, list) and data:
            return data[0]
        return None

    def _external_reference(self, customer: Customer) -> str:
        return f"customer-{customer.id}"

    def _build_pix_payment_payload(
        self,
        *,
        provider_customer_id: str,
        order: Order,
        amount: float,
        external_reference: str,
    ) -> dict[str, Any]:
        return {
            "customer": provider_customer_id,
            "billingType": "PIX",
            "value": round(float(amount), 2),
            "dueDate": date.today().isoformat(),
            "description": f"Pedido #{order.order_code or order.id}",
            "externalReference": external_reference,
        }

    def _build_credit_card_payment_payload(
        self,
        *,
        provider_customer_id: str,
        order: Order,
        amount: float,
        external_reference: str,
        card_payload: AsaasCreditCardPaymentCreate,
        remote_ip: str,
    ) -> dict[str, Any]:
        card = card_payload.credit_card
        holder = card_payload.credit_card_holder_info
        payload: dict[str, Any] = {
            "customer": provider_customer_id,
            "billingType": "CREDIT_CARD",
            "value": round(float(amount), 2),
            "dueDate": date.today().isoformat(),
            "description": f"Pedido #{order.order_code or order.id}",
            "externalReference": external_reference,
            "creditCard": {
                "holderName": card.holder_name,
                "number": card.number,
                "expiryMonth": card.expiry_month,
                "expiryYear": card.expiry_year,
                "ccv": card.ccv,
            },
            "creditCardHolderInfo": {
                "name": holder.name,
                "email": holder.email,
                "cpfCnpj": holder.cpf_cnpj,
                "postalCode": holder.postal_code,
                "addressNumber": holder.address_number,
                "addressComplement": holder.address_complement,
                "phone": holder.phone,
                "mobilePhone": holder.mobile_phone,
            },
            "remoteIp": remote_ip,
        }
        if card_payload.installments > 1:
            payload["installmentCount"] = card_payload.installments
            payload["totalValue"] = round(float(amount), 2)
        return self._compact(payload)

    def _store_pix_payment_data(
        self,
        payment: Payment,
        asaas_payment: dict[str, Any],
        qr_code: dict[str, Any],
        provider_customer_id: str,
    ) -> None:
        provider_payment_id = str(asaas_payment.get("id") or "").strip()
        encoded_image = qr_code.get("encodedImage")
        payload = qr_code.get("payload")

        payment.provider = self.provider
        payment.gateway = self.provider
        payment.provider_payment_id = provider_payment_id or payment.provider_payment_id
        payment.provider_customer_id = provider_customer_id
        payment.provider_status = asaas_payment.get("status") or payment.provider_status
        payment.transaction_id = provider_payment_id or payment.transaction_id
        payment.external_reference = asaas_payment.get("externalReference") or payment.external_reference
        payment.currency = "BRL"
        payment.payment_url = asaas_payment.get("invoiceUrl") or asaas_payment.get("bankSlipUrl") or payment.payment_url
        if payload:
            payment.qr_code_text = str(payload)
            payment.pix_payload = str(payload)
        if encoded_image:
            image = str(encoded_image)
            payment.qr_code = image if image.startswith("data:image") else f"data:image/png;base64,{image}"
            payment.pix_qr_code = payment.qr_code
        payment.pix_expires_at = self._parse_expiration(qr_code.get("expirationDate"))
        payment.raw_response = json.dumps(
            sanitize_asaas_payload({"payment": asaas_payment, "pixQrCode": qr_code}),
            ensure_ascii=False,
        )
        payment.webhook_data = payment.raw_response
        payment.updated_at = datetime.now(timezone.utc)
        self._db.add(payment)
        self._db.flush()

    def _store_credit_card_payment_data(
        self,
        payment: Payment,
        asaas_payment: dict[str, Any],
        provider_customer_id: str,
        *,
        installments: int,
    ) -> None:
        provider_payment_id = str(asaas_payment.get("id") or "").strip()
        brand = self._extract_card_brand(asaas_payment)

        payment.provider = self.provider
        payment.gateway = self.provider
        payment.method = payment.method
        payment.provider_payment_id = provider_payment_id or payment.provider_payment_id
        payment.provider_customer_id = provider_customer_id
        payment.provider_status = asaas_payment.get("status") or payment.provider_status
        payment.transaction_id = provider_payment_id or payment.transaction_id
        payment.external_reference = asaas_payment.get("externalReference") or payment.external_reference
        payment.currency = "BRL"
        payment.payment_url = asaas_payment.get("invoiceUrl") or payment.payment_url
        payment.installments = installments
        payment.card_brand = brand or payment.card_brand
        payment.card_brand_logo = self._card_brand_logo(brand) or payment.card_brand_logo
        payment.qr_code = None
        payment.qr_code_text = None
        payment.pix_payload = None
        payment.pix_qr_code = None
        payment.pix_expires_at = None
        payment.raw_response = json.dumps(sanitize_asaas_payload(asaas_payment), ensure_ascii=False)
        payment.webhook_data = payment.raw_response
        payment.updated_at = datetime.now(timezone.utc)
        self._db.add(payment)
        self._db.flush()

    def _parse_expiration(self, value: Any) -> datetime | None:
        if not value:
            return None
        text = str(value).strip()
        try:
            if len(text) == 10:
                return datetime.combine(date.fromisoformat(text), time(23, 59, 59), tzinfo=timezone.utc)
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _build_customer_payload(
        self,
        customer: Customer,
        cpf_cnpj: str,
        external_reference: str,
        order: Order | None,
    ) -> dict[str, Any]:
        phone = _digits(customer.phone or (order.delivery_phone if order else None))
        payload: dict[str, Any] = {
            "name": customer.name or (order.delivery_name if order else None) or f"Cliente {customer.id}",
            "cpfCnpj": cpf_cnpj,
            "email": customer.email,
            "externalReference": external_reference,
            "notificationDisabled": True,
            "groupName": "Telz",
        }
        if phone:
            payload["mobilePhone"] = phone
        if order:
            payload.update(self._address_payload(order))
        return self._compact(payload)

    def _address_payload(self, order: Order) -> dict[str, Any]:
        address = order.address
        if address:
            return {
                "address": address.street,
                "addressNumber": address.number,
                "complement": address.complement,
                "province": address.neighborhood,
                "postalCode": _digits(address.zip_code),
            }
        return {
            "address": order.delivery_street,
            "complement": order.delivery_complement,
        }

    def _extract_card_brand(self, asaas_payment: dict[str, Any]) -> str | None:
        candidates = [
            asaas_payment.get("creditCardBrand"),
            asaas_payment.get("cardBrand"),
            (asaas_payment.get("creditCard") or {}).get("creditCardBrand")
            if isinstance(asaas_payment.get("creditCard"), dict)
            else None,
            (asaas_payment.get("creditCard") or {}).get("brand")
            if isinstance(asaas_payment.get("creditCard"), dict)
            else None,
        ]
        for candidate in candidates:
            text = str(candidate or "").strip()
            if text:
                return text.upper()
        return None

    def _card_brand_logo(self, brand: str | None) -> str | None:
        if not brand:
            return None
        normalized = re.sub(r"[^a-z0-9]+", "_", brand.lower()).strip("_")
        aliases = {
            "master": "mastercard",
            "master_card": "mastercard",
            "american_express": "amex",
        }
        return aliases.get(normalized, normalized)

    def _compact(self, payload: dict[str, Any]) -> dict[str, Any]:
        compact: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, dict):
                nested = self._compact(value)
                if nested:
                    compact[key] = nested
            elif value not in (None, ""):
                compact[key] = value
        return compact

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.models.payment import PaymentMethod
from backend.models.payment_config import PaymentGatewayConfig


PROVIDER_MERCADO_PAGO = "mercado_pago"
PROVIDER_ASAAS = "asaas"
PROVIDER_ON_DELIVERY = "on_delivery"
SUPPORTED_PAYMENT_PROVIDERS = {PROVIDER_MERCADO_PAGO, PROVIDER_ASAAS}
ASAAS_CARD_SAFETY_REASON = (
    "Cartao ASAAS bloqueado: tokenizacao client-side oficial ainda nao homologada neste checkout."
)


def asaas_credit_card_runtime_available() -> bool:
    return False


def normalize_payment_provider(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw in {"mercado_pago", "mercadopago", "mp"}:
        return PROVIDER_MERCADO_PAGO
    if raw == "asaas":
        return PROVIDER_ASAAS
    return raw or PROVIDER_MERCADO_PAGO


def payment_gateway_name(provider: str) -> str:
    return "mercadopago" if provider == PROVIDER_MERCADO_PAGO else provider


@dataclass(frozen=True)
class ResolvedPaymentGateway:
    method: PaymentMethod
    provider: str
    enabled: bool
    reason: str | None = None

    @property
    def gateway(self) -> str:
        return payment_gateway_name(self.provider)


class PaymentGatewayResolver:
    def __init__(self, config: PaymentGatewayConfig):
        self.config = config

    def resolve(self, method: PaymentMethod | str) -> ResolvedPaymentGateway:
        payment_method = method if isinstance(method, PaymentMethod) else PaymentMethod(str(method))

        if payment_method == PaymentMethod.cash:
            return ResolvedPaymentGateway(
                method=payment_method,
                provider=PROVIDER_ON_DELIVERY,
                enabled=bool(self.config.accept_cash),
                reason=None if self.config.accept_cash else "Pagamento na entrega desativado.",
            )

        if not self._method_accepted(payment_method):
            return ResolvedPaymentGateway(
                method=payment_method,
                provider=self.provider_for_method(payment_method),
                enabled=False,
                reason="Forma de pagamento desativada no painel.",
            )

        provider = self.provider_for_method(payment_method)
        if provider not in SUPPORTED_PAYMENT_PROVIDERS:
            return ResolvedPaymentGateway(
                method=payment_method,
                provider=provider,
                enabled=False,
                reason="Provedor de pagamento nao suportado.",
            )

        ready, reason = self._provider_ready(provider, payment_method)
        return ResolvedPaymentGateway(
            method=payment_method,
            provider=provider,
            enabled=ready,
            reason=reason,
        )

    def provider_for_method(self, method: PaymentMethod) -> str:
        if method == PaymentMethod.pix:
            return normalize_payment_provider(self.config.pix_provider or self.config.gateway)
        if method == PaymentMethod.credit_card:
            return normalize_payment_provider(self.config.credit_card_provider or self.config.gateway)
        if method == PaymentMethod.debit_card:
            return PROVIDER_MERCADO_PAGO
        return PROVIDER_ON_DELIVERY

    def public_config(self) -> dict[str, Any]:
        pix = self.resolve(PaymentMethod.pix)
        credit_card = self.resolve(PaymentMethod.credit_card)
        debit_card = self.resolve(PaymentMethod.debit_card)
        cash = self.resolve(PaymentMethod.cash)

        return {
            "gateway": "multi",
            "routing": {
                "pix_provider": self.provider_for_method(PaymentMethod.pix),
                "credit_card_provider": self.provider_for_method(PaymentMethod.credit_card),
            },
            "methods": {
                "pix": self._public_method(pix),
                "credit_card": self._public_method(credit_card),
                "debit_card": self._public_method(debit_card),
                "cash": self._public_method(cash),
            },
            "providers": {
                PROVIDER_MERCADO_PAGO: {
                    "enabled": bool(self.config.mp_enabled),
                    "environment": self.config.mp_environment,
                    "public_key": self.config.mp_public_key or "",
                    "pix_enabled": bool(self.config.mp_pix_enabled),
                    "credit_card_enabled": bool(self.config.mp_credit_card_enabled),
                    "max_installments": self.config.mp_max_installments or 1,
                },
                PROVIDER_ASAAS: {
                    "enabled": bool(self.config.asaas_enabled),
                    "environment": self.config.asaas_environment,
                    "configured": bool(self.config.asaas_api_key),
                    "pix_enabled": bool(self.config.asaas_pix_enabled),
                    "credit_card_enabled": bool(
                        self.config.asaas_credit_card_enabled and asaas_credit_card_runtime_available()
                    ),
                    "credit_card_requested": bool(self.config.asaas_credit_card_enabled),
                    "credit_card_runtime_available": asaas_credit_card_runtime_available(),
                    "credit_card_block_reason": ASAAS_CARD_SAFETY_REASON,
                    "max_installments": self.config.asaas_max_installments or 1,
                    "tokenization_status": self.config.asaas_tokenization_status,
                },
            },
        }

    def _method_accepted(self, method: PaymentMethod) -> bool:
        return {
            PaymentMethod.pix: bool(self.config.accept_pix),
            PaymentMethod.credit_card: bool(self.config.accept_credit_card),
            PaymentMethod.debit_card: bool(self.config.accept_debit_card),
            PaymentMethod.cash: bool(self.config.accept_cash),
        }.get(method, False)

    def _provider_ready(self, provider: str, method: PaymentMethod) -> tuple[bool, str | None]:
        if provider == PROVIDER_MERCADO_PAGO:
            if not self.config.mp_enabled:
                return False, "Mercado Pago desativado."
            if method == PaymentMethod.pix and not self.config.mp_pix_enabled:
                return False, "Pix Mercado Pago desativado."
            if method == PaymentMethod.credit_card and not self.config.mp_credit_card_enabled:
                return False, "Cartao Mercado Pago desativado."
            return True, None

        if provider == PROVIDER_ASAAS:
            if not self.config.asaas_enabled:
                return False, "ASAAS desativado."
            if not self.config.asaas_api_key:
                return False, "ASAAS sem chave de API configurada."
            if method == PaymentMethod.pix and not self.config.asaas_pix_enabled:
                return False, "Pix ASAAS desativado."
            if method == PaymentMethod.credit_card and not self.config.asaas_credit_card_enabled:
                return False, "Cartao ASAAS desativado."
            if method == PaymentMethod.credit_card and self.config.asaas_tokenization_status != "validated":
                return False, "Tokenizacao segura ASAAS nao validada."
            if method == PaymentMethod.credit_card and not asaas_credit_card_runtime_available():
                return False, ASAAS_CARD_SAFETY_REASON
            return True, None

        return False, "Provedor de pagamento nao suportado."

    def _public_method(self, resolved: ResolvedPaymentGateway) -> dict[str, Any]:
        implementation_available = (
            resolved.provider in {PROVIDER_MERCADO_PAGO, PROVIDER_ON_DELIVERY}
            or (resolved.provider == PROVIDER_ASAAS and resolved.method == PaymentMethod.pix)
        )
        implementation_status = "available" if implementation_available else "pending_backend"
        enabled = resolved.enabled and implementation_status == "available"
        reason = resolved.reason
        if resolved.enabled and implementation_status == "pending_backend":
            reason = "Criacao de pagamento ASAAS ainda nao habilitada nesta fase."
        payload: dict[str, Any] = {
            "enabled": enabled,
            "provider": resolved.provider,
            "gateway": resolved.gateway,
            "reason": reason,
            "implementation_status": implementation_status,
        }
        if resolved.method == PaymentMethod.credit_card:
            payload["max_installments"] = self._max_installments(resolved.provider)
        if resolved.method == PaymentMethod.debit_card:
            payload["max_installments"] = 1
        if resolved.provider == PROVIDER_MERCADO_PAGO and resolved.method in {PaymentMethod.credit_card, PaymentMethod.debit_card}:
            payload["public_key"] = self.config.mp_public_key or ""
        return payload

    def _max_installments(self, provider: str) -> int:
        if provider == PROVIDER_ASAAS:
            return max(1, int(self.config.asaas_max_installments or 1))
        return max(1, int(self.config.mp_max_installments or 1))

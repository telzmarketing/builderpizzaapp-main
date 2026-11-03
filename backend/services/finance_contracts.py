"""Canonical, persistence-neutral contracts for financial projections.

These contracts sit between operational events and the existing finance
projections.  They deliberately do not introduce a second financial store.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


CENT = Decimal("0.01")


class FinancialContractViolation(ValueError):
    """Raised when an operational event cannot safely become financial data."""


def validate_purchase_payable_source(
    *,
    purchase_id: object,
    receipt_id: object | None = None,
    receipt_status: str | None = None,
    linked_obligation_id: object | None = None,
) -> None:
    """Prevent a purchase and its receipt from creating competing payables."""

    if not str(purchase_id or "").strip():
        raise FinancialContractViolation("Obrigacao de compra exige purchase_id.")
    if receipt_id and receipt_status != "rejected":
        detail = "ja possui obrigacao financeira" if linked_obligation_id else "possui documento de recebimento"
        raise FinancialContractViolation(f"Compra {detail}; conciliacao explicita obrigatoria.")


def _money(value: object, field: str) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise FinancialContractViolation(f"{field} invalido.") from None
    if not amount.is_finite() or amount <= 0:
        raise FinancialContractViolation(f"{field} precisa ser maior que zero.")
    return amount


@dataclass(frozen=True)
class PaymentConfirmedFact:
    """Canonical meaning of a confirmed payment before projection."""

    tenant_id: str
    payment_id: str
    order_id: str
    gateway: str
    amount: Decimal
    transaction_id: str | None

    @classmethod
    def build(
        cls,
        *,
        tenant_id: str,
        payment_id: str,
        order_id: str,
        gateway: str,
        persisted_gateway: object | None = None,
        payment_amount: object,
        event_amount: object,
        transaction_id: str | None = None,
    ) -> "PaymentConfirmedFact":
        values = {
            "tenant_id": tenant_id,
            "payment_id": payment_id,
            "order_id": order_id,
            "gateway": gateway,
        }
        if any(not str(value or "").strip() for value in values.values()):
            raise FinancialContractViolation("PaymentConfirmed exige tenant, pagamento, pedido e gateway.")
        if persisted_gateway and str(gateway).strip().lower() != str(persisted_gateway).strip().lower():
            raise FinancialContractViolation("O gateway do evento diverge do pagamento persistido.")

        persisted = _money(payment_amount, "valor persistido do pagamento")
        emitted = _money(event_amount, "valor do evento")
        if persisted != emitted:
            raise FinancialContractViolation(
                "O valor do evento diverge do valor persistido do pagamento."
            )

        return cls(
            tenant_id=str(tenant_id),
            payment_id=str(payment_id),
            order_id=str(order_id),
            gateway=str(gateway),
            amount=persisted,
            transaction_id=str(transaction_id) if transaction_id else None,
        )

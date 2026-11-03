from decimal import Decimal

import pytest

from backend.services.finance_contracts import (
    FinancialContractViolation,
    PaymentConfirmedFact,
    validate_purchase_payable_source,
)


def _kwargs(**overrides):
    values = {
        "tenant_id": "tenant-a",
        "payment_id": "pay-1",
        "order_id": "ord-1",
        "gateway": "pix",
        "persisted_gateway": "pix",
        "payment_amount": "42.50",
        "event_amount": "42.50",
        "transaction_id": "tx-1",
    }
    values.update(overrides)
    return values


def test_payment_confirmed_fact_requires_exact_event_and_persisted_amount():
    fact = PaymentConfirmedFact.build(**_kwargs())

    assert fact.amount == Decimal("42.50")
    assert fact.tenant_id == "tenant-a"
    assert fact.transaction_id == "tx-1"


def test_payment_confirmed_fact_rejects_amount_mismatch():
    with pytest.raises(FinancialContractViolation, match="diverge"):
        PaymentConfirmedFact.build(**_kwargs(event_amount="42.49"))


def test_payment_confirmed_fact_rejects_gateway_mismatch():
    with pytest.raises(FinancialContractViolation, match="gateway"):
        PaymentConfirmedFact.build(**_kwargs(gateway="card", persisted_gateway="pix"))


@pytest.mark.parametrize("field", ["tenant_id", "payment_id", "order_id", "gateway"])
def test_payment_confirmed_fact_requires_identity(field):
    with pytest.raises(FinancialContractViolation):
        PaymentConfirmedFact.build(**_kwargs(**{field: ""}))


def test_payment_confirmed_fact_rejects_non_positive_amount():
    with pytest.raises(FinancialContractViolation):
        PaymentConfirmedFact.build(**_kwargs(payment_amount="0", event_amount="0"))


def test_purchase_payable_is_blocked_when_receipt_is_already_present():
    with pytest.raises(FinancialContractViolation, match="documento de recebimento"):
        validate_purchase_payable_source(
            purchase_id="purchase-1",
            receipt_id="receipt-1",
            receipt_status="review_required",
        )


def test_rejected_receipt_does_not_block_purchase_payable():
    validate_purchase_payable_source(
        purchase_id="purchase-1",
        receipt_id="receipt-1",
        receipt_status="rejected",
    )

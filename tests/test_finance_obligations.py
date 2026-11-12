from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.schemas.finance import FinanceObligationFromFiscalIn, FinanceObligationOut
from backend.services.finance_service import FinanceInvalidReference, FinanceService


def _service() -> FinanceService:
    return object.__new__(FinanceService)


def test_fiscal_obligation_does_not_invent_installment_or_due_date():
    payload = FinanceObligationFromFiscalIn.model_validate({})
    assert _service()._validated_obligation_installments(payload, Decimal("100.00")) == []


def test_fiscal_obligation_requires_exact_decimal_installment_total():
    payload = FinanceObligationFromFiscalIn.model_validate({
        "installments": [
            {"installment_number": 1, "amount": "33.33"},
            {"installment_number": 2, "amount": "66.66"},
        ],
    })
    with pytest.raises(FinanceInvalidReference, match="soma das parcelas"):
        _service()._validated_obligation_installments(payload, Decimal("100.00"))


def test_fiscal_obligation_requires_sequential_installments():
    payload = FinanceObligationFromFiscalIn.model_validate({
        "installments": [
            {"installment_number": 1, "amount": "50.00"},
            {"installment_number": 3, "amount": "50.00"},
        ],
    })
    with pytest.raises(FinanceInvalidReference, match="sequencialmente"):
        _service()._validated_obligation_installments(payload, Decimal("100.00"))


def test_receipt_obligation_serializer_allows_missing_fiscal_document():
    row = SimpleNamespace(
        id="fin-obg-receipt",
        tenant_id="tenant-1",
        fiscal_document_id=None,
        idempotency_key="receipt-key",
        status="pending",
        currency="BRL",
        total_amount=Decimal("100.00"),
        product_amount=Decimal("100.00"),
        freight_amount=Decimal("0.00"),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        supplier_name=None,
        supplier_document=None,
        notes=None,
        created_by_admin_id=None,
        created_at=None,
        updated_at=None,
        installments=[],
    )

    serialized = _service()._serialize_obligation(row)
    response = FinanceObligationOut.model_validate(serialized)

    assert serialized["fiscal_document_id"] is None
    assert response.fiscal_document_id is None

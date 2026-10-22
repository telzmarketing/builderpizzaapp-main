from decimal import Decimal

import pytest

from backend.schemas.finance import FinanceObligationFromFiscalIn
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

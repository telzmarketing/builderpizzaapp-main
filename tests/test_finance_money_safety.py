from decimal import Decimal

import pytest

from backend.services.finance_service import FinanceInvalidReference, FinanceService


def test_money_rejects_non_finite_and_negative_operational_values():
    for value in ("NaN", "Infinity", "-Infinity", "-0.01"):
        with pytest.raises(FinanceInvalidReference):
            FinanceService._money(value, "valor")


def test_money_allows_negative_opening_balance_but_keeps_exact_cent_rounding():
    assert FinanceService._money("-12.345", "saldo inicial", allow_negative=True) == Decimal("-12.35")
    assert FinanceService._money("12.345", "valor") == Decimal("12.35")


def test_money_converts_decimal_errors_to_domain_error():
    with pytest.raises(FinanceInvalidReference):
        FinanceService._money(object(), "valor")

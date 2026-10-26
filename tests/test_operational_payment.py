from types import SimpleNamespace

from backend.services.operational_payment import cash_change_amount


def test_cash_change_is_decimal_read_only_and_rejects_invalid_amounts():
    payment = SimpleNamespace(method="cash", cash_needs_change=True,
                              delivery_payment_method="cash", cash_change_for=100)
    assert cash_change_amount(payment, 74.99) == 25.01
    assert payment.cash_change_for == 100
    assert cash_change_amount(payment, 100.01) is None
    assert cash_change_amount(payment, "NaN") is None
    payment.cash_needs_change = False
    assert cash_change_amount(payment, 74.99) is None
    assert cash_change_amount(None, 74.99) is None


def test_cash_change_is_not_projected_for_card_payment():
    payment = SimpleNamespace(method="credit_card", cash_needs_change=True,
                              delivery_payment_method="card", cash_change_for=100)
    assert cash_change_amount(payment, 74.99) is None

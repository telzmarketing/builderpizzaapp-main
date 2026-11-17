from decimal import Decimal

import pytest

from backend.core.exceptions import DomainError
from backend.schemas.order import CheckoutIn
from backend.services.order_service import OrderService


def _payload(**overrides):
    values = {
        "items": [],
        "delivery": {
            "name": "Cliente",
            "phone": "5511999999999",
            "street": "Rua A",
            "city": "Sao Paulo",
        },
        "payment_method": "cash",
    }
    values.update(overrides)
    return CheckoutIn.model_validate(values)


def _resolve(payload, subtotal=Decimal("100.00"), existing=Decimal("0.00"), allowed=True):
    service = OrderService.__new__(OrderService)
    return service._resolve_manual_discount(payload, subtotal, existing, allowed=allowed)


def test_percentage_discount_uses_decimal_and_preserves_requested_value():
    amount, kind, requested = _resolve(_payload(discount_type="percentage", discount_value=12.5))

    assert amount == Decimal("12.50")
    assert kind == "percentage"
    assert requested == 12.5


def test_fixed_discount_cannot_exceed_products_after_coupon():
    with pytest.raises(DomainError, match="superar"):
        _resolve(
            _payload(discount_type="fixed", discount_value=90),
            subtotal=Decimal("100.00"),
            existing=Decimal("20.00"),
        )


def test_percentage_discount_rejects_values_above_one_hundred():
    with pytest.raises(DomainError, match="entre 0 e 100"):
        _resolve(_payload(discount_type="percentage", discount_value=100.01))


def test_public_checkout_cannot_use_manual_discount():
    with pytest.raises(DomainError, match="somente pode"):
        _resolve(
            _payload(discount_type="fixed", discount_value=5),
            allowed=False,
        )

from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.core.exceptions import DomainError
from backend.services.payment_service import PaymentService
from backend.models.payment import PaymentMethod
import backend.services.payment_service as payment_module


def test_incremental_charge_fails_closed_before_creating_remote_charge():
    service = PaymentService.__new__(PaymentService)

    with pytest.raises(DomainError) as exc:
        service._amendment_charge(
            SimpleNamespace(id="order-1"),
            SimpleNamespace(id="amendment-1"),
            SimpleNamespace(),
            Decimal("10.00"),
            "provider-key",
        )

    assert exc.value.code == "PaymentSettlementCustomerActionRequired"


@pytest.mark.parametrize("amount", [Decimal("50.00"), Decimal("50.01")])
def test_amendment_refund_rejects_full_or_over_refund(amount):
    with pytest.raises(DomainError) as exc:
        PaymentService._validate_amendment_refund_amount(50, amount)

    assert exc.value.code == "PaymentSettlementFullRefundUnsupported"


def test_amendment_refund_accepts_strictly_partial_amount():
    PaymentService._validate_amendment_refund_amount(50, Decimal("49.99"))


def test_incremental_pix_charge_returns_customer_action_payload(monkeypatch):
    class FakePagarme:
        def __init__(self, _config):
            pass

        def create_incremental_pix_charge(self, *_args, **_kwargs):
            return {
                "id": "order-amendment-1",
                "charges": [{
                    "id": "charge-1",
                    "status": "pending",
                    "last_transaction": {"qr_code": "000201pix", "qr_code_url": "https://pay.test/1"},
                }],
            }

    monkeypatch.setattr(payment_module, "PagarmeGateway", FakePagarme)
    service = PaymentService.__new__(PaymentService)
    service._payment_provider = lambda _payment: "pagarme"
    service._cfg = lambda: object()
    order = SimpleNamespace(id="order-1", customer=SimpleNamespace(email="customer@example.com"))
    amendment = SimpleNamespace(id="amendment-1")
    payment = SimpleNamespace(method=PaymentMethod.pix)

    result = service._amendment_charge(order, amendment, payment, Decimal("10.00"), "provider-key")

    assert result["status"] == "pending"
    assert result["operation_id"] == "charge-1"
    assert result["qr_code_text"] == "000201pix"
    assert result["checkout_url"] == "https://pay.test/1"

from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.schemas.app_finance import AppFinanceConfigIn, AppFinanceRuleIn
from backend.models.order import Order
from backend.schemas.order import OrderOut
from backend.services.app_finance_service import DeliveryAppFinanceService
from backend.services.finance_service import FinanceInvalidReference, FinanceService
from backend.services.order_service import OrderService


class _Query:
    def __init__(self, config, rules):
        self.config, self.rules = config, rules

    def filter_by(self, **kwargs):
        return self

    def filter(self, *args):
        return self

    def first(self):
        return self.config

    def order_by(self, *args):
        return self

    def all(self):
        return self.rules


class _Db:
    def __init__(self, config, rules):
        self.config, self.rules = config, rules

    def query(self, model):
        return _Query(self.config, self.rules)


def test_app_finance_calculates_percentage_fixed_and_freight_rules():
    config = SimpleNamespace(id="cfg", tenant_id="tenant", app_key="ifood", app_name="iFood", active=True)
    rules = [
        SimpleNamespace(id="a", tenant_id="tenant", config_id="cfg", name="Comissao", rule_type="commission", calculation_type="percentage", value=Decimal("12.50"), sort_order=1, active=True),
        SimpleNamespace(id="b", tenant_id="tenant", config_id="cfg", name="Frete", rule_type="freight", calculation_type="fixed", value=Decimal("5.00"), sort_order=2, active=True),
    ]
    result = DeliveryAppFinanceService(_Db(config, rules), "tenant").calculate("ifood", Decimal("100.00"), Decimal("8.00"))
    assert result["gross_amount"] == Decimal("100.00")
    assert result["deductions"] == Decimal("17.50")
    assert result["net_amount"] == Decimal("82.50")


def test_app_finance_rule_rejects_negative_value():
    try:
        AppFinanceRuleIn(name="Taxa", rule_type="fee", calculation_type="fixed", value=-1)
    except ValueError:
        return
    raise AssertionError("negative app finance rule should be rejected")


def test_app_finance_only_accepts_existing_order_origins():
    for origin in ("partner_99", "ifood", "keeta"):
        assert AppFinanceConfigIn(app_key=origin, app_name=origin).app_key == origin
    try:
        AppFinanceConfigIn(app_key="own", app_name="Loja")
    except ValueError:
        return
    raise AssertionError("own must not be accepted as a delivery app origin")


def test_app_finance_rejects_negative_calculation_amount():
    config = SimpleNamespace(id="cfg", tenant_id="tenant", app_key="ifood", app_name="iFood", active=True)
    try:
        DeliveryAppFinanceService(_Db(config, []), "tenant").calculate("ifood", Decimal("-1"))
    except Exception:
        return
    raise AssertionError("negative gross amount should be rejected")


def test_order_has_queryable_app_finance_snapshot_contract():
    assert {"app_finance_gross_amount", "app_finance_deductions", "app_finance_net_amount", "app_finance_rules"}.issubset(
        Order.__table__.columns.keys()
    )
    payload = OrderOut.model_fields
    assert "app_finance_gross_amount" in payload
    assert "app_finance_deductions" in payload
    assert "app_finance_net_amount" in payload
    assert "app_finance_rules" in payload


def test_order_service_normalizes_decimal_app_finance_snapshot(monkeypatch):
    captured = {}

    def calculate(self, app_key, gross_amount, delivery_fee):
        captured.update(app_key=app_key, gross_amount=gross_amount, delivery_fee=delivery_fee)
        return {
            "app_key": app_key,
            "gross_amount": Decimal("108.00"),
            "deductions": Decimal("18.00"),
            "net_amount": Decimal("90.00"),
            "rules": [{"rule_id": "r1", "name": "Comissao", "amount": Decimal("18.00")}],
        }

    monkeypatch.setattr(DeliveryAppFinanceService, "calculate", calculate)
    service = OrderService.__new__(OrderService)
    service._db = object()
    service._tenant_context = SimpleNamespace(tenant_id="tenant-a")

    snapshot = service._calculate_app_finance_snapshot(
        "ifood", gross_amount=108.0, delivery_fee=8.0
    )

    assert captured == {
        "app_key": "ifood",
        "gross_amount": Decimal("108.0"),
        "delivery_fee": Decimal("8.0"),
    }
    assert snapshot["gross_amount"] == Decimal("108.00")
    assert snapshot["deductions"] == Decimal("18.00")
    assert snapshot["net_amount"] == Decimal("90.00")
    assert snapshot["rules"] == [{"rule_id": "r1", "name": "Comissao", "amount": "18.00"}]
    assert service._calculate_app_finance_snapshot("own", gross_amount=108, delivery_fee=8) is None


def test_finance_payment_composition_separates_customer_discount_and_app_deductions():
    order = SimpleNamespace(
        subtotal=100.0,
        delivery_fee_original=8.0,
        shipping_fee=0.0,
        delivery_fee_final=0.0,
        discount=5.0,
        delivery_fee_discount=3.0,
        app_finance_gross_amount=100.0,
        app_finance_deductions=17.50,
        app_finance_net_amount=82.50,
        sales_channel="delivery",
    )
    service = FinanceService.__new__(FinanceService)

    composition = service._payment_financial_composition(order, Decimal("100.00"))

    assert composition["gross_amount"] == Decimal("108.00")
    assert composition["customer_discount"] == Decimal("8.00")
    assert composition["commercial_amount"] == Decimal("100.00")
    assert composition["app_deductions"] == Decimal("17.50")
    assert composition["settled_net_amount"] == Decimal("82.50")


def test_finance_payment_composition_does_not_double_count_without_app_snapshot():
    order = SimpleNamespace(
        subtotal=100.0,
        delivery_fee_original=8.0,
        shipping_fee=0.0,
        discount=5.0,
        delivery_fee_discount=3.0,
        app_finance_gross_amount=None,
        app_finance_deductions=None,
        app_finance_net_amount=None,
    )
    service = FinanceService.__new__(FinanceService)

    composition = service._payment_financial_composition(order, Decimal("100.00"))

    assert composition["gross_amount"] == Decimal("108.00")
    assert composition["customer_discount"] == Decimal("8.00")
    assert composition["app_deductions"] == Decimal("0.00")
    assert composition["settled_net_amount"] == Decimal("100.00")


def test_finance_payment_composition_rejects_inconsistent_app_snapshot():
    order = SimpleNamespace(
        subtotal=100.0,
        delivery_fee_original=8.0,
        shipping_fee=0.0,
        discount=5.0,
        delivery_fee_discount=3.0,
        app_finance_gross_amount=100.0,
        app_finance_deductions=17.50,
        app_finance_net_amount=81.00,
    )
    service = FinanceService.__new__(FinanceService)

    with pytest.raises(FinanceInvalidReference, match="snapshot financeiro"):
        service._payment_financial_composition(order, Decimal("100.00"))

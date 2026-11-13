from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.core.exceptions import DomainError
from backend.models.marketplace_settlement import MarketplaceSettlement
from backend.models.order import OrderStatus
from backend.schemas.marketplace_settlement import MarketplaceSettlementIn
from backend.services.marketplace_settlement_service import MarketplaceSettlementService, money


def test_settlement_uses_decimal_columns_and_provider_constraints():
    assert str(MarketplaceSettlement.__table__.c.expected_net_amount.type) == "NUMERIC(20, 2)"
    checks = {constraint.name: str(constraint.sqltext) for constraint in MarketplaceSettlement.__table__.constraints if constraint.name}
    assert "partner_99" in checks["ck_marketplace_settlements_provider"]
    assert "received" in checks["ck_marketplace_settlements_status"]


def _payload():
    return MarketplaceSettlementIn(provider="ifood", gross_amount=Decimal("100.00"), expected_net_amount=Decimal("82.35"), received_net_amount=Decimal("80.00"), status="divergent")


class _Query:
    def __init__(self, row): self.row = row
    def filter(self, *args, **kwargs): return self
    def filter_by(self, **kwargs): return self
    def first(self): return self.row


class _DB:
    def __init__(self, order): self.order = order
    def query(self, model):
        if model.__name__ == "Order": return _Query(self.order)
        return _Query(None)


def test_settlement_rejects_undelivered_or_own_order():
    order = SimpleNamespace(id="o1", order_origin="own", status=OrderStatus.delivered)
    with pytest.raises(DomainError) as error:
        MarketplaceSettlementService(_DB(order), "tenant-a").create("o1", _payload(), "settlement-1")
    assert error.value.code == "MarketplaceSettlementOrderNotEligible"


def test_settlement_requires_idempotency_key():
    with pytest.raises(DomainError) as error:
        MarketplaceSettlementService(_DB(None), "tenant-a").create("o1", _payload(), " ")
    assert error.value.code == "MarketplaceSettlementIdempotencyRequired"


def test_settlement_money_rounds_as_decimal():
    assert money(Decimal("82.354")) == Decimal("82.35")
    assert money(Decimal("80.00") - Decimal("82.35")) == Decimal("-2.35")

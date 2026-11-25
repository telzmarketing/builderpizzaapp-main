from decimal import Decimal
from importlib import import_module
from pkgutil import iter_modules
from types import SimpleNamespace

import pytest

import backend.models
from backend.core.exceptions import DomainError
from backend.models.marketplace_settlement import MarketplaceSettlement
from backend.models.finance import FinanceTransaction
from backend.models.order import OrderStatus
from backend.schemas.marketplace_settlement import MarketplaceSettlementIn
from backend.services.marketplace_settlement_service import MarketplaceSettlementService, money


for module in iter_modules(backend.models.__path__):
    import_module(f"backend.models.{module.name}")


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


class _RowsQuery:
    def __init__(self, rows, order=None):
        self.rows = rows
        self.order = order
        self.criteria = {}

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, **kwargs):
        self.criteria.update(kwargs)
        return self

    def first(self):
        if self.order is not None:
            return self.order
        return next((row for row in self.rows if all(getattr(row, key, None) == value for key, value in self.criteria.items())), None)


class _RowsDB:
    def __init__(self, order):
        self.order = order
        self.settlements = []
        self.transactions = []

    def query(self, model):
        if model.__name__ == "Order":
            return _RowsQuery([], self.order)
        if model.__name__ == "MarketplaceSettlement":
            return _RowsQuery(self.settlements)
        if model.__name__ == "FinanceTransaction":
            return _RowsQuery(self.transactions)
        raise AssertionError(f"unexpected model: {model.__name__}")

    def add(self, row):
        if isinstance(row, MarketplaceSettlement):
            self.settlements.append(row)
        elif isinstance(row, FinanceTransaction):
            self.transactions.append(row)

    def flush(self):
        return None

    def commit(self):
        return None

    def refresh(self, row):
        return None


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


@pytest.mark.parametrize("status", ["received", "partially_received"])
def test_received_settlement_creates_one_idempotent_income_transaction(status):
    order = SimpleNamespace(id="o1", order_origin="ifood", status=OrderStatus.delivered)
    db = _RowsDB(order)
    payload = _payload().model_copy(update={"status": status, "settled_at": None})
    service = MarketplaceSettlementService(db, "tenant-a")

    first = service.create("o1", payload, "settlement-1", admin_id="admin-a")
    second = service.create("o1", payload, "settlement-1", admin_id="admin-a")

    assert first.id == second.id
    assert len(db.transactions) == 1
    transaction = db.transactions[0]
    assert transaction.tenant_id == "tenant-a"
    assert transaction.origin_type == "marketplace_settlement"
    assert transaction.origin_id == first.id
    assert transaction.entry_type == "income"
    assert transaction.amount == transaction.net_amount == 80.0
    assert transaction.description == "Recebimento ifood pedido o1"


def test_expected_settlement_does_not_create_income_transaction():
    order = SimpleNamespace(id="o1", order_origin="ifood", status=OrderStatus.delivered)
    db = _RowsDB(order)
    payload = _payload().model_copy(update={"status": "expected", "received_net_amount": Decimal("0")})

    MarketplaceSettlementService(db, "tenant-a").create("o1", payload, "settlement-expected")

    assert db.transactions == []

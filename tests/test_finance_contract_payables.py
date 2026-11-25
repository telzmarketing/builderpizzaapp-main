from datetime import date
from decimal import Decimal
from importlib import import_module
from pkgutil import iter_modules

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import backend.models
from backend.database import Base
from backend.models.finance import FinanceAccount, FinanceCategory, FinanceContract, FinanceCounterparty, FinanceTransaction
from backend.models.gestao import GestaoModuleSettings
from backend.services.finance_service import FinanceInvalidReference, FinanceService


for module in iter_modules(backend.models.__path__):
    import_module(f"backend.models.{module.name}")


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    models = [FinanceAccount, FinanceCategory, FinanceCounterparty, FinanceContract, FinanceTransaction, GestaoModuleSettings]
    Base.metadata.create_all(engine, tables=[model.__table__ for model in models])
    with Session(engine) as session:
        session.add(GestaoModuleSettings(
            id="settings-finance-a", tenant_id="tenant-a", module_key="finance",
            title="Financeiro", description="", enabled=True, status="active", settings_json="{}", notes="",
        ))
        session.add(FinanceCounterparty(
            id="supplier-a", tenant_id="tenant-a", name="Fornecedor A", counterparty_type="supplier",
        ))
        session.commit()
        yield session
    engine.dispose()


def service(db):
    return FinanceService(db, "tenant-a")


def contract(**overrides):
    values = dict(
        id="contract-a", tenant_id="tenant-a", counterparty_id="supplier-a", title="Contrato mensal",
        start_date=date(2026, 1, 31), end_date=date(2026, 4, 30), amount=Decimal("100.00"),
        billing_period="monthly", status="active",
    )
    values.update(overrides)
    return FinanceContract(**values)


def test_active_contract_generates_canonical_payables_and_is_idempotent(db):
    db.add(contract())
    db.commit()

    first = service(db).generate_contract_payables("contract-a", "admin-a")
    second = service(db).generate_contract_payables("contract-a", "admin-a")
    rows = db.query(FinanceTransaction).order_by(FinanceTransaction.installment_number).all()

    assert first["created"] == 4
    assert first["already_synced"] == 0
    assert second["created"] == 0
    assert second["already_synced"] == 4
    assert [row.due_date for row in rows] == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 28), date(2026, 4, 28)]
    assert all(row.origin_type == "finance_contract_payable" for row in rows)
    assert all(row.status == "pending" and row.entry_type == "expense" for row in rows)


@pytest.mark.parametrize("status", ["draft", "cancelled", "expired"])
def test_only_active_contracts_generate_payables(db, status):
    db.add(contract(status=status))
    db.commit()
    with pytest.raises(FinanceInvalidReference, match="ativos"):
        service(db).generate_contract_payables("contract-a")


def test_recurring_contract_requires_finite_end_date(db):
    db.add(contract(end_date=None))
    db.commit()
    with pytest.raises(FinanceInvalidReference, match="data final"):
        service(db).generate_contract_payables("contract-a")

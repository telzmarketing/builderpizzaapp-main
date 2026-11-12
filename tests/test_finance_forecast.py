"""Read-only forecast contract tests for the finance planning foundation."""

from datetime import date
from importlib import import_module
from pkgutil import iter_modules

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import backend.models
from backend.core.tenant_context import TenantContext, TenantSource
from backend.database import Base
from backend.models.finance import FinanceAccount, FinanceTransaction
from backend.services.finance_service import FinanceInvalidReference, FinanceService


for module in iter_modules(backend.models.__path__):
    import_module(f"backend.models.{module.name}")


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[FinanceAccount.__table__, FinanceTransaction.__table__])
    with Session(engine) as session:
        session.add(FinanceAccount(id="account-a", tenant_id="tenant-a", name="Caixa A", opening_balance=100))
        session.commit()
        yield session
    engine.dispose()


def test_forecast_returns_requested_periods_without_inventing_values(db):
    service = FinanceService(db, "tenant-a", TenantContext(tenant_id="tenant-a", source=TenantSource.JOB))

    result = service.forecast(2)

    assert result["months"] == 2
    assert len(result["periods"]) == 2
    assert result["periods"][0]["opening_balance"] == 100
    assert result["periods"][0]["projected_income"] == 0
    assert result["periods"][0]["projected_expense"] == 0
    assert result["periods"][0]["source_count"] == 0
    assert "Nenhuma receita" in result["methodology"]


def test_forecast_uses_open_due_amount_and_paid_cash_effect(db):
    today = date.today()
    db.add_all([
        FinanceTransaction(
            id="income-paid", tenant_id="tenant-a", entry_type="income", status="paid",
            description="Venda liquidada", amount=80, paid_amount=80, net_amount=80,
            competence_date=today,
        ),
        FinanceTransaction(
            id="expense-open", tenant_id="tenant-a", entry_type="expense", status="pending",
            description="Conta futura", amount=40, paid_amount=0, net_amount=0,
            competence_date=today, due_date=today,
        ),
    ])
    db.commit()
    service = FinanceService(db, "tenant-a", TenantContext(tenant_id="tenant-a", source=TenantSource.JOB))

    period = service.forecast(1)["periods"][0]

    assert period["projected_income"] == 80
    assert period["projected_expense"] == 40
    assert period["projected_result"] == 40
    assert period["closing_balance"] == 140
    assert period["source_count"] == 2


@pytest.mark.parametrize("months", [0, 13])
def test_forecast_rejects_unsupported_horizon(db, months):
    service = FinanceService(db, "tenant-a", TenantContext(tenant_id="tenant-a", source=TenantSource.JOB))

    with pytest.raises(FinanceInvalidReference):
        service.forecast(months)

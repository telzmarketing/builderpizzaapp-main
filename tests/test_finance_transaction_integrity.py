"""Financial commands against an isolated, in-memory ORM database.

These tests exercise persistence and rollback, not PostgreSQL row locks or
production constraints. No application database connection is used.
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from importlib import import_module
from pkgutil import iter_modules

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

import backend.models
from backend.database import Base
from backend.core.tenant_context import TenantContext, TenantSource
from backend.models.finance import (
    FinanceAccount, FinanceCategory, FinanceCounterparty, FinanceObligation,
    FinanceObligationInstallment, FinanceSettlement, FinanceTransaction,
)
from backend.schemas.finance import FinanceSettlementIn, FinanceTransactionIn, FinanceTransactionOut
from backend.services.finance_service import FinanceInvalidReference, FinanceNotFound, FinanceService


# Configure the existing shared mapper registry without creating other tables.
for module in iter_modules(backend.models.__path__):
    import_module(f"backend.models.{module.name}")


PAID_AT = datetime(2026, 11, 1, 12, 30, tzinfo=timezone.utc)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        model.__table__ for model in (
            FinanceAccount, FinanceCategory, FinanceCounterparty,
            FinanceObligation, FinanceTransaction, FinanceSettlement,
            FinanceObligationInstallment,
        )
    ])
    with Session(engine) as session:
        session.add_all([
            FinanceAccount(id="account-a", tenant_id="tenant-a", name="Caixa A"),
            FinanceAccount(id="account-b", tenant_id="tenant-b", name="Caixa B"),
        ])
        session.commit()
        yield session
    engine.dispose()


def service(db, tenant="tenant-a"):
    context = TenantContext(tenant_id=tenant, source=TenantSource.JOB)
    return FinanceService(db, tenant, context)


def body(**overrides):
    values = dict(
        description="Titulo de teste", amount=100, competence_date=date(2026, 11, 1),
        account_id="account-a", payment_method="cash", payment_reference="receipt-1",
        paid_at=PAID_AT, notes="Comprovante de teste",
    )
    values.update(overrides)
    return FinanceTransactionIn(**values)


@pytest.mark.parametrize("command", ["create", "update"])
@pytest.mark.parametrize("paid_amount", [0.001, 0.01, 40, 99.99, 100.01])
def test_paid_requires_the_full_adjusted_total(db, command, paid_amount):
    svc = service(db)
    transaction_id = svc.create_transaction(body())["id"] if command == "update" else None
    with pytest.raises(FinanceInvalidReference):
        payload = body(status="paid", paid_amount=paid_amount)
        if transaction_id:
            svc.update_transaction(transaction_id, payload)
        else:
            svc.create_transaction(payload)
    db.expire_all()
    assert db.query(FinanceSettlement).count() == 0
    if transaction_id:
        row = db.get(FinanceTransaction, transaction_id)
        assert (row.status, row.paid_amount) == ("pending", 0)
    else:
        assert db.query(FinanceTransaction).count() == 0


@pytest.mark.parametrize("command", ["create", "update"])
@pytest.mark.parametrize("status,paid", [("paid", 100), ("paid", 0), ("partial", 40)])
@pytest.mark.parametrize("entry_type", ["income", "expense"])
def test_creation_or_edit_with_payment_persists_one_settlement(db, command, status, paid, entry_type):
    svc = service(db)
    transaction_id = svc.create_transaction(body())["id"] if command == "update" else None
    payload = body(status=status, paid_amount=paid, entry_type=entry_type, fee_amount=3)
    result = (
        svc.update_transaction(transaction_id, payload, "actor-1") if transaction_id
        else svc.create_transaction(payload, "actor-1")
    )
    response = FinanceTransactionOut.model_validate(result)
    effective_paid = 100 if status == "paid" else 40
    expected_net = effective_paid + (3 if entry_type == "expense" else -3)
    settlement = db.query(FinanceSettlement).one()
    assert response.status == status
    assert response.paid_amount == effective_paid
    assert response.net_amount == expected_net
    assert settlement.transaction_id == response.id
    assert settlement.tenant_id == response.tenant_id == "tenant-a"
    assert settlement.account_id == "account-a"
    assert settlement.principal_amount == effective_paid
    assert settlement.fee_amount == 3
    assert settlement.net_amount == expected_net
    assert settlement.settled_at.replace(tzinfo=timezone.utc) == PAID_AT
    assert settlement.created_by_admin_id == "actor-1"
    assert settlement.payment_method == "cash"
    assert settlement.payment_reference == "receipt-1"
    assert settlement.notes == "Comprovante de teste"
    expected_balance = expected_net if entry_type == "income" else -expected_net
    assert svc._account_balance_map() == {"account-a": expected_balance}
    summary = svc.summary()
    assert summary[f"{entry_type}_paid"] == expected_net
    assert summary[f"{entry_type}_pending"] == (0 if status == "paid" else 60)


@pytest.mark.parametrize("status", ["pending", "cancelled"])
def test_unpaid_creation_has_no_settlement(db, status):
    result = service(db).create_transaction(body(status=status))
    assert result["status"] == status
    assert db.query(FinanceSettlement).count() == 0


def test_paid_without_account_keeps_optional_account_contract(db):
    result = service(db).create_transaction(body(status="paid", account_id=None))
    assert result["paid_amount"] == 100
    assert db.query(FinanceSettlement).one().account_id is None


def test_paid_uses_adjustments_and_half_up_cent_rounding(db):
    result = service(db).create_transaction(body(
        status="paid", amount=12.345, interest_amount=1.005, fine_amount=0.015,
        discount_amount=0.025, fee_amount=0.015, paid_amount=13.35,
    ))
    assert result["amount"] == 12.35
    assert result["paid_amount"] == 13.35
    settlement = db.query(FinanceSettlement).one()
    assert settlement.interest_amount == 1.01
    assert settlement.fine_amount == 0.02
    assert settlement.discount_amount == 0.03
    assert settlement.fee_amount == 0.02
    assert settlement.net_amount == 13.37


def test_paid_below_adjusted_total_is_rejected(db):
    with pytest.raises(FinanceInvalidReference):
        service(db).create_transaction(body(status="paid", paid_amount=100, interest_amount=10))
    assert db.query(FinanceTransaction).count() == 0


def test_partial_creation_then_normal_settlement_preserves_both_movements(db):
    svc = service(db)
    result = svc.create_transaction(body(status="partial", paid_amount=40))
    initial = db.query(FinanceSettlement).one()
    initial_id = initial.id
    result = svc.settle_transaction(result["id"], FinanceSettlementIn(paid_amount=60))
    assert result["status"] == "paid"
    assert result["paid_amount"] == 100
    assert db.query(FinanceSettlement).count() == 2
    assert db.get(FinanceSettlement, initial_id).principal_amount == 40
    assert svc._account_balance_map() == {"account-a": -100}


@pytest.mark.parametrize("paid_amount", [0, 100, 101])
def test_invalid_partial_payment_does_not_create_title_or_settlement(db, paid_amount):
    with pytest.raises(FinanceInvalidReference, match="parcial"):
        service(db).create_transaction(body(status="partial", paid_amount=paid_amount))
    assert db.query(FinanceTransaction).count() == 0
    assert db.query(FinanceSettlement).count() == 0


def test_valid_explicit_net_and_default_payment_date_are_preserved(db):
    result = service(db).create_transaction(body(
        status="paid", entry_type="income", fee_amount=3, net_amount=97, paid_at=None,
    ))
    assert result["net_amount"] == 97
    assert result["paid_at"] is not None
    assert db.query(FinanceSettlement).one().settled_at == result["paid_at"]


@pytest.mark.parametrize("cancelled_history", [False, True])
def test_edit_does_not_overwrite_payment_history(db, cancelled_history):
    svc = service(db)
    result = svc.create_transaction(body(status="paid"))
    original = db.query(FinanceSettlement).one()
    if cancelled_history:
        original.cancelled_at = PAID_AT
        row = db.get(FinanceTransaction, result["id"])
        row.paid_amount = 0
        row.net_amount = 0
        row.status = "pending"
        db.commit()
    with pytest.raises(FinanceInvalidReference, match="liquidacao"):
        svc.update_transaction(result["id"], body(status="paid", amount=200))
    assert db.query(FinanceSettlement).count() == 1
    assert original.principal_amount == 100
    assert db.get(FinanceTransaction, result["id"]).amount == 100


@pytest.mark.parametrize("command", ["create", "update"])
def test_title_and_settlement_roll_back_together_on_database_failure(db, command):
    svc = service(db)
    transaction_id = svc.create_transaction(body())["id"] if command == "update" else None

    def fail_settlement_insert(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("INSERT INTO FINANCE_SETTLEMENTS"):
            raise RuntimeError("simulated settlement insert failure")

    event.listen(db.get_bind(), "before_cursor_execute", fail_settlement_insert)
    with pytest.raises(RuntimeError, match="simulated settlement"):
        if transaction_id:
            svc.update_transaction(transaction_id, body(status="paid"))
        else:
            svc.create_transaction(body(status="paid"))
    # The command must roll back itself: the same session remains usable.
    assert db.query(FinanceSettlement).count() == 0
    if transaction_id:
        row = db.get(FinanceTransaction, transaction_id)
        assert (row.status, row.paid_amount, row.net_amount) == ("pending", 0, 0)
    else:
        assert db.query(FinanceTransaction).count() == 0


def test_foreign_tenant_account_or_transaction_is_rejected(db):
    svc = service(db)
    with pytest.raises(FinanceNotFound):
        svc.create_transaction(body(status="paid", account_id="account-b"))
    foreign = service(db, "tenant-b").create_transaction(body(account_id="account-b"))
    with pytest.raises(FinanceNotFound):
        svc.update_transaction(foreign["id"], body(status="paid"))
    assert db.query(FinanceSettlement).count() == 0


def test_reconciliation_rejects_foreign_tenant_obligation(db):
    obligation = FinanceObligation(
        id="foreign-obligation", tenant_id="tenant-b", idempotency_key="foreign-1",
        total_amount=Decimal("100.00"), status="pending",
    )
    db.add(obligation)
    db.commit()
    with pytest.raises(FinanceNotFound):
        service(db).reconcile_obligation(obligation.id)
    assert obligation.status == "pending"


@pytest.mark.parametrize("status", ["paid", "partial"])
def test_inconsistent_net_amount_is_rejected_before_persistence(db, status):
    with pytest.raises(FinanceInvalidReference):
        service(db).create_transaction(body(status=status, paid_amount=40 if status == "partial" else 100, net_amount=999))
    assert db.query(FinanceSettlement).count() == 0
    assert db.query(FinanceTransaction).count() == 0


@pytest.mark.parametrize("status", ["pending", "cancelled"])
def test_reconciling_empty_obligation_preserves_state_and_audit_timestamp(db, status):
    svc = service(db)
    obligation = FinanceObligation(
        id="obligation-empty", tenant_id="tenant-a", idempotency_key="empty-1",
        total_amount=Decimal("100.00"), status=status,
    )
    db.add(obligation)
    db.commit()
    timestamp = obligation.updated_at
    result = svc.reconcile_obligation(obligation.id)
    db.refresh(obligation)
    assert result["status"] == status
    assert result["installments"] == []
    assert obligation.updated_at == timestamp
    assert db.query(FinanceTransaction).count() == 0
    assert db.query(FinanceSettlement).count() == 0


@pytest.mark.parametrize("statuses,expected", [
    (["paid", "paid"], "paid"),
    (["pending", "partial"], "partial"),
    (["pending", "pending"], "pending"),
    (["cancelled", "cancelled"], "cancelled"),
])
def test_nonempty_obligation_keeps_legitimate_reconciliation(db, statuses, expected):
    svc = service(db)
    obligation = FinanceObligation(
        id="obligation-1", tenant_id="tenant-a", idempotency_key="obligation-key",
        total_amount=Decimal("100.00"),
    )
    for number, status in enumerate(statuses, 1):
        tx = svc.create_transaction(body(
            amount=50, status=status, paid_amount=20 if status == "partial" else 0,
        ))
        obligation.installments.append(FinanceObligationInstallment(
            id=f"installment-{number}", tenant_id="tenant-a", installment_number=number,
            amount=Decimal("50.00"), finance_transaction_id=tx["id"],
        ))
    db.add(obligation)
    db.commit()
    assert svc.reconcile_obligation(obligation.id)["status"] == expected


def test_invalid_legacy_paid_status_does_not_hide_open_balance():
    svc = object.__new__(FinanceService)
    row = FinanceTransaction(status="paid", amount=100, paid_amount=40)
    assert svc._open_amount(row) == 60

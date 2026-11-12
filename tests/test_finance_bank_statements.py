from datetime import date
from decimal import Decimal
from importlib import import_module
from pkgutil import iter_modules

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.database import Base
import backend.models
from backend.core.tenant_context import TenantContext, TenantSource
from backend.models.finance import FinanceAccount, FinanceBankReconciliationEvent, FinanceBankStatement, FinanceBankStatementLine, FinanceTransaction
from backend.schemas.finance import FinanceBankMatchIn, FinanceBankReconciliationReasonIn, FinanceBankStatementImportIn, FinanceBankStatementLineIn
from backend.services.finance_service import FinanceInvalidReference, FinanceService


for module in iter_modules(backend.models.__path__):
    import_module(f"backend.models.{module.name}")


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        FinanceAccount.__table__,
        FinanceBankStatement.__table__,
        FinanceBankStatementLine.__table__,
        FinanceTransaction.__table__,
        FinanceBankReconciliationEvent.__table__,
    ])
    with Session(engine) as session:
        session.add(FinanceAccount(id="account-a", tenant_id="tenant-a", name="Conta principal"))
        session.commit()
        yield session
    engine.dispose()


def service(db):
    return FinanceService(db, "tenant-a", TenantContext(tenant_id="tenant-a", source=TenantSource.JOB))


def payload(**overrides):
    values = dict(
        account_id="account-a",
        source="csv",
        file_hash="sha256:test-extrato",
        period_start=date(2026, 11, 1),
        period_end=date(2026, 11, 2),
        lines=[
            FinanceBankStatementLineIn(
                external_id="bank-line-1",
                transaction_date=date(2026, 11, 1),
                description="Tarifa bancaria",
                amount=Decimal("-12.50"),
                balance=Decimal("987.50"),
            ),
        ],
    )
    values.update(overrides)
    return FinanceBankStatementImportIn(**values)


def test_import_is_idempotent_by_file_hash(db):
    svc = service(db)

    first = svc.import_bank_statement(payload())
    second = svc.import_bank_statement(payload())

    assert second["id"] == first["id"]
    assert db.query(FinanceBankStatement).count() == 1
    assert db.query(FinanceBankStatementLine).count() == 1
    assert svc.list_bank_statement_lines(first["id"])[0]["reconciliation_status"] == "unmatched"


def test_import_rejects_duplicate_external_ids(db):
    svc = service(db)
    duplicate = FinanceBankStatementLineIn(
        external_id="same-line",
        transaction_date=date(2026, 11, 1),
        description="Duplicado",
        amount=Decimal("10.00"),
    )

    with pytest.raises(FinanceInvalidReference, match="identificadores"):
        svc.import_bank_statement(payload(file_hash=None, lines=[duplicate, duplicate]))

    assert db.query(FinanceBankStatement).count() == 0


def test_reconciliation_suggests_and_confirms_same_account_movement(db):
    svc = service(db)
    transaction = FinanceTransaction(
        id="transaction-a",
        tenant_id="tenant-a",
        account_id="account-a",
        entry_type="expense",
        status="paid",
        description="Tarifa bancaria",
        amount=12.50,
        paid_amount=12.50,
        net_amount=12.50,
        competence_date=date(2026, 11, 1),
    )
    db.add(transaction)
    db.commit()
    statement = svc.import_bank_statement(payload())

    reconciliation = svc.list_bank_reconciliation(statement["id"])
    assert [candidate["id"] for candidate in reconciliation[0]["candidates"]] == ["transaction-a"]

    matched = svc.match_bank_statement_line(reconciliation[0]["id"], FinanceBankMatchIn(transaction_id="transaction-a"))
    assert matched["reconciliation_status"] == "matched"
    assert matched["matched_transaction_id"] == "transaction-a"

    unmatched = svc.unmatch_bank_statement_line(
        reconciliation[0]["id"],
        FinanceBankReconciliationReasonIn(reason="Valor confirmado em outro comprovante."),
        admin_id="admin-a",
    )
    assert unmatched["reconciliation_status"] == "unmatched"
    assert unmatched["matched_transaction_id"] is None
    events = svc.list_reconciliation_events(reconciliation[0]["id"])
    assert [event["action"] for event in events] == ["unmatched", "matched"]
    assert events[0]["reason"] == "Valor confirmado em outro comprovante."

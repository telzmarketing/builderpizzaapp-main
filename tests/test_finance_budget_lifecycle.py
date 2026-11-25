from datetime import date
from importlib import import_module
from pkgutil import iter_modules

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import backend.models
from backend.database import Base
from backend.core.tenant_context import TenantContext, TenantSource
from backend.models.finance import FinanceBudget, FinanceBudgetLine, FinanceCategory
from backend.schemas.finance import FinanceBudgetIn, FinanceBudgetLineIn
from backend.services.finance_service import FinanceInvalidReference, FinanceNotFound, FinanceService

for module in iter_modules(backend.models.__path__):
    import_module(f"backend.models.{module.name}")


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[FinanceCategory.__table__, FinanceBudget.__table__, FinanceBudgetLine.__table__])
    with Session(engine) as session:
        yield session
    engine.dispose()


def _service(db, tenant="tenant-a"):
    return FinanceService(db, tenant, TenantContext(tenant_id=tenant, source=TenantSource.JOB))


def _payload():
    return FinanceBudgetIn(
        name="Plano 2026",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        lines=[FinanceBudgetLineIn(planned_amount="100.00")],
    )


def test_budget_lifecycle_is_forward_only_and_idempotent(db):
    service = _service(db)
    budget = service.create_budget(_payload())
    assert service.activate_budget(budget["id"])["status"] == "active"
    assert service.activate_budget(budget["id"])["status"] == "active"
    assert service.close_budget(budget["id"])["status"] == "closed"
    assert service.close_budget(budget["id"])["status"] == "closed"
    with pytest.raises(FinanceInvalidReference, match="nao pode mudar"):
        service.activate_budget(budget["id"])


def test_budget_cannot_close_before_activation(db):
    service = _service(db)
    budget = service.create_budget(_payload())
    with pytest.raises(FinanceInvalidReference, match="nao pode mudar"):
        service.close_budget(budget["id"])


def test_budget_lifecycle_is_tenant_scoped(db):
    budget = _service(db, "tenant-a").create_budget(_payload())
    with pytest.raises(FinanceNotFound):
        _service(db, "tenant-b").activate_budget(budget["id"])


def test_budget_transition_rolls_back_when_commit_fails(db, monkeypatch):
    service = _service(db)
    budget = service.create_budget(_payload())
    original_rollback = db.rollback
    rolled_back = False

    def fail_commit():
        raise RuntimeError("commit failed")

    def track_rollback():
        nonlocal rolled_back
        rolled_back = True
        original_rollback()

    monkeypatch.setattr(db, "commit", fail_commit)
    monkeypatch.setattr(db, "rollback", track_rollback)
    with pytest.raises(RuntimeError, match="commit failed"):
        service.activate_budget(budget["id"])
    assert rolled_back is True


def test_budget_routes_use_edit_for_activation_and_close():
    route = __import__("pathlib").Path("backend/routes/finance.py").read_text(encoding="utf-8")
    assert 'path.endswith(("/activate", "/settle", "/close", "/reopen"))' in route
    assert '@router.post("/budgets/{budget_id}/activate"' in route
    assert '@router.post("/budgets/{budget_id}/close"' in route

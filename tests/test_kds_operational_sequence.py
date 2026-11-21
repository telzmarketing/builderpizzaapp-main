"""Behavioral SQLite coverage for the operational KDS sequence.

SQLite validates the service contract and tenant/station predicates; PostgreSQL
is still required to prove concurrent row-lock behavior.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.main import app  # register the existing model relationships
from backend.database import Base
from backend.core.exceptions import DomainError
from backend.core.tenant_context import TenantContext, TenantSource
from backend.models.tenant import Tenant
from backend.models.order import Order, OrderItem
from backend.models.kds_production import (
    KdsAssignment,
    KdsOperatorState,
    ProductionAttempt,
    ProductionAttemptConsumption,
    ProductionUnit,
)
from backend.models.rbac import AdminAuditLog
from backend.models.product import Product
from backend.models.cmv import OrderItemCmvSnapshot
from backend.models.gestao import GestaoModuleSettings
from backend.services.kds_production_service import KdsProductionService


@pytest.fixture
def kds():
    engine = create_engine("sqlite://")
    models = [Tenant, Product, Order, OrderItem, AdminAuditLog, ProductionUnit,
              ProductionAttempt, ProductionAttemptConsumption, OrderItemCmvSnapshot,
              GestaoModuleSettings, KdsOperatorState, KdsAssignment]
    Base.metadata.create_all(engine, tables=[model.__table__ for model in models])
    with Session(engine, autoflush=False) as db:
        db.add(Tenant(id="tenant", slug="kds-sequence", name="KDS sequence"))
        # SQLite does not apply the PostgreSQL partial legacy-tenant index.
        db.add(Tenant(id="other", slug="other-kds", name="Other KDS", is_legacy=True))
        db.add(Product(id="pizza-product", tenant_id="tenant", name="Pizza",
                       description="Pizza", price=10, product_type="pizza"))
        for suffix, station in (("pizza", "pizza-1"), ("esfiha", "esfiha"),
                                ("legacy", "pizza")):
            order_id = f"order-{suffix}"
            item_id = f"item-{suffix}"
            unit_id = f"unit-{suffix}"
            task_id = f"task-{suffix}"
            db.add(Order(id=order_id, tenant_id="tenant", status="preparing",
                         subtotal=10, total=10, fulfillment_type="pickup"))
            db.add(OrderItem(id=item_id, tenant_id="tenant", order_id=order_id,
                             product_id="pizza-product", quantity=1, unit_price=10,
                             total_price=10))
            db.add(ProductionUnit(id=unit_id, tenant_id="tenant", order_id=order_id,
                                  order_item_id=item_id, unit_index=1,
                                  station_id=station, state="queued", requires_oven=True))
            db.add(ProductionAttempt(id=task_id, tenant_id="tenant",
                                     production_unit_id=unit_id, attempt_number=1,
                                     state="queued"))
        db.commit()
        service = KdsProductionService(db, TenantContext("tenant", TenantSource.JOB))
        clock = [datetime(2026, 11, 20, 12, tzinfo=timezone.utc)]
        service._now = lambda: clock[0]
        yield SimpleNamespace(db=db, service=service, clock=clock)
    engine.dispose()


def body(version, station="pizza-1", *, approved=True, reason=None):
    return SimpleNamespace(expected_version=version, station_id=station,
                           approved=approved, reason=reason)


def test_operational_sequence_does_not_skip_and_audits_transitions(kds):
    service = kds.service
    with pytest.raises(DomainError, match="incompativel"):
        service.command("task-pizza", "cook", body(1), "finish-assembly")

    started = service.command("task-pizza", "cook", body(1), "start")
    kds.clock[0] += timedelta(seconds=5)
    assembling = service.command("task-pizza", "cook", body(started["version"]), "confirm-stock")
    assembled = service.command("task-pizza", "cook", body(assembling["version"]), "finish-assembly")
    baking = service.command("task-pizza", "cook", body(assembled["version"]), "start-oven")
    checking = service.command("task-pizza", "cook", body(baking["version"]), "complete-oven")
    ready = service.command("task-pizza", "cook", body(checking["version"]), "check")

    assert [assembling["state"], assembled["state"], baking["state"],
            checking["state"], ready["state"]] == [
                "assembling", "assembled", "baking", "checking", "ready"
            ]
    assert kds.db.query(AdminAuditLog).filter_by(entity_id="task-pizza").count() >= 6


def test_persisted_station_and_legacy_station_scope_are_preserved(kds):
    service = kds.service
    result = service.command("task-pizza", "cook", body(1, "pizza-1"), "start")
    assert result["station_id"] == "pizza-1"
    legacy = service.command("task-legacy", "legacy-cook", body(1, "pizza-1"), "start")
    assert legacy["station_id"] == "pizza"
    with pytest.raises(DomainError, match="outra estacao"):
        service.command("task-esfiha", "cook", body(1, "pizza-1"), "start")


def test_presence_conflict_applies_to_stock_commands(kds):
    service = kds.service
    service.presence("cook", SimpleNamespace(station_id="pizza-1",
                                              effective_state="available",
                                              expected_version=0))
    with pytest.raises(DomainError, match="outra estacao"):
        service.command("task-esfiha", "cook", body(1, "esfiha"), "start")


def test_tenant_isolation_applies_before_operational_changes(kds):
    foreign = KdsProductionService(kds.db, TenantContext("other", TenantSource.JOB))
    with pytest.raises(DomainError, match="nao encontrada"):
        foreign.command("task-pizza", "cook", body(1), "start")


def test_remake_priority_is_after_started_work_and_before_normal_queue(kds):
    service = kds.service
    old = kds.db.get(ProductionAttempt, "task-pizza")
    old.state = old.unit.state = "ready"
    old.started_at = kds.clock[0]
    old.operator_id = "cook"
    kds.db.commit()
    remake = service.remake("task-pizza", "cook", body(old.version, reason="reprovada"))

    # Already accepted work must remain ahead of the new urgent queued task.
    active = kds.db.get(ProductionAttempt, "task-legacy")
    active.state = active.unit.state = "assembling"
    active.started_at = kds.clock[0]
    active.operator_id = "cook"
    kds.db.add(ProductionUnit(id="unit-normal", tenant_id="tenant", order_id="order-pizza",
                              order_item_id="item-pizza", unit_index=2,
                              station_id="pizza-1", state="queued", requires_oven=True))
    kds.db.add(ProductionAttempt(id="task-normal", tenant_id="tenant",
                                 production_unit_id="unit-normal", attempt_number=1,
                                 state="queued", created_at=kds.clock[0] - timedelta(days=1)))
    kds.db.commit()

    queue = service.all_queued("pizza-1")
    assert remake["attempt_number"] == 2
    assert kds.db.get(ProductionAttempt, remake["task_id"]).priority == 1
    assert [row["task_id"] for row in queue] == ["task-legacy", remake["task_id"], "task-normal"]
    assert queue[1]["priority"] == 1
    assert [row["task_id"] for row in service.queue("cook", "pizza-1")] == [row["task_id"] for row in queue]


def test_remake_rejects_unstarted_cancelled_and_duplicate_tentative(kds):
    service = kds.service
    with pytest.raises(DomainError, match="iniciadas"):
        service.remake("task-pizza", "cook", body(1, reason="cedeu"))

    task = kds.db.get(ProductionAttempt, "task-pizza")
    task.state = task.unit.state = "cancelled"
    task.started_at = kds.clock[0]
    task.operator_id = "cook"
    kds.db.commit()
    with pytest.raises(DomainError, match="cancelada"):
        service.remake("task-pizza", "cook", body(task.version, reason="nao"))

    task.state = task.unit.state = "ready"
    task.version += 1
    kds.db.add(ProductionAttempt(id="tentative", tenant_id="tenant",
                                 production_unit_id=task.production_unit_id,
                                 attempt_number=2, state="queued"))
    kds.db.commit()
    with pytest.raises(DomainError, match="tentativa"):
        service.remake("task-pizza", "cook", body(task.version, reason="duplicada"))


def test_confirm_stock_processes_requests_in_fifo_order(kds):
    service = kds.service
    first = service.command("task-pizza", "cook1", body(1), "start")
    kds.clock[0] += timedelta(milliseconds=1)
    second = service.command("task-legacy", "cook2", body(1), "start")
    kds.clock[0] += timedelta(seconds=5)
    service.command("task-legacy", "cook2", body(second["version"]), "confirm-stock")
    assert kds.db.get(ProductionAttempt, "task-pizza").state == "assembling"
    assert kds.db.get(ProductionAttempt, "task-legacy").state == "assembling"

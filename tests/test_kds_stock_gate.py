"""Behavioral stock-gate regressions; SQLite does not prove PostgreSQL locking."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session

from backend.main import app  # register model relationships without startup
from backend.database import Base
from backend.core.exceptions import DomainError
from backend.core.tenant_context import TenantContext, TenantSource
from backend.models.tenant import Tenant
from backend.models.order import Order, OrderItem, OrderItemFlavor
from backend.models.rbac import AdminAuditLog
from backend.models.kds_production import ProductionUnit, ProductionAttempt, ProductionAttemptConsumption
from backend.models.cmv import OrderItemCmvSnapshot, OrderItemCmvIngredientSnapshot
from backend.models.inventory import InventoryItem, InventoryStockMovement
from backend.models.inventory_foundation import InventoryOperation, InventoryLot, InventoryReservation
from backend.models.delivery import Delivery, DeliveryPerson
from backend.models.product import Product
from backend.services.kds_production_service import KdsProductionService
from backend.services.inventory_service import InventoryService
from backend.services.order_service import OrderService
from backend.services.delivery_service import DeliveryService


@pytest.fixture
def gate():
    engine = create_engine("sqlite://")
    models = [Tenant, Order, OrderItem, OrderItemFlavor, AdminAuditLog, ProductionUnit, ProductionAttempt,
              ProductionAttemptConsumption, OrderItemCmvSnapshot, OrderItemCmvIngredientSnapshot,
              InventoryItem, InventoryStockMovement, InventoryOperation, InventoryLot, InventoryReservation,
              Delivery, DeliveryPerson, Product]
    Base.metadata.create_all(engine, tables=[m.__table__ for m in models])
    with Session(engine, autoflush=False) as db:
        db.add(Tenant(id="tenant", slug="stock-test", name="Stock gate test"))
        db.add(InventoryItem(id="cheese", tenant_id="tenant", name="Cheese"))
        db.add(InventoryStockMovement(id="opening", tenant_id="tenant", item_id="cheese",
            location_id="kitchen", quantity_delta=1, source_type="manual_entry"))
        for number in (1, 2):
            oid, iid, uid, aid = (f"order{number}", f"item{number}", f"unit{number}", f"task{number}")
            db.add(Order(id=oid, tenant_id="tenant", status="preparing", subtotal=50, total=50,
                         fulfillment_type="delivery"))
            db.add(ProductionUnit(id=uid, tenant_id="tenant", order_id=oid, order_item_id=iid,
                unit_index=1, state="queued", requires_oven=True))
            db.add(ProductionAttempt(id=aid, tenant_id="tenant", production_unit_id=uid,
                attempt_number=1, state="queued"))
            db.add(OrderItemCmvSnapshot(id=f"snapshot{number}", tenant_id="tenant", snapshot_id="root",
                order_item_id=iid, product_name="Pizza", quantity=1))
            db.add(OrderItemCmvIngredientSnapshot(id=f"ingredient{number}", tenant_id="tenant",
                item_snapshot_id=f"snapshot{number}", inventory_item_id="cheese",
                inventory_item_name="Cheese", quantity=1, unit_cost=5))
        db.commit()
        context = TenantContext("tenant", TenantSource.JOB)
        service = KdsProductionService(db, context)
        clock = [datetime(2026, 10, 26, 12, tzinfo=timezone.utc)]
        service._now = lambda: clock[0]
        yield SimpleNamespace(db=db, service=service, clock=clock, context=context)
    engine.dispose()


def command(version):
    return SimpleNamespace(expected_version=version, reason=None, approved=True)


def balance(gate):
    return gate.db.query(func.sum(InventoryStockMovement.quantity_delta)).scalar()


def test_kitchen_queue_excludes_archived_cancelled_and_outdated_orders_but_keeps_active_rework(gate):
    now = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
    cases = [
        ("archived", "preparing", now, now, "old-archived"),
        ("cancelled", "cancelled", now, None, "old-cancelled"),
        ("finished", "ready_for_pickup", now, None, "old-finished"),
        ("active", "preparing", now, None, "active-current"),
    ]
    for index, (suffix, status, created_at, archived_at, item_id) in enumerate(cases, start=10):
        order_id = f"queue-{suffix}"
        unit_id = f"queue-unit-{suffix}"
        gate.db.add(Order(
            id=order_id, tenant_id="tenant", status=status, subtotal=50, total=50,
            fulfillment_type="delivery", created_at=created_at, archived_at=archived_at,
        ))
        gate.db.add(ProductionUnit(
            id=unit_id, tenant_id="tenant", order_id=order_id, order_item_id=item_id,
            unit_index=1, state="queued",
        ))
        gate.db.add(ProductionAttempt(
            id=f"queue-attempt-{suffix}", tenant_id="tenant",
            production_unit_id=unit_id, attempt_number=1, state="queued",
        ))

    # The cancelled first attempt remains valid history; only the queued
    # rework attempt may be returned for the active unit.
    gate.db.add(Order(
        id="queue-rework", tenant_id="tenant", status="preparing",
        subtotal=50, total=50, fulfillment_type="delivery",
    ))
    gate.db.add(ProductionUnit(
        id="queue-unit-rework", tenant_id="tenant", order_id="queue-rework",
        order_item_id="rework-item", unit_index=1, state="queued",
    ))
    gate.db.add_all([
        ProductionAttempt(
            id="queue-attempt-rework-old", tenant_id="tenant",
            production_unit_id="queue-unit-rework", attempt_number=1, state="cancelled",
        ),
        ProductionAttempt(
            id="queue-attempt-rework-current", tenant_id="tenant",
            production_unit_id="queue-unit-rework", attempt_number=2, state="queued",
        ),
    ])
    gate.db.commit()

    queued = gate.service.all_queued()
    queued_ids = {row["order_id"] for row in queued}
    assert "queue-active" in queued_ids
    assert "queue-rework" in queued_ids
    assert not {"queue-archived", "queue-cancelled", "queue-finished"} & queued_ids
    assert [row["id"] for row in queued if row["order_id"] == "queue-rework"] == [
        "queue-attempt-rework-current"
    ]

    mine = gate.service.queue("cook")
    mine_ids = {row["order_id"] for row in mine}
    assert {"queue-active", "queue-rework"} <= mine_ids
    assert not {"queue-archived", "queue-cancelled", "queue-finished"} & mine_ids


def test_start_persists_five_second_deadline_without_debit_and_replays(gate):
    task = gate.service.command("task1", "cook", command(1), "start")
    assert task["state"] == "checking_stock" and task["started_at"] is None
    assert task["stock_check_after"] - task["stock_requested_at"] == timedelta(seconds=5)
    assert balance(gate) == Decimal("1")
    replay = gate.service.command("task1", "cook", command(1), "start")
    assert replay["version"] == task["version"]
    with pytest.raises(DomainError, match="cinco segundos"):
        gate.service.command("task1", "cook", command(task["version"]), "confirm-stock")
    assert balance(gate) == Decimal("1")


def test_later_confirmation_cannot_overtake_first_request_and_loser_returns(gate):
    first = gate.service.command("task1", "cook1", command(1), "start")
    gate.clock[0] += timedelta(milliseconds=1)
    later = gate.service.command("task2", "cook2", command(1), "start")
    gate.clock[0] += timedelta(seconds=6)
    result = gate.service.command("task2", "cook2", command(later["version"]), "confirm-stock")
    assert gate.db.get(ProductionAttempt, "task1").state == "assembling"
    assert result["state"] == "aguardando_analise" and result["blocked_reason"]
    assert balance(gate) == Decimal("0")
    assert gate.db.query(ProductionAttemptConsumption).count() == 1
    assert gate.db.query(InventoryOperation).count() == 1
    returned = gate.service.command("task2", "cook2", command(result["version"]), "return-to-service")
    assert returned["state"] == "atendimento"
    assert gate.service.stock_alerts()[0]["order_id"] == "order2"
    assert gate.db.query(AdminAuditLog).count() == 5
    replay = gate.service.command("task1", "cook1", command(first["version"]), "confirm-stock")
    assert replay["state"] == "assembling" and balance(gate) == 0


def test_failed_second_ingredient_rolls_back_all_attempt_movements(gate):
    gate.db.add(InventoryItem(id="sauce", tenant_id="tenant", name="Sauce"))
    gate.db.add(OrderItemCmvIngredientSnapshot(id="extra", tenant_id="tenant",
        item_snapshot_id="snapshot1", inventory_item_id="sauce", inventory_item_name="Sauce", quantity=1))
    gate.db.commit()
    task = gate.service.command("task1", "cook", command(1), "start")
    gate.clock[0] += timedelta(seconds=5)
    result = gate.service.command("task1", "cook", command(task["version"]), "confirm-stock")
    assert result["state"] == "aguardando_analise"
    assert balance(gate) == Decimal("1")
    assert gate.db.query(InventoryOperation).count() == 0
    assert gate.db.query(ProductionAttemptConsumption).count() == 0


def test_legacy_coverage_does_not_consume_twice_and_unit_writer_blocks_legacy(gate):
    gate.db.add(InventoryStockMovement(id="old-sale", tenant_id="tenant", item_id="cheese",
        location_id="kitchen", source_type="order_sale", source_id="order1", quantity_delta=-1))
    gate.db.commit()
    task = gate.service.command("task1", "cook", command(1), "start")
    gate.clock[0] += timedelta(seconds=5)
    result = gate.service.command("task1", "cook", command(task["version"]), "confirm-stock")
    assert result["state"] == "assembling" and result["consumption_mode"] == "legacy_covered"
    assert balance(gate) == 0 and gate.db.query(InventoryOperation).count() == 0
    inventory = InventoryService(gate.db, "tenant", gate.context)
    inventory.automatic_deduction_enabled = lambda: True
    assert inventory.consume_order_sale("order1")["reason"] == "kds_units"
    gate.service.command("task1", "cook", command(result["version"]), "finish-assembly")
    assert balance(gate) == 0


def test_other_operator_and_other_tenant_cannot_claim_and_pending_unit_blocks_release(gate):
    gate.service.command("task1", "cook", command(1), "start")
    with pytest.raises(DomainError, match="outro operador"):
        gate.service.command("task1", "other", command(1), "start")
    foreign = KdsProductionService(gate.db, TenantContext("other-tenant", TenantSource.JOB))
    with pytest.raises(DomainError, match="nao encontrada"):
        foreign._unit("task1")
    with pytest.raises(DomainError, match="unidades"):
        OrderService(gate.db, gate.context).change_status("order1", "ready_for_pickup")


@pytest.mark.parametrize("action", ["picked_up", "on_the_way", "driver_start"])
def test_delivery_paths_cannot_bypass_pending_production(gate, action):
    gate.db.add(DeliveryPerson(id="driver", tenant_id="tenant", name="Driver", phone="11999999999", status="busy"))
    gate.db.add(Delivery(id="delivery", tenant_id="tenant", order_id="order1", delivery_person_id="driver", status="assigned"))
    gate.db.commit()
    service = DeliveryService(gate.db, "tenant", gate.context)
    with pytest.raises(DomainError, match="unidades"):
        if action == "driver_start":
            service.start_driver_delivery("driver", "delivery")
        else:
            service.update_status("delivery", action)
    delivery = gate.db.get(Delivery, "delivery")
    assert delivery.status.value == "assigned" and delivery.picked_up_at is None
    assert gate.db.get(Order, "order1").status.value == "preparing"

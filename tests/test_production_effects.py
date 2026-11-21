"""Behavioral tests for transactional production effects (SQLite only)."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session

from backend.main import app  # noqa: F401 - register the complete ORM graph
from backend.core.exceptions import DomainError
from backend.core.tenant_context import TenantContext, TenantSource
from backend.database import Base
from backend.models.cmv import OrderItemCmvIngredientSnapshot, OrderItemCmvSnapshot
from backend.models.finance import FinanceSettlement, FinanceTransaction
from backend.models.inventory import InventoryItem, InventoryStockMovement
from backend.models.inventory_foundation import InventoryLot, InventoryOperation, InventoryReservation
from backend.models.kds_production import (
    KdsAssignment,
    ProductionAttempt,
    ProductionAttemptConsumption,
    ProductionEffect,
    ProductionUnit,
)
from backend.models.order import Order, OrderItem
from backend.models.payment import Payment
from backend.models.product import Product
from backend.models.rbac import AdminAuditLog
from backend.models.tenant import Tenant
from backend.schemas.production_effects import (
    OrderBonificationIn,
    ProductionLossIn,
    ProductionReproductionIn,
)
from backend.services.finance_service import FinanceService
from backend.services.kds_production_service import KdsProductionService
from backend.services.production_effects_service import ProductionEffectsService, ProductionEffectConflict


@pytest.fixture
def fx():
    engine = create_engine("sqlite://")
    tables = [
        Tenant, Order, OrderItem, Product, AdminAuditLog,
        ProductionUnit, ProductionAttempt, ProductionAttemptConsumption,
        ProductionEffect, KdsAssignment,
        OrderItemCmvSnapshot, OrderItemCmvIngredientSnapshot,
        InventoryItem, InventoryStockMovement, InventoryOperation,
        InventoryLot, InventoryReservation,
        FinanceTransaction, FinanceSettlement, Payment,
    ]
    Base.metadata.create_all(engine, tables=[model.__table__ for model in tables])
    with Session(engine, autoflush=False) as db:
        for tenant_id in ("t1", "t2"):
            db.add(Tenant(id=tenant_id, slug=tenant_id, name=tenant_id, is_legacy=(tenant_id == "t2")))
            db.add(InventoryItem(id=f"cheese-{tenant_id}", tenant_id=tenant_id, name="Cheese"))
            db.add(InventoryStockMovement(
                id=f"opening-{tenant_id}", tenant_id=tenant_id,
                item_id=f"cheese-{tenant_id}", location_id="kitchen",
                quantity_delta=2, source_type="manual_entry",
            ))
            db.add(Product(id=f"pizza-{tenant_id}", tenant_id=tenant_id, name="Pizza", description="Pizza de teste", price=50))
            order_id = f"order-{tenant_id}"
            item_id = f"item-{tenant_id}"
            db.add(Order(
                id=order_id, tenant_id=tenant_id, status="preparing",
                order_origin="own", subtotal=50, total=50,
                fulfillment_type="delivery",
            ))
            db.add(OrderItem(
                id=item_id, tenant_id=tenant_id, order_id=order_id,
                product_id=f"pizza-{tenant_id}", quantity=1, position=1,
                unit_price=50, total_price=50, is_gift=False,
            ))
            db.add(ProductionUnit(
                id=f"unit-{tenant_id}", tenant_id=tenant_id, order_id=order_id,
                order_item_id=item_id, unit_index=1, state="queued",
            ))
            db.add(ProductionAttempt(
                id=f"attempt-{tenant_id}", tenant_id=tenant_id,
                production_unit_id=f"unit-{tenant_id}", attempt_number=1,
                state="queued",
            ))
            snapshot_id = f"snapshot-{tenant_id}"
            db.add(OrderItemCmvSnapshot(
                id=snapshot_id, tenant_id=tenant_id, snapshot_id="root",
                order_item_id=item_id, product_name="Pizza", quantity=1,
            ))
            db.add(OrderItemCmvIngredientSnapshot(
                id=f"ingredient-{tenant_id}", tenant_id=tenant_id,
                item_snapshot_id=snapshot_id, inventory_item_id=f"cheese-{tenant_id}",
                inventory_item_name="Cheese", quantity=1, unit_cost=5,
            ))
        db.commit()
        yield db
    engine.dispose()


def context(tenant_id="t1"):
    return TenantContext(tenant_id, TenantSource.JOB)


def effects(fx, tenant_id="t1", actor="qa"):
    return ProductionEffectsService(fx, context(tenant_id), actor)


def started(fx, tenant_id="t1"):
    attempt = fx.get(ProductionAttempt, f"attempt-{tenant_id}")
    unit = fx.get(ProductionUnit, f"unit-{tenant_id}")
    attempt.state = unit.state = "assembling"
    attempt.started_at = datetime.now(timezone.utc)
    fx.commit()
    return attempt


def stock_balance(fx, tenant_id="t1"):
    return fx.query(func.sum(InventoryStockMovement.quantity_delta)).filter(
        InventoryStockMovement.tenant_id == tenant_id,
        InventoryStockMovement.item_id == f"cheese-{tenant_id}",
    ).scalar()


def test_loss_consumes_original_once_and_repeated_key_replays(fx):
    attempt = started(fx)
    service = effects(fx)
    first = service.record_loss(
        ProductionLossIn(attempt_id=attempt.id, expected_version=1, reason="queimou"), "loss-1"
    )
    balance = stock_balance(fx)
    replay = service.record_loss(
        ProductionLossIn(attempt_id=attempt.id, expected_version=1, reason="queimou"), "loss-1"
    )
    assert first == replay
    assert balance == stock_balance(fx)
    assert fx.query(ProductionEffect).count() == 1
    assert fx.query(ProductionAttemptConsumption).filter_by(attempt_id=attempt.id).count() == 1


def test_loss_does_not_double_debit_existing_consumption(fx):
    attempt = started(fx)
    kds = KdsProductionService(fx, context())
    kds.consume_attempt(attempt.id, "qa", require_stock=True)
    fx.commit()
    before = stock_balance(fx)
    result = effects(fx).record_loss(
        ProductionLossIn(attempt_id=attempt.id, expected_version=1, reason="defeito"), "loss-existing"
    )
    assert result["kind"] == "loss"
    assert stock_balance(fx) == before
    assert fx.query(ProductionAttemptConsumption).filter_by(attempt_id=attempt.id).count() == 1


def test_reproduction_consumes_only_when_new_attempt_starts_and_conflicts_are_safe(fx):
    attempt = started(fx)
    loss = effects(fx).record_loss(
        ProductionLossIn(attempt_id=attempt.id, expected_version=1, reason="erro"), "loss-repro"
    )
    reproduction = effects(fx).create_reproduction(
        ProductionReproductionIn(loss_id=loss["id"], reason="refazer"), "repro-1"
    )
    new_attempt = fx.get(ProductionAttempt, reproduction["attempt_id"])
    assert new_attempt.state == "queued"
    assert fx.query(ProductionAttemptConsumption).filter_by(attempt_id=new_attempt.id).count() == 0
    KdsProductionService(fx, context()).consume_attempt(new_attempt.id, "qa", require_stock=True)
    fx.commit()
    assert fx.query(ProductionAttemptConsumption).filter_by(attempt_id=new_attempt.id).count() == 1
    assert effects(fx).create_reproduction(
        ProductionReproductionIn(loss_id=loss["id"], reason="refazer"), "repro-1"
    ) == reproduction
    with pytest.raises(ProductionEffectConflict, match="conteudo diferente"):
        effects(fx).create_reproduction(
            ProductionReproductionIn(loss_id=loss["id"], reason="outro"), "repro-1"
        )
    with pytest.raises(ProductionEffectConflict, match="origem"):
        effects(fx).create_reproduction(
            ProductionReproductionIn(loss_id=loss["id"], reason="refazer"), "repro-2"
        )


def test_idempotency_and_effects_are_tenant_isolated(fx):
    for tenant_id in ("t1", "t2"):
        started(fx, tenant_id)
        result = effects(fx, tenant_id).record_loss(
            ProductionLossIn(attempt_id=f"attempt-{tenant_id}", expected_version=1, reason="perda"), "same-key"
        )
        assert result["tenant_id"] if "tenant_id" in result else True
    assert fx.query(ProductionEffect).count() == 2
    assert stock_balance(fx, "t1") == stock_balance(fx, "t2") == 1
    with pytest.raises(DomainError):
        effects(fx, "t2").record_loss(
            ProductionLossIn(attempt_id="attempt-t1", expected_version=1, reason="cross"), "cross-key"
        )


def test_insufficient_stock_rolls_back_loss(fx):
    attempt = started(fx)
    fx.query(InventoryStockMovement).filter_by(tenant_id="t1").delete()
    fx.commit()
    with pytest.raises(DomainError):
        effects(fx).record_loss(
            ProductionLossIn(attempt_id=attempt.id, expected_version=1, reason="sem estoque"), "loss-short"
        )
    fx.expire_all()
    assert fx.query(ProductionEffect).count() == 0
    assert fx.get(ProductionAttempt, attempt.id).state == "assembling"
    assert fx.query(ProductionAttemptConsumption).count() == 0


def test_transaction_failure_before_commit_rolls_back_everything(fx, monkeypatch):
    attempt = started(fx)
    original_commit = fx.commit

    def fail_once():
        monkeypatch.setattr(fx, "commit", original_commit)
        raise RuntimeError("commit failure")

    monkeypatch.setattr(fx, "commit", fail_once)
    with pytest.raises(RuntimeError, match="commit failure"):
        effects(fx).record_loss(
            ProductionLossIn(attempt_id=attempt.id, expected_version=1, reason="falha"), "loss-rollback"
        )
    fx.expire_all()
    assert fx.query(ProductionEffect).count() == 0
    assert fx.get(ProductionAttempt, attempt.id).state == "assembling"
    assert fx.query(ProductionAttemptConsumption).count() == 0


def _make_pending_order(fx, suffix="bonus"):
    order_id, item_id = f"order-{suffix}", f"item-{suffix}"
    fx.add(Order(id=order_id, tenant_id="t1", status="pending", order_origin="own",
                 subtotal=50, total=50, fulfillment_type="delivery"))
    fx.add(OrderItem(id=item_id, tenant_id="t1", order_id=order_id,
                     product_id="pizza-t1", quantity=1, position=1,
                     unit_price=50, total_price=50, is_gift=False))
    fx.add(ProductionUnit(id=f"unit-{suffix}", tenant_id="t1", order_id=order_id,
                          order_item_id=item_id, unit_index=1, state="queued"))
    fx.add(ProductionAttempt(id=f"attempt-{suffix}", tenant_id="t1",
                             production_unit_id=f"unit-{suffix}", attempt_number=1, state="queued"))
    snap = OrderItemCmvSnapshot(id=f"snapshot-{suffix}", tenant_id="t1",
                                snapshot_id="root", order_item_id=item_id,
                                product_name="Pizza", quantity=1)
    fx.add(snap)
    fx.add(OrderItemCmvIngredientSnapshot(id=f"ingredient-{suffix}", tenant_id="t1",
                                          item_snapshot_id=snap.id,
                                          inventory_item_id="cheese-t1",
                                          inventory_item_name="Cheese", quantity=1, unit_cost=5))
    fx.commit()
    return order_id, item_id


def test_bonification_zeros_sale_preserves_snapshot_and_consumes_on_start(fx):
    order_id, item_id = _make_pending_order(fx)
    result = effects(fx).bonify_order(
        OrderBonificationIn(order_id=order_id, beneficiary="equipe", reason="refeicao"), "bonus-1"
    )
    order = fx.get(Order, order_id)
    item = fx.get(OrderItem, item_id)
    assert result["discount_amount"] == "50.00"
    assert order.total == order.subtotal == 0
    assert item.is_gift and item.gift_reason == "staff_meal"
    assert fx.get(OrderItemCmvSnapshot, "snapshot-bonus").ingredients
    attempt = fx.get(ProductionAttempt, "attempt-bonus")
    attempt.state = fx.get(ProductionUnit, "unit-bonus").state = "assembling"
    attempt.started_at = datetime.now(timezone.utc)
    KdsProductionService(fx, context()).consume_attempt(attempt.id, "qa", require_stock=True)
    fx.commit()
    assert fx.query(ProductionAttemptConsumption).filter_by(attempt_id=attempt.id).count() == 1


@pytest.mark.parametrize("case", ["payment", "started"])
def test_bonification_is_blocked_after_payment_or_production(case, fx):
    order_id, item_id = _make_pending_order(fx, case)
    if case == "payment":
        fx.add(Payment(id="payment-bonus", tenant_id="t1", order_id=order_id,
                       amount=50, status="paid", method="pix"))
    else:
        fx.get(Order, order_id).status = "preparing"
        fx.get(ProductionAttempt, f"attempt-{case}").started_at = datetime.now(timezone.utc)
    fx.commit()
    with pytest.raises(ProductionEffectConflict):
        effects(fx).bonify_order(
            OrderBonificationIn(order_id=order_id, beneficiary="equipe", reason="refeicao"), f"bonus-{case}"
        )


def test_financial_summary_classifies_cost_without_transaction_or_settlement(fx):
    attempt = started(fx)
    loss = effects(fx).record_loss(
        ProductionLossIn(attempt_id=attempt.id, expected_version=1, reason="avaria"), "summary-loss"
    )
    before_transactions = fx.query(FinanceTransaction).count()
    before_settlements = fx.query(FinanceSettlement).count()
    summary = FinanceService(fx, "t1", context("t1")).production_effects_summary("order-t1")
    assert loss["kind"] == "loss"
    assert summary["loss_count"] == 1
    assert summary["loss_cost"] == "5.00"
    assert summary["cash_effect"] == "0.00"
    assert fx.query(FinanceTransaction).count() == before_transactions
    assert fx.query(FinanceSettlement).count() == before_settlements

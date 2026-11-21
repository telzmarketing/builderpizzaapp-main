"""Persistence and rollback tests; SQLite does not prove PostgreSQL row locks."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import event, func

from test_kds_stock_gate import gate
from backend.database import Base
from backend.core.exceptions import DomainError
from backend.core.tenant_context import TenantContext, TenantSource
from backend.models.finance import FinanceSettlement, FinanceTransaction
from backend.models.inventory import InventoryStockMovement
from backend.models.kds_production import KdsAssignment, ProductionAttempt, ProductionAttemptConsumption, ProductionEffect
from backend.models.order import Order, OrderItem
from backend.models.payment import Payment
from backend.models.rbac import AdminAuditLog
from backend.models.tenant import Tenant
from backend.schemas.production_effects import OrderBonificationIn, ProductionLossIn, ProductionReproductionIn
from backend.services.finance_service import FinanceService
from backend.services.production_effects_service import ProductionEffectsService


@pytest.fixture
def effects(gate):
    Base.metadata.create_all(gate.db.get_bind(), tables=[model.__table__ for model in (
        ProductionEffect, KdsAssignment, Payment, FinanceTransaction, FinanceSettlement,
    )])
    gate.db.add(OrderItem(id="item1", tenant_id="tenant", order_id="order1", product_id="pizza",
        quantity=1, unit_price=50, total_price=50))
    gate.db.get(InventoryStockMovement, "opening").quantity_delta = 10
    gate.db.commit()
    yield SimpleNamespace(**vars(gate), effects=ProductionEffectsService(gate.db, gate.context, "cook"))


def balance(effects):
    return effects.db.query(func.sum(InventoryStockMovement.quantity_delta)).scalar()


def loss(effects, key="loss"):
    attempt = effects.db.get(ProductionAttempt, "task1")
    attempt.state = attempt.unit.state = "assembling"
    attempt.started_at = datetime.now(timezone.utc)
    effects.db.commit()
    return effects.effects.record_loss(ProductionLossIn(
        attempt_id="task1", expected_version=1, reason="Pizza queimada",
    ), key)


def test_loss_replay_reproduction_and_non_cash_finance(effects):
    original = loss(effects)
    assert balance(effects) == 9
    replay = effects.effects.record_loss(ProductionLossIn(
        attempt_id="task1", expected_version=1, reason="Pizza queimada",
    ), "loss")
    assert replay == original
    remake_body = ProductionReproductionIn(loss_id=original["id"], reason="Refazer para cliente")
    remake = effects.effects.create_reproduction(remake_body, "remake")
    assert effects.effects.create_reproduction(remake_body, "remake") == remake
    assert balance(effects) == 9
    effects.service.consume_attempt(remake["attempt_id"], "cook", require_stock=True)
    effects.db.commit()
    effects.service.consume_attempt(remake["attempt_id"], "cook", require_stock=True)
    effects.db.commit()
    assert balance(effects) == 8
    assert effects.db.query(ProductionAttemptConsumption).count() == 2
    assert effects.db.query(ProductionEffect).count() == 2
    assert effects.db.query(AdminAuditLog).count() == 2
    summary = FinanceService(effects.db, "tenant", effects.context).production_effects_summary("order1")
    assert summary["loss_cost"] == summary["reproduction_cost"] == "5.00"
    assert summary["physical_cost"] == "10.00" and summary["incremental_cost"] == "5.00"
    assert summary["cash_effect"] == "0.00"
    assert effects.db.query(FinanceTransaction).count() == effects.db.query(FinanceSettlement).count() == 0


@pytest.mark.parametrize("same_key", [False, True])
def test_duplicate_business_or_changed_payload_cannot_duplicate_loss(effects, same_key):
    loss(effects)
    with pytest.raises(DomainError) as failure:
        effects.effects.record_loss(ProductionLossIn(
            attempt_id="task1", expected_version=1, reason="Outro motivo" if same_key else "Pizza queimada",
        ), "loss" if same_key else "other-key")
    assert failure.value.code == ("IdempotencyConflict" if same_key else "BusinessIdentityConflict")
    assert balance(effects) == 9 and effects.db.query(ProductionEffect).count() == 1


def test_loss_requires_started_production(effects):
    with pytest.raises(DomainError) as failure:
        effects.effects.record_loss(ProductionLossIn(attempt_id="task1", expected_version=1, reason="Troca"), "loss")
    assert failure.value.code == "ProductionNotStarted"
    assert balance(effects) == 10 and effects.db.query(ProductionEffect).count() == 0


def test_shortage_rolls_back_loss_and_can_retry_same_key(effects):
    effects.db.get(InventoryStockMovement, "opening").quantity_delta = 0
    effects.db.commit()
    with pytest.raises(DomainError):
        loss(effects)
    assert effects.db.query(ProductionEffect).count() == effects.db.query(ProductionAttemptConsumption).count() == 0
    assert effects.db.get(ProductionAttempt, "task1").state == "assembling"
    effects.db.get(InventoryStockMovement, "opening").quantity_delta = 10
    effects.db.commit()
    loss(effects)
    assert balance(effects) == 9


def test_audit_failure_rolls_back_physical_debit_and_effect(effects):
    def reject_audit(session, context, instances):
        if any(isinstance(row, AdminAuditLog) for row in session.new):
            raise RuntimeError("injected audit failure")
    event.listen(effects.db, "before_flush", reject_audit)
    try:
        with pytest.raises(RuntimeError, match="injected audit failure"):
            loss(effects)
    finally:
        event.remove(effects.db, "before_flush", reject_audit)
    assert balance(effects) == 10
    assert effects.db.query(ProductionEffect).count() == effects.db.query(ProductionAttemptConsumption).count() == 0
    loss(effects)
    assert balance(effects) == 9


def test_bonification_zeros_sale_but_consumes_once_when_produced(effects):
    order = effects.db.get(Order, "order1")
    order.status = "pending"
    effects.db.commit()
    body = OrderBonificationIn(order_id=order.id, reason="Janta", beneficiary="Equipe de trabalho")
    bonus = effects.effects.bonify_order(body, "bonus")
    assert effects.effects.bonify_order(body, "bonus") == bonus
    assert effects.db.get(Order, "order1").total == 0
    item = effects.db.get(OrderItem, "item1")
    assert item.is_gift and item.gift_reason == "staff_meal" and item.unit_price == item.total_price == 0
    assert balance(effects) == 10
    # Staff meals retain consumption even with the automatic gate switched off.
    from backend.models.gestao import GestaoModuleSettings
    effects.db.get(GestaoModuleSettings, "inventory-settings").settings_json = '{}'
    effects.db.commit()
    effects.service.consume_attempt("task1", "cook")
    effects.db.commit()
    effects.service.consume_attempt("task1", "cook")
    effects.db.commit()
    assert balance(effects) == 9
    summary = FinanceService(effects.db, "tenant", effects.context).production_effects_summary("order1")
    assert summary["bonification_cost"] == "5.00" and summary["waived_sale"] == "50.00"
    assert effects.db.query(FinanceTransaction).count() == effects.db.query(FinanceSettlement).count() == 0


@pytest.mark.parametrize("blocker", ["payment", "production"])
def test_bonification_rejects_existing_payment_or_started_production(effects, blocker):
    effects.db.get(Order, "order1").status = "pending"
    if blocker == "payment":
            effects.db.add(Payment(id="payment", tenant_id="tenant", order_id="order1", method="cash", amount=50, status="approved", provider_payment_id="gateway-payment"))
    else:
        effects.db.get(ProductionAttempt, "task1").started_at = datetime.now(timezone.utc)
    effects.db.commit()
    with pytest.raises(DomainError):
        effects.effects.bonify_order(OrderBonificationIn(order_id="order1", reason="Janta", beneficiary="Equipe"), "bonus")
    assert effects.db.get(Order, "order1").total == 50
    assert effects.db.query(ProductionEffect).count() == 0


def test_tenant_cannot_register_effect_for_another_order(effects):
    effects.db.add(Tenant(id="other", name="Other", slug="other", is_legacy=True))
    effects.db.commit()
    service = ProductionEffectsService(effects.db, TenantContext("other", TenantSource.JOB), "cook")
    with pytest.raises(DomainError):
        service.record_loss(ProductionLossIn(attempt_id="task1", expected_version=1, reason="Perda"), "loss")
    assert effects.db.query(ProductionEffect).count() == 0 and balance(effects) == 10

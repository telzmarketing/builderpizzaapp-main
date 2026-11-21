"""Focused acceptance test for a full post-production composition change."""

from datetime import datetime, timezone
from types import SimpleNamespace

from backend.core.tenant_context import TenantContext, TenantSource
from backend.core.rbac_authorization import AuthorizedTenantActor
from backend.database import Base
from backend.models.idempotency import IdempotencyKey
from backend.models.kds_production import (
    KdsAssignment, ProductionAttempt, ProductionAttemptConsumption, ProductionEffect, ProductionUnit,
)
from backend.models.order import Order, OrderAmendment, OrderItem
from backend.models.product import Product, MultiFlavorsConfig
from backend.models.payment import Payment
from backend.models.finance import FinanceTransaction
from backend.models.delivery import Delivery
from backend.models.inventory import InventoryStockMovement
from backend.models.inventory_foundation import InventoryReservation
from backend.schemas.order import OrderAmendmentIn
from backend.services.order_service import OrderService
from test_kds_stock_gate import gate  # noqa: F401 - shared isolated stock fixture


def test_post_production_amendment_accepts_any_composition_and_requeues_priority(gate, monkeypatch):
    """The old line is retained as loss; a different line/quantity is queued."""
    db = gate.db
    Base.metadata.create_all(db.get_bind(), tables=[
        IdempotencyKey.__table__, OrderAmendment.__table__, ProductionEffect.__table__,
        KdsAssignment.__table__,
        ProductionAttemptConsumption.__table__, Payment.__table__, FinanceTransaction.__table__,
        Delivery.__table__, InventoryStockMovement.__table__, InventoryReservation.__table__,
        MultiFlavorsConfig.__table__,
    ])
    db.add_all([
        Product(id="pizza", tenant_id="tenant", name="Original", description="Original", price=50, product_type="pizza"),
        Product(id="replacement", tenant_id="tenant", name="Replacement", description="Replacement", price=70, product_type="pizza"),
    ])
    old = OrderItem(id="item1", tenant_id="tenant", order_id="order1", product_id="pizza",
                    quantity=1, position=0, selected_size="Grande", flavor_division=1,
                    unit_price=50, total_price=50)
    db.add(old)
    db.add(Payment(id="payment1", tenant_id="tenant", order_id="order1",
                   method="pix", status="pending", amount=50,
                   gateway="mercado_pago", provider="mercado_pago"))
    attempt = db.get(ProductionAttempt, "task1")
    unit = db.get(ProductionUnit, "unit1")
    attempt.state = unit.state = "assembling"
    attempt.started_at = datetime.now(timezone.utc)
    db.commit()

    def consume(self, attempt_id, actor_id, *, require_stock=False):
        row = self._unit(attempt_id, True)
        self.db.add(ProductionAttemptConsumption(
            id="consumed-original", tenant_id="tenant", attempt_id=attempt_id,
            inventory_item_id="cheese", quantity=1, unit_cost=5,
            movement_ids=["opening"], operation_id="loss-operation",
        ))
        row.stock_consumption_mode = "attempts"
        self.db.flush()
        return {"consumed": True, "mode": "attempts", "lines": 1}

    monkeypatch.setattr("backend.services.kds_production_service.KdsProductionService.consume_attempt", consume)
    context = TenantContext("tenant", TenantSource.JOB)
    actor = AuthorizedTenantActor("tenant", "cook", "Cook", context)
    service = OrderService(db, context)
    # CMV snapshot creation has its own integration suite; this acceptance
    # test isolates the amendment/loss/requeue contract.
    monkeypatch.setattr(service, "_ensure_amendment_cmv_snapshots", lambda _order: None)
    replacement = db.query(Product).filter_by(id="replacement", tenant_id="tenant").one()
    service._validate_item = lambda item, config, channel: (
        70.0, [replacement], SimpleNamespace(
            free_shipping=False, gift_enabled=False, standard_price=70.0,
            final_price=70.0, promotion_id=None, promotion_name=None,
            discount_amount=0.0, promotion_blocked=False, promotion_block_reason=None,
        ), None, None,
    )
    body = OrderAmendmentIn.model_validate({
        "expected_revision": 0, "expected_total": 140, "reason": "Cliente trocou a pizza e pediu duas",
        "items": [{
            "product_id": "replacement", "quantity": 2, "selected_size": "Grande",
            "flavors": [{"product_id": "replacement", "name": "Replacement", "price": 70, "icon": ""}],
            "final_price": 70,
        }],
    })
    history = service.amend_order("order1", body, actor=actor, idempotency_key="post-change-1")

    db.expire_all()
    live = db.query(OrderItem).filter(OrderItem.order_id == "order1", OrderItem.superseded_at.is_(None)).all()
    old_row = db.get(OrderItem, "item1")
    order_units = db.query(ProductionUnit).filter_by(order_id="order1").all()
    queued = [a for a in db.query(ProductionAttempt).join(ProductionUnit).filter(ProductionUnit.order_id == "order1").all()
              if a.state == "queued" and a.priority == 1]
    assert history.after_snapshot["financial_adjustment"]["action"] == "charge"
    assert db.query(FinanceTransaction).filter_by(
        order_id="order1", origin_type="order_amendment_adjustment", status="pending",
    ).count() == 1
    adjustment = db.query(FinanceTransaction).filter_by(
        order_id="order1", origin_type="order_amendment_adjustment",
    ).one()
    assert adjustment.entry_type == "income" and adjustment.amount == 90
    assert adjustment.status == "pending"
    assert old_row.superseded_at is not None
    assert len(live) == 1 and live[0].product_id == "replacement" and live[0].quantity == 2
    assert attempt.state == "cancelled"
    assert len(queued) == 2
    assert db.query(ProductionEffect).filter_by(kind="loss", order_id="order1").count() == 1
    assert db.query(ProductionEffect).filter_by(kind="reproduction", order_id="order1").count() == 2
    assert len(order_units) >= 3

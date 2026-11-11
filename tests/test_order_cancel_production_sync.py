from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.main import app  # noqa: F401 - register the project's model graph
from backend.database import Base
from backend.core.tenant_context import TenantContext, TenantSource
from backend.models.inventory import InventoryItem
from backend.models.admin import AdminUser
from backend.models.order import Order, OrderItem
from backend.models.product import Product
from backend.models.rbac import AdminAuditLog
from backend.models.tenant import Tenant
from backend.models.kds_production import (
    ProductionAttempt,
    ProductionAttemptConsumption,
    ProductionUnit,
)
from backend.services.kds_production_service import KdsProductionService
from backend.services.order_service import OrderService


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    tables = [
        Tenant, AdminUser, Product, Order, OrderItem, InventoryItem, AdminAuditLog,
        ProductionUnit, ProductionAttempt, ProductionAttemptConsumption,
    ]
    Base.metadata.create_all(engine, tables=[model.__table__ for model in tables])
    with Session(engine) as session:
        session.add(Tenant(id="tenant", slug="cancel-sync", name="Cancel sync"))
        session.add(Product(
            id="product-1", tenant_id="tenant", name="Pizza", description="Teste", price=10,
        ))
        session.add(Order(
            id="order-1", tenant_id="tenant", status="preparing",
            subtotal=10, total=10, fulfillment_type="delivery",
        ))
        session.add(OrderItem(
            id="item-1", tenant_id="tenant", order_id="order-1",
            product_id="product-1", quantity=1, unit_price=10, total_price=10,
        ))
        session.add(ProductionUnit(
            id="unit-1", tenant_id="tenant", order_id="order-1",
            order_item_id="item-1", unit_index=1, state="aguardando_analise",
        ))
        session.add(ProductionAttempt(
            id="attempt-1", tenant_id="tenant", production_unit_id="unit-1",
            attempt_number=1, state="aguardando_analise",
            assigned_at=datetime(2026, 10, 30, tzinfo=timezone.utc),
            stock_requested_at=datetime(2026, 10, 30, tzinfo=timezone.utc),
        ))
        session.commit()
        yield session
    engine.dispose()


def test_cancel_for_order_syncs_untouched_work_and_preserves_history(db):
    service = KdsProductionService(db, TenantContext("tenant", TenantSource.JOB))

    assert service.cancel_for_order("order-1", actor_id=None, reason="teste") is True

    unit = db.get(ProductionUnit, "unit-1")
    attempt = db.get(ProductionAttempt, "attempt-1")
    assert unit.state == "cancelled"
    assert attempt.state == "cancelled"
    assert attempt.assigned_at is not None
    assert attempt.stock_requested_at is not None
    assert db.query(AdminAuditLog).count() == 2


def test_cancel_for_order_fails_closed_on_execution_evidence(db):
    attempt = db.get(ProductionAttempt, "attempt-1")
    attempt.started_at = datetime(2026, 10, 30, 1, tzinfo=timezone.utc)
    db.flush()
    service = KdsProductionService(db, TenantContext("tenant", TenantSource.JOB))

    assert service.cancel_for_order("order-1", reason="teste") is False
    assert db.get(ProductionUnit, "unit-1").state == "aguardando_analise"
    assert db.get(ProductionAttempt, "attempt-1").state == "aguardando_analise"
    assert db.query(AdminAuditLog).count() == 0


def test_order_cancel_invokes_official_production_sync(monkeypatch):
    order = SimpleNamespace(
        id="order-1", tenant_id="tenant", payment=None,
        cancellation_reason=None, cancelled_by=None, cancelled_at=None,
    )
    calls = []
    service = OrderService.__new__(OrderService)
    service._db = SimpleNamespace(flush=lambda: None, commit=lambda: None, refresh=lambda _: None)
    service._tenant_context = TenantContext("tenant", TenantSource.JOB)
    monkeypatch.setattr(OrderService, "change_status", lambda self, *args, **kwargs: order)
    monkeypatch.setattr(
        "backend.services.kds_production_service.KdsProductionService.cancel_for_order",
        lambda self, *args, **kwargs: calls.append((args, kwargs)) or True,
    )
    monkeypatch.setattr("backend.services.order_service.bus.publish", lambda *args, **kwargs: None)

    result = service.cancel("order-1", reason="teste", cancelled_by="admin-1")

    assert result is order
    assert calls == [(('order-1',), {"actor_id": "admin-1", "reason": "teste"})]


def test_order_cancel_does_not_use_role_sentinel_as_audit_user(monkeypatch):
    order = SimpleNamespace(
        id="order-1", tenant_id="tenant", payment=None,
        cancellation_reason=None, cancelled_by=None, cancelled_at=None,
    )
    calls = []
    service = OrderService.__new__(OrderService)
    service._db = SimpleNamespace(flush=lambda: None, commit=lambda: None, refresh=lambda _: None)
    service._tenant_context = TenantContext("tenant", TenantSource.JOB)
    monkeypatch.setattr(OrderService, "change_status", lambda self, *args, **kwargs: order)
    monkeypatch.setattr(
        "backend.services.kds_production_service.KdsProductionService.cancel_for_order",
        lambda self, *args, **kwargs: calls.append(kwargs) or True,
    )
    monkeypatch.setattr("backend.services.order_service.bus.publish", lambda *args, **kwargs: None)

    service.cancel("order-1", cancelled_by="admin")

    assert calls == [{"actor_id": None, "reason": ""}]

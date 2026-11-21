"""Checkout amendment transactions against a real disposable SQLAlchemy session."""
from datetime import datetime, timezone
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.main import app as registered_app  # noqa: F401 - complete ORM registry
from backend.core.exceptions import DomainError, IdempotencyConflict, OrderNotFound
from backend.core.rbac_authorization import AuthorizedTenantActor
from backend.core.tenant_context import TenantContext, TenantSource
from backend.database import Base, get_db
from backend.models.cmv import OrderCmvSnapshot
from backend.models.idempotency import IdempotencyKey
from backend.models.kds_production import ProductionUnit, ProductionAttempt
from backend.models.order import Order, OrderItem, OrderItemFlavor, OrderStatus, OrderAmendment
from backend.models.payment import Payment, PaymentSettlement, PaymentStatus
from backend.models.finance import FinanceSettlement, FinanceTransaction
from backend.models.product import Product, MultiFlavorsConfig, PricingRule
from backend.models.tenant import Tenant
from backend.routes.orders import router
from backend.schemas.order import OrderAmendmentIn
from backend.services.order_service import OrderService
from backend.services.payment_service import PaymentService


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    names = {
        "tenants", "orders", "order_items", "order_item_flavors", "order_amendments", "idempotency_keys", "payment_settlements",
        "payments", "products", "product_categories", "product_sizes", "product_crust_types",
        "product_drink_variants", "product_option_groups", "product_options", "product_promotions",
        "product_promotion_combinations", "multi_flavors_config", "production_units", "production_attempts", "kds_assignments",
        "order_cmv_snapshots", "inventory_stock_movements", "inventory_reservations", "finance_transactions", "finance_settlements", "deliveries",
        "admin_users", "tenant_memberships", "roles", "rbac_modules", "rbac_permissions", "role_permissions", "user_permissions",
    }
    # These tests exercise service persistence; PostgreSQL-specific locks and
    # trigger DDL are checked separately rather than simulated by SQLite.
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[name] for name in names])
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def sale(db):
    context = TenantContext(tenant_id="tenant-a", source=TenantSource.JOB)
    actor = AuthorizedTenantActor("tenant-a", "operator-a", "Operador A", context)
    db.add_all([
        Tenant(id="tenant-a", slug="tenant-a", name="A"),
        Tenant(id="tenant-b", slug="tenant-b", name="B", is_legacy=True),
        Product(id="pizza", tenant_id="tenant-a", name="Calabresa", description="", price=40,
                delivery_price=45, product_type="pizza"),
        Product(id="other", tenant_id="tenant-b", name="Foreign", description="", price=1, product_type="pizza"),
        MultiFlavorsConfig(id="multi-flavors-tenant-a", tenant_id="tenant-a", max_flavors=3, pricing_rule=PricingRule.average),
    ])
    order = Order(id="order-a", tenant_id="tenant-a", status=OrderStatus.pending, sales_channel="counter",
                  subtotal=40, shipping_fee=5, discount=0, total=45, composition_revision=0)
    order.items = [OrderItem(id="old-item", tenant_id="tenant-a", product_id="pizza", quantity=1,
                            selected_size="Grande", unit_price=40, total_price=40, position=0,
                            flavors=[OrderItemFlavor(id="old-flavor", tenant_id="tenant-a", product_id="pizza",
                                                     flavor_name="Calabresa", flavor_price=40, position=0)])]
    order.payment = Payment(id="payment-a", tenant_id="tenant-a", method="cash", status=PaymentStatus.pending,
                            amount=45, gateway="on_delivery", provider="on_delivery", pay_on_delivery=True)
    db.add(order)
    db.commit()
    return OrderService(db, context), order, actor


def payload(*, revision=0, quantity=2, total=95, product="pizza", **values):
    return OrderAmendmentIn.model_validate({
        "expected_revision": revision, "expected_total": total, "reason": "Cliente pediu outra quantidade",
        "items": [{"product_id": product, "quantity": quantity, "selected_size": "Falso",
                   "flavors": [{"product_id": product, "name": "Falso", "price": .01, "icon": ""}],
                   "final_price": .01, "notes": "Sem cebola"}], **values,
    })


def amend(sale, body=None, key="change-1"):
    service, order, actor = sale
    return service.amend_order(order.id, body or payload(), actor=actor, idempotency_key=key)


def test_amends_server_priced_items_with_immutable_before_after_identity_and_state(db, sale):
    _, order, _ = sale
    history = amend(sale)
    assert order.total == order.payment.amount == 95
    assert order.subtotal == 90 and order.shipping_fee == 5
    assert order.status == OrderStatus.pending and order.composition_revision == 1
    assert order.id == "order-a" and order.payment.id == "payment-a"
    assert history.before_snapshot["items"][0]["quantity"] == 1
    assert history.before_snapshot["items"][0]["id"] == "old-item"
    assert history.after_snapshot["items"][0]["quantity"] == 2
    assert history.after_snapshot["items"][0]["unit_price"] == 45
    assert history.after_snapshot["items"][0]["flavors"][0]["flavor_name"] == "Calabresa"
    assert history.after_snapshot["items"][0]["notes"] == "Sem cebola"
    assert history.state == "pending" and history.actor_id == "operator-a"
    assert history.actor_name == "Operador A" and history.created_at is not None
    assert db.get(OrderItem, "old-item") is None
    assert db.query(OrderItemFlavor).count() == 1


def test_idempotent_replay_returns_original_revision_even_after_another_change(db, sale):
    first = amend(sale)
    amend(sale, payload(revision=1, quantity=1, total=50), key="change-2")
    replay = amend(sale)
    assert replay.id == first.id and replay.after_snapshot["total"] == 95
    assert sale[1].total == 50
    assert db.query(OrderAmendment).count() == 2
    assert db.query(IdempotencyKey).filter_by(status="completed").count() == 2


def test_reusing_key_with_different_payload_conflicts(db, sale):
    amend(sale)
    with pytest.raises(IdempotencyConflict):
        amend(sale, payload(revision=1, quantity=3, total=140))
    assert db.query(OrderAmendment).count() == 1


@pytest.mark.parametrize("body,code", [
    (payload(revision=1), "OrderAmendmentVersionConflict"),
    (payload(total=.01), "CheckoutPriceChanged"),
    (payload(product="other", total=7), "ProductNotFound"),
])
def test_stale_tampered_and_foreign_items_do_not_mutate_or_leave_claims(db, sale, body, code):
    with pytest.raises(DomainError) as exc:
        amend(sale, body)
    assert exc.value.code == code
    assert sale[1].total == sale[1].payment.amount == 45
    assert sale[1].items[0].id == "old-item"
    assert db.query(OrderAmendment).count() == db.query(IdempotencyKey).count() == 0


@pytest.mark.parametrize("status", [OrderStatus.preparing, OrderStatus.ready_for_pickup,
                                    OrderStatus.on_the_way, OrderStatus.delivered, OrderStatus.cancelled, OrderStatus.refunded])
def test_production_and_terminal_statuses_block_without_creating_history(db, sale, status):
    sale[1].status = status
    db.commit()
    with pytest.raises(DomainError) as exc:
        amend(sale)
    assert exc.value.code == "OrderProductionAlreadyStarted"
    assert sale[1].items[0].id == "old-item"
    assert db.query(OrderAmendment).count() == 0


def test_production_timestamp_blocks_even_if_order_status_was_reset(db, sale):
    sale[1].preparation_started_at = datetime.now(timezone.utc)
    db.commit()
    with pytest.raises(DomainError) as exc:
        amend(sale)
    assert exc.value.code == "OrderProductionAlreadyStarted"


@pytest.mark.parametrize("started", [False, True])
def test_existing_kds_units_are_not_rewritten_and_started_attempt_is_detected(db, sale, started):
    unit = ProductionUnit(id="unit", tenant_id="tenant-a", order_id="order-a", order_item_id="old-item",
                          unit_index=1, state="assembling" if started else "queued", station_id="pizza")
    db.add_all([unit, ProductionAttempt(id="attempt", tenant_id="tenant-a", production_unit_id="unit", attempt_number=1,
                                      state=unit.state, started_at=datetime.now(timezone.utc) if started else None)])
    db.commit()
    if started:
        with pytest.raises(DomainError) as exc:
            amend(sale)
        # Post-production amendments are now fail-closed until the production
        # effects migration is present; once applied, this path records the
        # loss and queues the replacement instead of silently rewriting it.
        assert exc.value.code in {
            "OrderProductionAlreadyStarted",
            "OrderAmendmentProductionCompositionUnsupported",
            "OrderAmendmentProductionEffectsUnavailable",
        }
        assert db.get(ProductionUnit, "unit").order_item_id == "old-item"
    else:
        amendment = amend(sale)
        assert amendment.revision == 1
        assert db.get(ProductionUnit, "unit") is None


@pytest.mark.parametrize("field,value", [("status", PaymentStatus.approved), ("provider_payment_id", "gateway-id"),
                                        ("pix_payload", "issued-pix"), ("payment_url", "https://gateway.test")])
def test_settled_or_issued_payments_block(db, sale, field, value):
    setattr(sale[1].payment, field, value)
    db.commit()
    with pytest.raises(DomainError) as exc:
        amend(sale)
    assert exc.value.code == "OrderAmendmentPaymentLocked"


def test_pay_on_delivery_acceptance_is_not_confused_with_settled_payment(db, sale):
    sale[1].status = OrderStatus.paid
    sale[1].paid_at = sale[1].payment.paid_at = datetime.now(timezone.utc)
    db.commit()
    history = amend(sale)
    assert history.state == "paid" and sale[1].payment.status == PaymentStatus.pending


def test_frozen_cmv_is_preserved_and_blocks_amendment(db, sale):
    db.add(OrderCmvSnapshot(id="frozen", tenant_id="tenant-a", order_id="order-a", sale_total=40, cost_total=12))
    db.commit()
    with pytest.raises(DomainError) as exc:
        amend(sale)
    assert exc.value.code == "OrderAmendmentDependentRecords"
    assert db.get(OrderCmvSnapshot, "frozen").cost_total == 12


def test_manual_discount_is_recomputed_and_decrease_is_supported(db, sale):
    order = sale[1]
    order.manual_discount_type, order.manual_discount_value = "percentage", 10
    order.discount, order.total, order.payment.amount = 4, 41, 41
    db.commit()
    history = amend(sale, payload(quantity=1, total=45.5))
    assert history.after_snapshot["discount"] == 4.5
    assert history.after_snapshot["total"] == 45.5


def test_cross_tenant_order_and_history_are_not_found(db, sale):
    service = OrderService(db, TenantContext(tenant_id="tenant-b", source=TenantSource.JOB))
    actor = AuthorizedTenantActor("tenant-b", "operator-b", "B", service._tenant_context)
    with pytest.raises(OrderNotFound):
        service.amend_order("order-a", payload(), actor=actor, idempotency_key="other-tenant")
    with pytest.raises(OrderNotFound):
        service.amendment_history("order-a")
    assert db.query(IdempotencyKey).count() == 0


def test_failure_after_item_flush_rolls_back_composition_and_releases_key(db, sale, monkeypatch):
    service = sale[0]
    original = service._amendment_snapshot
    calls = 0

    def fail_second(order):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated history failure")
        return original(order)

    monkeypatch.setattr(service, "_amendment_snapshot", fail_second)
    with pytest.raises(RuntimeError):
        amend(sale)
    db.expire_all()
    assert sale[1].total == sale[1].payment.amount == 45
    assert sale[1].composition_revision == 0 and sale[1].items[0].id == "old-item"
    assert db.query(OrderAmendment).count() == db.query(IdempotencyKey).count() == 0
    monkeypatch.setattr(service, "_amendment_snapshot", original)
    assert amend(sale).revision == 1


@pytest.mark.parametrize("values", [{"items": []}, {"reason": "   "}, {"expected_total": float("nan")},
                                   {"tenant_id": "tenant-b"}, {"status": "preparing"}])
def test_schema_rejects_empty_composition_and_protected_fields(values):
    with pytest.raises(ValidationError):
        payload(**values)


def test_api_requires_auth_edit_permission_and_idempotency_and_returns_history(db, sale):
    api = FastAPI()
    api.include_router(router, prefix="/api")
    api.dependency_overrides[get_db] = lambda: db
    post_route = next(route for route in router.routes if route.path == "/orders/{order_id}/amendments" and "POST" in route.methods)
    get_route = next(route for route in router.routes if route.path == "/orders/{order_id}/amendments" and "GET" in route.methods)
    post_actor = next(dep.call for dep in post_route.dependant.dependencies if dep.name == "actor")
    get_actor = next(dep.call for dep in get_route.dependant.dependencies if dep.name == "actor")
    entitlement = next(dep.call for dep in post_route.dependant.dependencies if dep.name == "_entitlement")
    api.dependency_overrides[entitlement] = lambda: None
    with TestClient(api) as client:
        assert client.post("/api/orders/order-a/amendments", json=payload().model_dump()).status_code == 401

        def deny():
            raise HTTPException(403, "Sem permissao")

        api.dependency_overrides[post_actor] = deny
        assert client.post("/api/orders/order-a/amendments", json=payload().model_dump()).status_code == 403
        api.dependency_overrides[post_actor] = lambda: sale[2]
        assert client.post("/api/orders/order-a/amendments", json=payload().model_dump()).status_code == 422
        result = client.post("/api/orders/order-a/amendments", json=payload().model_dump(), headers={"Idempotency-Key": "api-1"})
        assert result.status_code == 200 and result.json()["data"]["revision"] == 1
        api.dependency_overrides[get_actor] = lambda: sale[2]
        history = client.get("/api/orders/order-a/amendments").json()["data"]
        assert history["composition_revision"] == 1 and len(history["amendments"]) == 1
        assert history["amendments"][0]["actor_id"] == "operator-a"
    assert db.query(OrderAmendment).count() == 1


def test_postgresql_migration_renders_revision_tenant_constraints_and_append_only_trigger():
    import importlib.util
    from io import StringIO
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    path = Path(__file__).resolve().parents[1] / "backend/migrations/versions/20261120_order_amendments.py"
    spec = importlib.util.spec_from_file_location("amendment_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "20261117_combo_landing"
    output = StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
    with Operations.context(context):
        migration.upgrade()
        migration.downgrade()
    sql = output.getvalue()
    assert "composition_revision INTEGER DEFAULT '0' NOT NULL" in sql
    assert "FOREIGN KEY(tenant_id, order_id) REFERENCES orders (tenant_id, id) ON DELETE RESTRICT" in sql
    assert "CREATE UNIQUE INDEX uq_order_amendments_revision" in sql
    assert "CREATE UNIQUE INDEX uq_order_amendments_claim" in sql
    assert "BEFORE UPDATE OR DELETE ON order_amendments" in sql
    assert "DROP TABLE order_amendments" in sql


def test_payment_lookup_takes_postgresql_order_lock_before_using_total():
    from unittest.mock import MagicMock
    from backend.services.payment_service import PaymentService

    db = MagicMock()
    query = db.query.return_value.filter.return_value
    query.filter.return_value = query
    locked = query.populate_existing.return_value.with_for_update.return_value
    order = type("LoadedOrder", (), {"payment": None})()
    locked.first.return_value = order
    service = PaymentService(db, tenant_id="tenant-a")
    assert service._get_order("order-a") is order
    query.populate_existing.return_value.with_for_update.assert_called_once_with(of=Order)


def test_real_rbac_rejects_view_only_role_and_honors_edit_grant_and_deny(db, sale, monkeypatch):
    from starlette.requests import Request
    from backend.core import rbac_authorization
    from backend.models.admin import AdminUser
    from backend.models.membership import TenantMembership
    from backend.models.rbac import Role, RbacModule, RbacPermission, RolePermission, UserPermission

    admin = AdminUser(id="operator-a", name="Operador A", email="operator@example.test", password_hash="test", role_id="sales")
    db.add_all([
        admin,
        TenantMembership(id="member", tenant_id="tenant-a", user_id=admin.id, role="operator", status="active"),
        Role(id="sales", tenant_id="tenant-a", name="Vendas"),
        RbacModule(id="orders-module", key="pedidos", name="Pedidos"),
        RbacPermission(id="view", key="view", name="Visualizar"),
        RbacPermission(id="edit", key="edit", name="Alterar"),
        RolePermission(id="view-only", tenant_id="tenant-a", role_id="sales", module_id="orders-module", permission_id="view", allowed=True),
    ])
    db.commit()
    monkeypatch.setattr(rbac_authorization, "resolve_panel_tenant_context", lambda *args: sale[2].tenant_context)
    request = Request({"type": "http"})
    edit = rbac_authorization.require_rbac_permission("pedidos", "edit")
    with pytest.raises(HTTPException) as exc:
        edit(request=request, db=db, admin=admin)
    assert exc.value.status_code == 403
    db.add(RolePermission(id="edit-grant", tenant_id="tenant-a", role_id="sales", module_id="orders-module", permission_id="edit", allowed=True))
    db.commit()
    actor = edit(request=request, db=db, admin=admin)
    assert actor.tenant_id == "tenant-a" and actor.user_id == "operator-a"
    db.add(UserPermission(id="edit-deny", tenant_id="tenant-a", user_id=admin.id, module_id="orders-module", permission_id="edit", allowed=False))
    db.commit()
    with pytest.raises(HTTPException) as exc:
        edit(request=request, db=db, admin=admin)
    assert exc.value.status_code == 403


def test_commit_failure_rolls_back_order_history_payment_and_claim(db, sale, monkeypatch):
    original_commit = db.commit
    count = 0

    def fail_business_commit():
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError("simulated commit failure")
        original_commit()

    monkeypatch.setattr(db, "commit", fail_business_commit)
    with pytest.raises(RuntimeError):
        amend(sale)
    db.expire_all()
    assert sale[1].composition_revision == 0 and sale[1].items[0].id == "old-item"
    assert sale[1].total == sale[1].payment.amount == 45
    assert db.query(OrderAmendment).count() == db.query(IdempotencyKey).count() == 0


def _add_post_amendment_delta(db, sale, *, delta: str):
    _, order, _ = sale
    payment = order.payment
    payment.status = PaymentStatus.approved
    payment.method = "pix"
    payment.pay_on_delivery = False
    payment.provider = "mercado_pago"
    payment.gateway = "mercadopago"
    payment.provider_payment_id = "mp-original"
    payment.transaction_id = "mp-original"
    claim = IdempotencyKey(
        id="amendment-claim", tenant_id="tenant-a", operation="orders.amend",
        key_hash="a" * 64, request_hash="b" * 64, status="completed",
        resource_id="amendment-1", expires_at=datetime.now(timezone.utc),
    )
    amendment = OrderAmendment(
        id="amendment-1", tenant_id="tenant-a", order_id=order.id, revision=1,
        idempotency_key_id=claim.id, actor_id="operator-a", actor_name="Operador A",
        reason="Ajuste de pos-producao", state="preparing", before_snapshot={"total": 45},
        after_snapshot={"total": 45, "financial_adjustment": {"delta": delta}},
        created_at=datetime.now(timezone.utc),
    )
    finance = FinanceTransaction(
        id="finance-amendment-1", tenant_id="tenant-a", entry_type="income" if not delta.startswith("-") else "expense",
        status="pending", description="Ajuste de alteracao", amount=abs(float(delta)),
        paid_amount=0, net_amount=abs(float(delta)), order_id=order.id, payment_id=payment.id,
        origin_type="order_amendment_adjustment", origin_id=amendment.id,
    )
    db.add_all([claim, amendment, finance])
    db.commit()
    return amendment


def test_positive_post_amendment_settlement_is_tenant_scoped_and_idempotent(db, sale, monkeypatch):
    amendment = _add_post_amendment_delta(db, sale, delta="10.00")
    calls = []

    def charge(service, order, amendment_row, payment, amount, provider_key):
        calls.append((order.tenant_id, amendment_row.id, payment.id, amount, provider_key))
        return {"provider": "mercado_pago", "operation_id": "mp-extra", "provider_status": "pending",
                "status": "pending", "response": {"id": "mp-extra"}}

    monkeypatch.setattr(PaymentService, "_amendment_charge", charge)
    service = PaymentService(db, tenant_id="tenant-a")
    first = service.settle_amendment("order-a", amendment.id, idempotency_key="settle-1")
    replay = service.settle_amendment("order-a", amendment.id, idempotency_key="settle-1")

    assert first.id == replay.id and first.direction == "charge" and first.status == "pending"
    assert len(calls) == 1 and calls[0][0] == "tenant-a"
    assert db.get(Payment, "payment-a").amount == 45
    assert db.query(FinanceTransaction).filter_by(id="finance-amendment-1").one().status == "pending"
    with pytest.raises(OrderNotFound):
        PaymentService(db, tenant_id="tenant-b").settle_amendment("order-a", amendment.id, idempotency_key="other-tenant")


def test_negative_post_amendment_settlement_records_partial_refund_without_refunding_original_payment(db, sale, monkeypatch):
    amendment = _add_post_amendment_delta(db, sale, delta="-10.00")

    def refund(service, payment, amount, reason, provider_key):
        return {"provider": "mercado_pago", "operation_id": "refund-1", "provider_status": "accepted",
                "status": "succeeded", "response": {"id": "refund-1", "amount": float(amount)}}

    monkeypatch.setattr(PaymentService, "_amendment_refund", refund)
    result = PaymentService(db, tenant_id="tenant-a").settle_amendment(
        "order-a", amendment.id, idempotency_key="settle-refund", reason="Cliente recebeu abatimento",
    )

    payment = db.get(Payment, "payment-a")
    finance = db.query(FinanceTransaction).filter_by(id="finance-amendment-1").one()
    assert result.direction == "refund" and result.status == "succeeded" and result.amount == 10
    assert payment.status == PaymentStatus.approved
    assert finance.status == "paid" and db.query(FinanceSettlement).count() == 1
    assert db.query(PaymentSettlement).filter_by(direction="refund").count() == 1


def test_amendment_charge_webhook_requires_matching_amount_and_direction(db, sale):
    amendment = _add_post_amendment_delta(db, sale, delta="10.00")
    finance = db.query(FinanceTransaction).filter_by(id="finance-amendment-1").one()
    db.add(PaymentSettlement(
        id="settlement-charge", tenant_id="tenant-a", order_id="order-a", amendment_id=amendment.id,
        payment_id="payment-a", finance_transaction_id=finance.id, direction="charge", status="pending",
        amount=10, provider="mercado_pago", provider_operation_id="remote-1", idempotency_key="settle-charge",
    ))
    db.add(PaymentSettlement(
        id="settlement-refund", tenant_id="tenant-a", order_id="order-a", amendment_id=amendment.id,
        payment_id="payment-a", finance_transaction_id=finance.id, direction="refund", status="pending",
        amount=10, provider="mercado_pago", provider_operation_id="remote-1", idempotency_key="settle-refund",
    ))
    db.commit()

    service = PaymentService(db, tenant_id="tenant-a")
    result = service._reconcile_amendment_settlement_webhook(
        provider="mercado_pago", operation_id="remote-1", external_reference=None,
        provider_status="approved", provider_amount=11,
    )

    assert result["reason"] == "settlement_amount_mismatch"
    assert db.get(PaymentSettlement, "settlement-charge").status == "failed"
    assert db.get(PaymentSettlement, "settlement-refund").status == "pending"


def test_partial_asaas_refund_webhook_reconciles_delta_without_full_refund(db, sale):
    amendment = _add_post_amendment_delta(db, sale, delta="-10.00")
    payment = db.get(Payment, "payment-a")
    payment.provider = "asaas"
    payment.gateway = "asaas"
    payment.provider_payment_id = "asaas-original"
    payment.transaction_id = "asaas-original"
    finance = db.query(FinanceTransaction).filter_by(id="finance-amendment-1").one()
    db.add(PaymentSettlement(
        id="settlement-asaas-refund", tenant_id="tenant-a", order_id="order-a", amendment_id=amendment.id,
        payment_id=payment.id, finance_transaction_id=finance.id, direction="refund", status="pending",
        amount=10, provider="asaas", provider_operation_id="asaas-original", idempotency_key="settle-asaas-refund",
    ))
    db.commit()

    result = PaymentService(db, tenant_id="tenant-a")._reconcile_amendment_refund_webhook(
        provider="asaas", operation_id="asaas-original", provider_status="PARTIALLY_REFUNDED",
        event_type="PAYMENT_PARTIALLY_REFUNDED",
    )

    assert result["settlement_status"] == "succeeded"
    assert payment.status == PaymentStatus.approved
    assert finance.status == "paid"

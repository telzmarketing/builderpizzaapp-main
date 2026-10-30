"""Opt-in tests against the disposable, fully migrated product-audit database."""
import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.main import app  # registers the complete ORM model registry
from backend.core.exceptions import DomainError
from backend.core.tenant_context import TenantContext, TenantSource
from backend.models.order import Order, OrderStatus
from backend.models.payment import PaymentStatus
from backend.models.product import Product, ProductSize, ProductCrustType, MultiFlavorsConfig, PricingRule
from backend.models.salao import RestaurantTable, TableSession
from backend.models.tenant import Tenant
from backend.services.order_service import OrderService
from backend.services.salao_service import TableSessionService


@pytest.fixture
def db():
    url = os.getenv("PRODUCT_AUDIT_DATABASE_URL")
    if not url:
        pytest.skip("PRODUCT_AUDIT_DATABASE_URL requires an explicitly configured disposable migrated PostgreSQL")
    engine = create_engine(url)
    with engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()
    engine.dispose()


@pytest.fixture
def sale(db, monkeypatch):
    token = uuid.uuid4().hex[:12]
    tenant_id = f"option-test-{token}"
    db.add(Tenant(id=tenant_id, name="Options audit", slug=tenant_id))
    db.flush()
    context = TenantContext(tenant_id=tenant_id, source=TenantSource.JOB)
    product = Product(id=f"prod-{token}", tenant_id=tenant_id, name="Pizza", description="", price=30,
                      dine_in_price=32, delivery_price=35, product_type="pizza")
    table = RestaurantTable(id=f"table-{token}", tenant_id=tenant_id, number=token)
    db.add_all([product, table, MultiFlavorsConfig(id=f"multi-flavors-{tenant_id}", tenant_id=tenant_id, max_flavors=3, pricing_rule=PricingRule.average)])
    db.flush()
    size = ProductSize(id=f"size-{token}", tenant_id=tenant_id, product_id=product.id, label="Grande", price=80)
    border = ProductCrustType(id=f"border-{token}", tenant_id=tenant_id, product_id=product.id, name="Catupiry", price_addition=8, option_kind="border")
    comanda = TableSession(id=f"session-{token}", tenant_id=tenant_id, table_id=table.id)
    db.add_all([size, border, comanda])
    db.flush()
    monkeypatch.setattr(OrderService, "_notify_new_order_whatsapp", lambda *args: None)
    return context, product, size, border, comanda


def test_salao_preserves_options_serve_before_payment_and_cross_tenant_denied(db, sale):
    context, product, size, border, comanda = sale
    TableSessionService(db, context).add_item(comanda.id, {
        "product_id": product.id, "quantity": 2, "unit_price": .01,
        "selected_size_id": size.id, "selected_border_id": border.id,
    })
    orders = OrderService(db, context)
    order = orders.create_from_table_session(comanda.id)
    assert order.total == 176
    assert order.items[0].selected_size_id == size.id
    assert order.items[0].selected_border_id == border.id
    assert order.items[0].selected_border_name == "Catupiry"
    assert order.items[0].flavors[0].product_id == product.id
    assert order.payment.status == PaymentStatus.pending
    orders.change_status(order.id, "ready_for_pickup")
    served = orders.serve_table_session(comanda.id)
    assert served.status == OrderStatus.delivered
    paid = orders.confirm_table_session_payment(comanda.id)
    assert paid.status == OrderStatus.delivered
    assert paid.payment.status == PaymentStatus.approved
    assert paid.table_session.status == "paid"
    other_context = TenantContext(tenant_id=f"other-{uuid.uuid4().hex}", source=TenantSource.JOB)
    with pytest.raises(DomainError):
        OrderService(db, other_context).create_from_table_session(comanda.id)
    with pytest.raises(DomainError):
        OrderService(db, other_context).confirm_table_session_payment(comanda.id)
    with pytest.raises(DomainError):
        OrderService(db, other_context).serve_table_session(comanda.id)


def test_comanda_rejects_invalid_option_without_creating_order(db, sale):
    context, product, _, _, comanda = sale
    with pytest.raises(DomainError):
        TableSessionService(db, context).add_item(comanda.id, {
            "product_id": product.id, "quantity": 1, "selected_size_id": "unknown",
        })
    assert db.query(Order).filter(Order.table_session_id == comanda.id).count() == 0


def test_checkout_reconfirmation_prevents_creation_and_preserves_option_snapshots(db, sale, monkeypatch):
    from backend.schemas.order import CheckoutIn, CartItemIn, DeliveryAddressIn
    from backend.schemas.shipping_v2 import ShippingCalculateOut
    from backend.services.store_operation_service import StoreOperationService
    from backend.services.shipping_service import ShippingService
    context, product, size, border, _ = sale
    monkeypatch.setattr(StoreOperationService, "validate_order_allowed", lambda *args, **kwargs: None)
    monkeypatch.setattr(ShippingService, "calculate", lambda *args: ShippingCalculateOut(shipping_price=0, shipping_type="pickup", rule_name="Pickup", free=True))
    payload = CheckoutIn(items=[CartItemIn(product_id=product.id, quantity=1, selected_size="Fake", selected_size_id=size.id,
        selected_border_id=border.id, selected_border_name="Fake", flavors=[{"product_id": product.id, "name": "Fake", "price": .01, "icon": ""}], final_price=.01)],
        delivery=DeliveryAddressIn(name="Audit", phone="11999990000", street="Pickup", city="Audit", is_pickup=True),
        payment_method="cash", expected_total=1)
    service = OrderService(db, context)
    with pytest.raises(DomainError) as error:
        service.create_from_checkout(payload)
    assert error.value.code == "CheckoutPriceChanged"
    assert db.query(Order).filter(Order.tenant_id == context.tenant_id).count() == 0
    payload.expected_total = 88
    order = service.create_from_checkout(payload)
    assert order.total == order.payment.amount == 88
    assert order.items[0].selected_size == "Grande"
    assert order.items[0].selected_border_name == "Catupiry"
    assert order.items[0].selected_border_id == border.id
    assert order.items[0].flavors[0].flavor_name == "Pizza"

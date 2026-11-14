import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app  # noqa: F401 - register the complete ORM metadata
from backend.core.tenant_context import TenantContext, TenantSource
from backend.database import Base
from backend.models.customer import Customer
from backend.models.customer_review import CustomerReview
from backend.models.delivery import Delivery, DeliveryStatus
from backend.models.order import Order, OrderItem, OrderStatus
from backend.models.product import Product
from backend.models.tenant import Tenant
from backend.schemas.customer_review import CustomerReviewAdminCreate, CustomerReviewCreate, CustomerReviewModerationIn
from backend.services.customer_review_service import CustomerReviewService, ReviewAlreadyExists


def _context(tenant_id: str) -> TenantContext:
    return TenantContext(tenant_id=tenant_id, source=TenantSource.JOB, correlation_id=f"test:{tenant_id}")


def _db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[Tenant.__table__, Customer.__table__, Product.__table__, Order.__table__, OrderItem.__table__, Delivery.__table__, CustomerReview.__table__])
    return engine, sessionmaker(bind=engine)()


def _item_review(order_id: str, item_id: str, product_id: str, rating: int) -> CustomerReviewCreate:
    return CustomerReviewCreate(order_id=order_id, review_type="item", rating=rating, order_item_id=item_id, product_id=product_id, comment="Muito boa")


def test_customer_product_review_is_tenant_scoped_and_rejects_duplicate_target():
    engine, db = _db()
    db.add_all([
        Tenant(id="tenant-a", slug="a", name="A", is_legacy=True), Tenant(id="tenant-b", slug="b", name="B", is_legacy=None),
        Customer(id="customer-a", tenant_id="tenant-a", name="Ana"),
        Product(id="pizza-a", tenant_id="tenant-a", name="Pizza A", description="", price=40, rating=4.5),
        Product(id="pizza-b", tenant_id="tenant-b", name="Pizza B", description="", price=40, rating=4.5),
        Order(id="order-a", tenant_id="tenant-a", customer_id="customer-a", status=OrderStatus.delivered, subtotal=40, total=40, delivery_name="Ana Cliente"),
        OrderItem(id="item-a", tenant_id="tenant-a", order_id="order-a", product_id="pizza-a", quantity=1, unit_price=40, total_price=40),
        Order(id="order-b", tenant_id="tenant-b", status=OrderStatus.delivered, subtotal=40, total=40, delivery_name="B Cliente"),
        OrderItem(id="item-b", tenant_id="tenant-b", order_id="order-b", product_id="pizza-b", quantity=1, unit_price=40, total_price=40),
    ])
    db.commit()
    service = CustomerReviewService(db, _context("tenant-a"))
    first = service.create_customer_review(_item_review("order-a", "item-a", "pizza-a", 5), customer_id="customer-a")
    assert first.status == "pending"
    with pytest.raises(ReviewAlreadyExists):
        service.create_customer_review(_item_review("order-a", "item-a", "pizza-a", 4), customer_id="customer-a")
    with pytest.raises(Exception) as exc:
        service.create_customer_review(_item_review("order-b", "item-b", "pizza-b", 5))
    assert getattr(exc.value, "status_code", None) == 404
    db.close()
    engine.dispose()


def test_admin_moderation_updates_product_aggregate_and_delivery_sync_keeps_legacy_contract():
    engine, db = _db()
    db.add_all([
        Tenant(id="tenant-a", slug="a", name="A"),
        Product(id="pizza-a", tenant_id="tenant-a", name="Pizza A", description="", price=40, rating=4.5),
        Order(id="order-a", tenant_id="tenant-a", status=OrderStatus.delivered, subtotal=40, total=40, delivery_name="Cliente"),
        OrderItem(id="item-a", tenant_id="tenant-a", order_id="order-a", product_id="pizza-a", quantity=1, unit_price=40, total_price=40),
        Delivery(id="delivery-a", tenant_id="tenant-a", order_id="order-a", status=DeliveryStatus.completed, rating=5),
    ])
    db.commit()
    service = CustomerReviewService(db, _context("tenant-a"))
    product_review = service.create_admin_review(CustomerReviewAdminCreate(order_id="order-a", review_type="product", order_item_id="item-a", product_id="pizza-a", rating=5, author_name="Cliente"), admin_id="admin-a")
    delivery_review = service.sync_legacy_delivery_rating(db.query(Delivery).one(), 3, "Chegou morna")
    assert product_review.status == "approved"
    assert delivery_review.status == "approved"
    assert service.list_reviews(public_only=True, review_type="item", product_id="pizza-a")[0].rating == 5
    service.moderate(product_review.id, CustomerReviewModerationIn(status="rejected", moderation_note="Ocultada"), admin_id="admin-a")
    assert service.list_reviews(public_only=True, review_type="item", product_id="pizza-a") == []
    db.close()
    engine.dispose()

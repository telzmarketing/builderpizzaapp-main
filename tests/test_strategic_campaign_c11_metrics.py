from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.main  # noqa: F401 - load complete SQLAlchemy registry
from backend.database import Base
from backend.models.cmv import OrderCmvSnapshot
from backend.models.order import Order, OrderCommercialGroup, OrderItem, OrderStatus
from backend.models.paid_traffic import AdDailyMetric
from backend.models.payment import Payment, PaymentMethod, PaymentStatus
from backend.models.product import Product
from backend.models.strategic_campaign import StrategicCampaign, StrategicCampaignStatus, StrategicCapacitySlot, StrategicReservation
from backend.routes.marketing import VisitorEvent
from backend.services.strategic_campaign_metrics_service import StrategicCampaignMetricsService


NOW = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
DATE_FROM = date(2026, 11, 1)
DATE_TO = date(2026, 11, 30)


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(
        engine,
        tables=[
            StrategicCampaign.__table__,
            StrategicCapacitySlot.__table__,
            StrategicReservation.__table__,
            VisitorEvent.__table__,
            Order.__table__,
            Payment.__table__,
            Product.__table__,
            OrderCommercialGroup.__table__,
            OrderItem.__table__,
            OrderCmvSnapshot.__table__,
            AdDailyMetric.__table__,
        ],
    )
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def _campaign(db):
    db.add(StrategicCampaign(
        id="campaign-1",
        tenant_id="tenant-1",
        name="Black Friday",
        slug="black-friday",
        status=StrategicCampaignStatus.active,
        visual_config={},
        commercial_config={},
        marketing_config={},
    ))
    db.commit()


def _paid_order(db, order_id: str, *, tenant_id="tenant-1", channel="landing_page", total=100):
    order = Order(
        id=order_id,
        tenant_id=tenant_id,
        status=OrderStatus.paid,
        strategic_campaign_id="campaign-1",
        entry_channel=channel,
        subtotal=total,
        total=total,
        created_at=NOW,
    )
    db.add_all([
        order,
        Payment(
            id=f"payment-{order_id}",
            tenant_id=tenant_id,
            order_id=order_id,
            method=PaymentMethod.pix,
            status=PaymentStatus.approved,
            amount=total,
            created_at=NOW,
        ),
    ])
    return order


def _component(db, order: Order, *, group_id: str, product_id: str, subcategory_id: str, quantity: int):
    db.add(OrderCommercialGroup(
        id=group_id,
        tenant_id=order.tenant_id,
        order_id=order.id,
        position=0,
        strategic_campaign_id="campaign-1",
        strategic_offer_id="offer-1",
        campaign_version=1,
        composition_revision=1,
        quantity=1,
        entry_channel=order.entry_channel,
        pricing_strategy="catalog",
        original_amount=100,
        discount_amount=0,
        promotional_amount=100,
        commercial_snapshot={},
        created_at=NOW,
    ))
    db.add(OrderItem(
        id=f"item-{group_id}-{product_id}",
        tenant_id=order.tenant_id,
        order_id=order.id,
        product_id=product_id,
        commercial_group_id=group_id,
        commercial_group_position=0,
        source_subcategory_id=subcategory_id,
        quantity=quantity,
        unit_price=50,
        total_price=50 * quantity,
    ))


def test_c11_breaks_paid_sales_down_by_entry_channel(db):
    _campaign(db)
    _paid_order(db, "landing-1", channel="landing_page", total=120)
    _paid_order(db, "pdv-1", channel="pdv", total=80)
    _paid_order(db, "pdv-2", channel="pdv", total=100)
    _paid_order(db, "other-tenant", tenant_id="tenant-2", channel="pdv", total=999)
    db.commit()

    result = StrategicCampaignMetricsService(db, "tenant-1").get("campaign-1", DATE_FROM, DATE_TO)

    assert result["revenue"] == 300.0
    assert result["sales_breakdown"]["by_entry_channel"] == [
        {
            "entry_channel": "landing_page",
            "paid_orders": 1,
            "revenue": 120.0,
            "scheduled_paid_orders": 0,
            "average_ticket": 120.0,
        },
        {
            "entry_channel": "pdv",
            "paid_orders": 2,
            "revenue": 180.0,
            "scheduled_paid_orders": 0,
            "average_ticket": 90.0,
        },
    ]


def test_c11_breaks_components_down_by_selected_subcategory_and_product(db):
    _campaign(db)
    first = _paid_order(db, "order-1", channel="operations", total=150)
    second = _paid_order(db, "order-2", channel="pdv", total=100)
    other = _paid_order(db, "order-other", tenant_id="tenant-2", channel="pdv", total=999)
    _component(db, first, group_id="group-1", product_id="pizza-1", subcategory_id="traditional", quantity=2)
    _component(db, second, group_id="group-2", product_id="pizza-1", subcategory_id="traditional", quantity=1)
    _component(db, other, group_id="group-other", product_id="pizza-2", subcategory_id="premium", quantity=99)
    db.commit()

    result = StrategicCampaignMetricsService(db, "tenant-1").get("campaign-1", DATE_FROM, DATE_TO)

    assert result["sales_breakdown"]["by_selected_subcategory"] == [{
        "subcategory_id": "traditional",
        "quantity": 3,
        "paid_orders": 2,
        "commercial_groups": 2,
    }]
    assert result["sales_breakdown"]["by_selected_component"] == [{
        "offer_id": "offer-1",
        "subcategory_id": "traditional",
        "product_id": "pizza-1",
        "quantity": 3,
        "paid_orders": 2,
        "commercial_groups": 2,
    }]


def test_c11_ignores_unbound_legacy_items_and_unpaid_orders(db):
    _campaign(db)
    paid = _paid_order(db, "paid", channel="phone", total=75)
    unpaid = Order(
        id="unpaid",
        tenant_id="tenant-1",
        status=OrderStatus.pending,
        strategic_campaign_id="campaign-1",
        entry_channel="counter",
        subtotal=50,
        total=50,
        created_at=NOW,
    )
    db.add(unpaid)
    _component(db, unpaid, group_id="group-unpaid", product_id="pizza-2", subcategory_id="premium", quantity=4)
    db.add(OrderItem(
        id="legacy-item",
        tenant_id="tenant-1",
        order_id=paid.id,
        product_id="legacy-product",
        quantity=3,
        unit_price=25,
        total_price=75,
    ))
    db.commit()

    result = StrategicCampaignMetricsService(db, "tenant-1").get("campaign-1", DATE_FROM, DATE_TO)

    assert result["sales_breakdown"]["by_entry_channel"][0]["entry_channel"] == "phone"
    assert result["sales_breakdown"]["by_selected_subcategory"] == []
    assert result["sales_breakdown"]["by_selected_component"] == []

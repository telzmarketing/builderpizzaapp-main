from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.main  # noqa: F401 - load complete SQLAlchemy registry
from backend.database import Base
from backend.models.cmv import OrderCmvSnapshot
from backend.models.order import Order, OrderItem, OrderStatus
from backend.models.paid_traffic import AdDailyMetric
from backend.models.payment import Payment, PaymentMethod, PaymentStatus
from backend.models.product import Product
from backend.models.strategic_campaign import (
    StrategicCampaign,
    StrategicCampaignStatus,
    StrategicCapacitySlot,
    StrategicReservation,
)
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
            OrderItem.__table__,
            OrderCmvSnapshot.__table__,
            AdDailyMetric.__table__,
        ],
    )
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def _campaign(db, campaign_id="campaign-1", tenant_id="tenant-1", traffic_id="traffic-1"):
    row = StrategicCampaign(
        id=campaign_id,
        tenant_id=tenant_id,
        name="Black Friday",
        slug=f"black-friday-{tenant_id}",
        status=StrategicCampaignStatus.active,
        visual_config={},
        commercial_config={},
        marketing_config={"planned_budget": 500, "traffic_campaign_id": traffic_id},
    )
    db.add(row)
    db.commit()
    return row


def _paid_order(db, order_id="order-1", tenant_id="tenant-1", campaign_id="campaign-1", total=200):
    order = Order(
        id=order_id,
        tenant_id=tenant_id,
        status=OrderStatus.paid,
        strategic_campaign_id=campaign_id,
        subtotal=total,
        total=total,
        is_scheduled=True,
        created_at=NOW,
    )
    payment = Payment(
        id=f"payment-{order_id}",
        tenant_id=tenant_id,
        order_id=order_id,
        method=PaymentMethod.pix,
        status=PaymentStatus.approved,
        amount=total,
        created_at=NOW,
    )
    db.add_all([order, payment])
    return order


def test_c8_reconciles_marketing_financial_and_operational_sources(db):
    _campaign(db)
    product = Product(
        id="pizza-1",
        tenant_id="tenant-1",
        name="Pizza campanha",
        description="Pizza",
        price=100,
        product_type="pizza",
    )
    order = _paid_order(db)
    db.add_all([
        product,
        OrderItem(
            id="item-1",
            tenant_id="tenant-1",
            order_id=order.id,
            product_id=product.id,
            quantity=2,
            unit_price=100,
            total_price=200,
        ),
        OrderCmvSnapshot(
            id="cmv-1",
            tenant_id="tenant-1",
            order_id=order.id,
            sale_total=200,
            cost_total=80,
            missing_recipe=False,
            missing_cost=False,
        ),
        AdDailyMetric(
            id="ad-1",
            tenant_id="tenant-1",
            traffic_campaign_id="traffic-1",
            platform="meta",
            metric_date=DATE_TO,
            spend=20,
            impressions=1000,
            clicks=100,
            conversions=4,
        ),
        StrategicCapacitySlot(
            id="slot-1",
            tenant_id="tenant-1",
            campaign_id="campaign-1",
            offer_scope="*",
            starts_at=NOW + timedelta(days=1),
            ends_at=NOW + timedelta(days=1, hours=1),
            capacity_total=10,
            capacity_used=3,
        ),
        StrategicReservation(
            id="reservation-1",
            tenant_id="tenant-1",
            campaign_id="campaign-1",
            slot_id="slot-1",
            customer_reference="customer-1",
            quantity=3,
            status="confirmed",
            payment_mode="partial",
            amount_total=Decimal("150"),
            amount_paid=Decimal("50"),
            idempotency_key="reservation-request-1",
            request_hash="a" * 64,
            created_at=NOW,
        ),
        VisitorEvent(
            id="event-1",
            tenant_id="tenant-1",
            visitor_id="visitor-1",
            session_id="session-1",
            event_type="strategic_campaign_view",
            metadata_json='{"campaign_id":"campaign-1"}',
            created_at=NOW,
        ),
        VisitorEvent(
            id="event-2",
            tenant_id="tenant-1",
            visitor_id="visitor-1",
            session_id="session-1",
            event_type="strategic_campaign_offer_click",
            metadata_json='{"campaign_id":"campaign-1"}',
            created_at=NOW,
        ),
        # Same external identifiers in another tenant must never leak.
        AdDailyMetric(
            id="ad-other",
            tenant_id="tenant-2",
            traffic_campaign_id="traffic-1",
            platform="meta",
            metric_date=DATE_TO,
            spend=999,
            impressions=999,
            clicks=999,
            conversions=999,
        ),
        VisitorEvent(
            id="event-other",
            tenant_id="tenant-2",
            visitor_id="visitor-other",
            session_id="session-other",
            event_type="strategic_campaign_view",
            metadata_json='{"campaign_id":"campaign-1"}',
            created_at=NOW,
        ),
    ])
    db.commit()

    result = StrategicCampaignMetricsService(db, "tenant-1").get("campaign-1", DATE_FROM, DATE_TO)

    assert result["funnel"] == {
        "views": 1,
        "offer_clicks": 1,
        "offer_scrolls": 0,
        "checkout_starts": 0,
        "visitors": 1,
        "sessions": 1,
        "paid_orders": 1,
    }
    assert result["commercial"] == {
        "paid_orders": 1,
        "revenue": 200.0,
        "average_ticket": 200.0,
        "scheduled_paid_orders": 1,
        "pizzas_sold": 2,
    }
    assert result["marketing"]["spend"] == 20.0
    assert result["marketing"]["ctr"] == 10.0
    assert result["marketing"]["cpc"] == 0.2
    assert result["marketing"]["cpa"] == 20.0
    assert result["roas"] == 10.0
    assert result["financial"] == {
        "cmv": 80.0,
        "cmv_complete": True,
        "gross_margin": 120.0,
        "media_cost": 20.0,
        "invested_cost": 100.0,
        "result": 100.0,
        "roi": 100.0,
    }
    assert result["operational"]["capacity_available"] == 7
    assert result["operational"]["capacity_utilization_rate"] == 30.0
    assert result["operational"]["reserved_quantity"] == 3
    assert result["operational"]["prepaid_value"] == 50.0


def test_c8_uses_null_for_unavailable_media_and_capacity(db):
    _campaign(db, traffic_id=None)
    result = StrategicCampaignMetricsService(db, "tenant-1").get("campaign-1", DATE_FROM, DATE_TO)

    assert result["spend"] is None
    assert result["roas"] is None
    assert result["marketing"]["impressions"] is None
    assert result["marketing"]["data_available"] is False
    assert result["financial"]["result"] is None
    assert result["financial"]["roi"] is None
    assert result["operational"]["capacity_total"] is None
    assert result["operational"]["capacity_utilization_rate"] is None


def test_c8_missing_cmv_does_not_invent_margin_or_roi(db):
    _campaign(db)
    _paid_order(db)
    db.add(AdDailyMetric(
        id="ad-1",
        tenant_id="tenant-1",
        traffic_campaign_id="traffic-1",
        platform="meta",
        metric_date=DATE_TO,
        spend=20,
    ))
    db.commit()

    result = StrategicCampaignMetricsService(db, "tenant-1").get("campaign-1", DATE_FROM, DATE_TO)

    assert result["revenue"] == 200.0
    assert result["financial"]["cmv"] is None
    assert result["financial"]["gross_margin"] is None
    assert result["financial"]["result"] is None
    assert result["financial"]["roi"] is None
    assert any("CMV incompleto" in warning for warning in result["data_quality"]["warnings"])


def test_c8_external_media_projection_failure_is_non_blocking(db, monkeypatch):
    _campaign(db)
    service = StrategicCampaignMetricsService(db, "tenant-1")

    def unavailable(*_args, **_kwargs):
        raise SQLAlchemyError("collector projection unavailable")

    monkeypatch.setattr(service, "_media_metrics", unavailable)
    result = service.get("campaign-1", DATE_FROM, DATE_TO)

    assert result["revenue"] == 0
    assert result["spend"] is None
    assert result["data_quality"]["external_sources_non_blocking"] is True
    assert any("Falha ao consultar" in warning for warning in result["data_quality"]["warnings"])


def test_c8_rejects_cross_tenant_campaign_and_invalid_period(db):
    _campaign(db)
    with pytest.raises(LookupError):
        StrategicCampaignMetricsService(db, "tenant-2").get("campaign-1", DATE_FROM, DATE_TO)
    with pytest.raises(ValueError):
        StrategicCampaignMetricsService(db, "tenant-1").get("campaign-1", DATE_TO, DATE_FROM)

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.main  # noqa: F401 - load the complete SQLAlchemy registry
from backend.core.exceptions import DomainError
from backend.database import Base
from backend.models.order import Order, OrderItem, OrderStatus
from backend.models.strategic_campaign import StrategicCapacitySlot, StrategicReservation
from backend.schemas.strategic_campaign_capacity import StrategicReservationRelease
from backend.services.strategic_campaign_capacity_service import StrategicCampaignCapacityService


NOW = datetime.now(timezone.utc).replace(microsecond=0)
TENANT = "tenant-c7"


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[
            Order.__table__,
            OrderItem.__table__,
            StrategicCapacitySlot.__table__,
            StrategicReservation.__table__,
        ],
    )
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def _slot_and_reservation(db, *, reservation_id="reservation-c7", status="confirmed"):
    slot = StrategicCapacitySlot(
        id="slot-c7",
        tenant_id=TENANT,
        campaign_id="campaign-c7",
        offer_id="offer-c7",
        offer_scope="offer-c7",
        starts_at=NOW - timedelta(minutes=30),
        ends_at=NOW + timedelta(minutes=30),
        capacity_total=2,
        capacity_used=1,
        blocked=False,
    )
    reservation = StrategicReservation(
        id=reservation_id,
        tenant_id=TENANT,
        campaign_id="campaign-c7",
        offer_id="offer-c7",
        slot_id=slot.id,
        customer_reference="customer-c7",
        quantity=1,
        status=status,
        payment_mode="full",
        amount_total=Decimal("50.00"),
        amount_paid=Decimal("50.00"),
        idempotency_key=f"key-{reservation_id}",
        request_hash="a" * 64,
        confirmed_at=NOW - timedelta(hours=1),
    )
    db.add_all([slot, reservation])
    db.commit()
    return slot, reservation


def _scheduled_order(db, *, order_id="order-c7", scheduled_for=NOW - timedelta(minutes=1)):
    order = Order(
        id=order_id,
        tenant_id=TENANT,
        status=OrderStatus.paid,
        strategic_campaign_id="campaign-c7",
        strategic_offer_id="offer-c7",
        strategic_offer_snapshot={"campaign": {"id": "campaign-c7"}},
        subtotal=50,
        total=50,
        is_scheduled=True,
        scheduled_for=scheduled_for,
        fulfillment_type="pickup",
        order_origin="own",
        sales_channel="delivery",
    )
    item = OrderItem(
        id=f"item-{order_id}",
        tenant_id=TENANT,
        order_id=order.id,
        product_id="product-c7",
        position=0,
        quantity=1,
        selected_size="Unico",
        unit_price=50,
        total_price=50,
        add_ons=[],
        option_selections=[],
        customizations=[],
    )
    db.add_all([order, item])
    db.commit()
    return order


def test_confirmed_reservation_binds_once_to_matching_canonical_order(db):
    _, reservation = _slot_and_reservation(db)
    order = _scheduled_order(db)
    service = StrategicCampaignCapacityService(db, TENANT)

    bound = service.bind_confirmed_order(reservation.id, order.id)
    replay = service.bind_confirmed_order(reservation.id, order.id)

    assert bound.order_id == order.id
    assert replay.order_id == order.id
    db.refresh(order)
    assert order.strategic_offer_snapshot["reservation"]["id"] == reservation.id


def test_binding_fails_closed_for_wrong_offer_and_wrong_tenant(db):
    _, reservation = _slot_and_reservation(db)
    order = _scheduled_order(db)
    order.strategic_offer_id = "other-offer"
    db.commit()

    with pytest.raises(DomainError) as mismatch:
        StrategicCampaignCapacityService(db, TENANT).bind_confirmed_order(reservation.id, order.id)
    assert mismatch.value.code == "StrategicReservationOrderMismatch"

    with pytest.raises(DomainError) as cross_tenant:
        StrategicCampaignCapacityService(db, "other-tenant").bind_confirmed_order(reservation.id, order.id)
    assert cross_tenant.value.code == "StrategicReservationNotFound"


def test_due_release_uses_canonical_kds_once(monkeypatch, db):
    _, reservation = _slot_and_reservation(db)
    order = _scheduled_order(db)
    service = StrategicCampaignCapacityService(db, TENANT)
    service.bind_confirmed_order(reservation.id, order.id)
    calls = []

    def fake_start_preparation(kds, order_id, *, actor_id, station_id="pizza"):
        calls.append((order_id, actor_id, station_id))
        current = db.query(Order).filter(Order.id == order_id).one()
        current.status = OrderStatus.preparing
        current.preparation_started_at = NOW
        db.commit()
        return {"id": order_id}

    monkeypatch.setattr(
        "backend.services.kds_service.KdsService.start_preparation",
        fake_start_preparation,
    )

    first = service.release_due_orders(actor_id="scheduler-c7", now=NOW)
    second = service.release_due_orders(actor_id="scheduler-c7", now=NOW + timedelta(minutes=1))

    assert [row.id for row in first] == [reservation.id]
    assert second == []
    assert calls == [(order.id, "scheduler-c7", "pizza")]
    db.refresh(reservation)
    released_at = reservation.operational_released_at
    if released_at.tzinfo is None:  # SQLite drops timezone metadata.
        released_at = released_at.replace(tzinfo=timezone.utc)
    assert released_at == NOW


def test_future_or_unpaid_order_is_not_released(monkeypatch, db):
    _, reservation = _slot_and_reservation(db)
    order = _scheduled_order(db, scheduled_for=NOW + timedelta(minutes=10))
    StrategicCampaignCapacityService(db, TENANT).bind_confirmed_order(reservation.id, order.id)
    monkeypatch.setattr(
        "backend.services.kds_service.KdsService.start_preparation",
        lambda *args, **kwargs: pytest.fail("future order must not reach KDS"),
    )

    assert StrategicCampaignCapacityService(db, TENANT).release_due_orders(now=NOW) == []
    order.scheduled_for = NOW - timedelta(minutes=1)
    order.status = OrderStatus.waiting_payment
    db.commit()
    assert StrategicCampaignCapacityService(db, TENANT).release_due_orders(now=NOW) == []


def test_active_bound_order_blocks_manual_capacity_release_and_cancel_returns_once(db):
    slot, reservation = _slot_and_reservation(db)
    order = _scheduled_order(db)
    service = StrategicCampaignCapacityService(db, TENANT)
    service.bind_confirmed_order(reservation.id, order.id)

    with pytest.raises(DomainError) as active:
        service.release_reservation(
            reservation.id,
            StrategicReservationRelease(reason="manual", cancelled=True),
            now=NOW,
        )
    assert active.value.code == "StrategicReservationHasActiveOrder"

    order.status = OrderStatus.cancelled
    db.commit()
    service.release_for_cancelled_order(order.id, now=NOW)
    service.release_for_cancelled_order(order.id, now=NOW + timedelta(minutes=1))

    db.refresh(slot)
    db.refresh(reservation)
    assert reservation.status == "cancelled"
    assert slot.capacity_used == 0

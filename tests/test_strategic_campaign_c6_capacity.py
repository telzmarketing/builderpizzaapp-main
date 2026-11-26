from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.main  # noqa: F401 - load the complete SQLAlchemy registry
from backend.core.exceptions import (
    DomainError,
    StrategicCapacityConflict,
    StrategicReservationIdempotencyConflict,
)
from backend.database import Base
from backend.models.strategic_campaign import (
    StrategicCampaign,
    StrategicCampaignStatus,
    StrategicCapacitySlot,
    StrategicReservation,
)
from backend.schemas.strategic_campaign_capacity import (
    StrategicCapacitySlotCreate,
    StrategicCapacitySlotUpdate,
    StrategicReservationCreate,
    StrategicReservationRelease,
)
from backend.services.strategic_campaign_capacity_service import StrategicCampaignCapacityService


NOW = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)


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
            StrategicCampaign.__table__,
            StrategicCapacitySlot.__table__,
            StrategicReservation.__table__,
        ],
    )
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def _campaign(db, campaign_id="campaign-1", tenant_id="tenant-1"):
    row = StrategicCampaign(
        id=campaign_id,
        tenant_id=tenant_id,
        name="Natal antecipado",
        slug=f"natal-{campaign_id}",
        status=StrategicCampaignStatus.draft,
        visual_config={},
        commercial_config={"sales_mode": "preorder"},
        marketing_config={},
        starts_at=NOW - timedelta(days=1),
        ends_at=NOW + timedelta(days=30),
    )
    db.add(row)
    db.commit()
    return row


def _slot(service, campaign_id="campaign-1", capacity=2):
    return service.create_slot(
        campaign_id,
        StrategicCapacitySlotCreate(
            label="Almoco",
            starts_at=NOW + timedelta(hours=1),
            ends_at=NOW + timedelta(hours=2),
            capacity_total=capacity,
        ),
    )


def _reservation(slot_id, key, *, quantity=1, customer="customer-1", hold_minutes=15):
    return StrategicReservationCreate(
        slot_id=slot_id,
        customer_reference=customer,
        quantity=quantity,
        payment_mode="no_payment",
        amount_total=Decimal("50.00"),
        amount_paid=Decimal("0"),
        hold_minutes=hold_minutes,
        idempotency_key=key,
    )


def test_last_slot_capacity_cannot_be_reserved_twice(db):
    _campaign(db)
    service = StrategicCampaignCapacityService(db, "tenant-1")
    slot = _slot(service, capacity=1)

    first = service.create_reservation("campaign-1", _reservation(slot.id, "request-0001"), now=NOW)
    assert first.status == "held"

    with pytest.raises(StrategicCapacityConflict) as error:
        service.create_reservation("campaign-1", _reservation(slot.id, "request-0002", customer="customer-2"), now=NOW)

    assert error.value.code == "StrategicCapacityExhausted"
    db.refresh(slot)
    assert slot.capacity_used == 1
    assert db.query(StrategicReservation).count() == 1


def test_reservation_creation_is_tenant_scoped_and_idempotent(db):
    _campaign(db)
    service = StrategicCampaignCapacityService(db, "tenant-1")
    slot = _slot(service)
    payload = _reservation(slot.id, "request-1001")

    first = service.create_reservation("campaign-1", payload, now=NOW)
    replay = service.create_reservation("campaign-1", payload, now=NOW)

    assert replay.id == first.id
    db.refresh(slot)
    assert slot.capacity_used == 1

    conflicting = payload.model_copy(update={"quantity": 2})
    with pytest.raises(StrategicReservationIdempotencyConflict):
        service.create_reservation("campaign-1", conflicting, now=NOW)

    with pytest.raises(DomainError) as cross_tenant:
        StrategicCampaignCapacityService(db, "tenant-2").create_reservation("campaign-1", payload, now=NOW)
    assert cross_tenant.value.code == "StrategicCampaignNotFound"


def test_expiration_releases_capacity_once_and_allows_new_hold(db):
    _campaign(db)
    service = StrategicCampaignCapacityService(db, "tenant-1")
    slot = _slot(service, capacity=1)
    expired = service.create_reservation(
        "campaign-1",
        _reservation(slot.id, "request-2001", hold_minutes=1),
        now=NOW,
    )

    ids = service.expire_due("campaign-1", now=NOW + timedelta(minutes=2))
    assert ids == [expired.id]
    assert service.expire_due("campaign-1", now=NOW + timedelta(minutes=3)) == []
    db.refresh(slot)
    db.refresh(expired)
    assert expired.status == "expired"
    assert slot.capacity_used == 0

    replacement = service.create_reservation(
        "campaign-1",
        _reservation(slot.id, "request-2002", customer="customer-2"),
        now=NOW + timedelta(minutes=3),
    )
    assert replacement.status == "held"
    db.refresh(slot)
    assert slot.capacity_used == 1


def test_confirmation_and_release_are_safe_and_idempotent(db):
    _campaign(db)
    service = StrategicCampaignCapacityService(db, "tenant-1")
    slot = _slot(service, capacity=3)
    reservation = service.create_reservation(
        "campaign-1",
        _reservation(slot.id, "request-3001", quantity=2),
        now=NOW,
    )

    confirmed = service.confirm_reservation(reservation.id, now=NOW + timedelta(minutes=1))
    assert confirmed.status == "confirmed"
    assert confirmed.expires_at is None
    assert service.confirm_reservation(reservation.id, now=NOW + timedelta(minutes=2)).id == reservation.id

    released = service.release_reservation(
        reservation.id,
        StrategicReservationRelease(reason="Cancelamento administrativo", cancelled=True),
        now=NOW + timedelta(minutes=3),
    )
    replay = service.release_reservation(
        reservation.id,
        StrategicReservationRelease(reason="Repeticao segura", cancelled=True),
        now=NOW + timedelta(minutes=4),
    )
    assert released.status == "cancelled"
    assert replay.status == "cancelled"
    db.refresh(slot)
    assert slot.capacity_used == 0


def test_slot_cannot_be_reduced_below_active_usage(db):
    _campaign(db)
    service = StrategicCampaignCapacityService(db, "tenant-1")
    slot = _slot(service, capacity=3)
    service.create_reservation(
        "campaign-1",
        _reservation(slot.id, "request-4001", quantity=2),
        now=NOW,
    )

    with pytest.raises(StrategicCapacityConflict) as error:
        service.update_slot(slot.id, StrategicCapacitySlotUpdate(capacity_total=1))
    assert error.value.code == "StrategicCapacityBelowUsage"


def test_payment_modes_are_validated_by_schema():
    base = {
        "slot_id": "slot-1",
        "customer_reference": "customer-1",
        "quantity": 1,
        "amount_total": Decimal("100.00"),
        "hold_minutes": 15,
        "idempotency_key": "request-5001",
    }
    StrategicReservationCreate(**base, payment_mode="no_payment", amount_paid=Decimal("0"))
    StrategicReservationCreate(**base, payment_mode="partial", amount_paid=Decimal("25.00"))
    StrategicReservationCreate(**base, payment_mode="full", amount_paid=Decimal("100.00"))

    with pytest.raises(ValidationError):
        StrategicReservationCreate(**base, payment_mode="partial", amount_paid=Decimal("100.00"))
    with pytest.raises(ValidationError):
        StrategicReservationCreate(**base, payment_mode="full", amount_paid=Decimal("90.00"))

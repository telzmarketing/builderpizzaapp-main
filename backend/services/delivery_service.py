"""
DeliveryService — all delivery operations are centralized here.

RULE: no route or ERP integration may change delivery.status or
      delivery_person.status directly. Every change goes through
      DeliveryService which enforces the delivery state machine,
      keeps the order status in sync, and updates motoboy availability.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.core.exceptions import (
    DeliveryNotFound, DeliveryPersonNotFound, DeliveryPersonUnavailable,
    OrderNotReadyForDelivery, DeliveryAlreadyAssigned, OrderNotFound,
)
from backend.core.state_machine import delivery_sm, order_sm
from backend.core.events import (
    bus, DeliveryAssigned, DeliveryStatusChanged, DeliveryCompleted,
)
from backend.models.delivery import (
    Delivery, DeliveryPerson, DeliveryStatus, DeliveryPersonStatus,
)
from backend.models.order import Order, OrderStatus


class DeliveryService:
    """
    Single authority for delivery assignment, tracking, and completion.

    Both the loja REST API and the ERP use this class.
    """

    def __init__(self, db: Session):
        self._db = db

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_delivery(self, delivery_id: str) -> Delivery:
        d = self._db.query(Delivery).filter(Delivery.id == delivery_id).first()
        if not d:
            raise DeliveryNotFound(delivery_id)
        return d

    def _get_delivery_person(self, person_id: str) -> DeliveryPerson:
        p = (
            self._db.query(DeliveryPerson)
            .filter(DeliveryPerson.id == person_id, DeliveryPerson.active == True)  # noqa: E712
            .first()
        )
        if not p:
            raise DeliveryPersonNotFound(person_id)
        return p

    def _get_order(self, order_id: str) -> Order:
        o = self._db.query(Order).filter(Order.id == order_id).first()
        if not o:
            raise OrderNotFound(order_id)
        return o

    # ── Assign ────────────────────────────────────────────────────────────────

    # Status that allow a motoboy to be assigned.
    # 'preparing'       → kitchen confirmed production, direct dispatch.
    # 'ready_for_pickup'→ optional checkpoint: pizza on the counter, motoboy picks up.
    _ASSIGNABLE_STATUSES = {OrderStatus.preparing, OrderStatus.ready_for_pickup}

    def assign(
        self,
        order_id: str,
        delivery_person_id: str,
        *,
        estimated_minutes: int = 40,
    ) -> Delivery:
        """
        Assign a delivery person to an order.

        Requirements:
        - Order must be in 'preparing' or 'ready_for_pickup' status.
          (cannot assign before payment is confirmed — state machine enforces this)
        - Delivery person must be active and available.
        - No existing active delivery assignment for this order.

        On success:
        - Order advances to 'on_the_way' via order state machine.
        - Delivery person status changes to 'busy'.
        - DeliveryAssigned event is published.
        """
        order = self._get_order(order_id)

        if order.status not in self._ASSIGNABLE_STATUSES:
            raise OrderNotReadyForDelivery(order_id, order.status.value)

        # Check for existing delivery
        existing = (
            self._db.query(Delivery)
            .filter(Delivery.order_id == order_id)
            .first()
        )
        if existing and existing.status not in (
            DeliveryStatus.failed, DeliveryStatus.cancelled
        ):
            raise DeliveryAlreadyAssigned(order_id)

        person = self._get_delivery_person(delivery_person_id)
        if person.status == DeliveryPersonStatus.busy:
            raise DeliveryPersonUnavailable(delivery_person_id)

        now = datetime.now(timezone.utc)

        # Create or reuse delivery record
        if existing:
            delivery = existing
            delivery.delivery_person_id = delivery_person_id
            delivery.status = DeliveryStatus.assigned
            delivery.assigned_at = now
            delivery.estimated_minutes = estimated_minutes
        else:
            delivery = Delivery(
                id=str(uuid.uuid4()),
                order_id=order_id,
                delivery_person_id=delivery_person_id,
                status=DeliveryStatus.assigned,
                assigned_at=now,
                estimated_minutes=estimated_minutes,
            )
            self._db.add(delivery)

        # Mark motoboy as busy
        person.status = DeliveryPersonStatus.busy

        # Advance order to 'on_the_way'
        order_sm.transition(order_id, order.status.value, "on_the_way")
        order.status = OrderStatus.on_the_way
        order.updated_at = now

        self._db.commit()
        self._db.refresh(delivery)

        bus.publish(DeliveryAssigned(
            delivery_id=delivery.id,
            order_id=order_id,
            delivery_person_id=delivery_person_id,
            delivery_person_name=person.name,
            estimated_minutes=estimated_minutes,
        ))

        return delivery

    # ── Status updates ────────────────────────────────────────────────────────

    def update_status(self, delivery_id: str, new_status: str) -> Delivery:
        """
        Advance a delivery through its state machine.

        Valid transitions:
          assigned → picked_up → on_the_way → delivered → completed
          any → failed | cancelled
        """
        delivery = self._get_delivery(delivery_id)
        old_status = delivery.status.value

        delivery_sm.transition(delivery_id, old_status, new_status)

        now = datetime.now(timezone.utc)
        delivery.status = DeliveryStatus(new_status)

        if new_status == "picked_up":
            delivery.picked_up_at = now

        elif new_status == "delivered":
            delivery.delivered_at = now
            # Order advances to 'delivered'
            order = self._get_order(delivery.order_id)
            if order:
                order_sm.transition(delivery.order_id, order.status.value, "delivered")
                order.status = OrderStatus.delivered
                order.updated_at = now

                # Award loyalty points
                if order.customer_id:
                    from backend.services.loyalty_service import award_points_for_order
                    points = award_points_for_order(
                        order.customer_id, delivery.order_id, order.total, self._db
                    )
                    order.loyalty_points_earned = points

        elif new_status in ("failed", "cancelled"):
            # Free up the delivery person
            if delivery.delivery_person_id:
                person = (
                    self._db.query(DeliveryPerson)
                    .filter(DeliveryPerson.id == delivery.delivery_person_id)
                    .first()
                )
                if person:
                    person.status = DeliveryPersonStatus.available

        self._db.commit()
        self._db.refresh(delivery)

        bus.publish(DeliveryStatusChanged(
            delivery_id=delivery_id,
            order_id=delivery.order_id,
            from_status=old_status,
            to_status=new_status,
        ))

        return delivery

    def complete(
        self,
        delivery_id: str,
        *,
        recipient_name: str | None = None,
        delivery_photo_url: str | None = None,
        notes: str | None = None,
    ) -> Delivery:
        """
        Mark delivery as completed (after 'delivered').
        Records proof-of-delivery fields and frees the motoboy.
        """
        delivery = self._get_delivery(delivery_id)

        delivery_sm.transition(delivery_id, delivery.status.value, "completed")
        delivery.status = DeliveryStatus.completed
        if recipient_name:
            delivery.recipient_name = recipient_name
        if delivery_photo_url:
            delivery.delivery_photo_url = delivery_photo_url
        if notes:
            delivery.notes = notes

        # Free up the delivery person and update stats
        duration_minutes = 0
        if delivery.delivery_person_id:
            person = (
                self._db.query(DeliveryPerson)
                .filter(DeliveryPerson.id == delivery.delivery_person_id)
                .first()
            )
            if person:
                person.status = DeliveryPersonStatus.available
                person.total_deliveries = (person.total_deliveries or 0) + 1

        if delivery.assigned_at and delivery.delivered_at:
            delta = delivery.delivered_at - delivery.assigned_at
            duration_minutes = int(delta.total_seconds() / 60)

        self._db.commit()
        self._db.refresh(delivery)

        bus.publish(DeliveryCompleted(
            delivery_id=delivery_id,
            order_id=delivery.order_id,
            delivery_person_id=delivery.delivery_person_id or "",
            duration_minutes=duration_minutes,
        ))

        return delivery

    def rate(self, delivery_id: str, rating: int, comment: str | None = None) -> Delivery:
        """Record customer rating (1–5) for a completed delivery."""
        delivery = self._get_delivery(delivery_id)
        if delivery.status not in (DeliveryStatus.delivered, DeliveryStatus.completed):
            raise DeliveryNotFound(delivery_id)  # not eligible, reuse 404

        delivery.rating = max(1, min(5, rating))
        delivery.rating_comment = comment

        # Update running average on delivery person
        if delivery.delivery_person_id:
            person = (
                self._db.query(DeliveryPerson)
                .filter(DeliveryPerson.id == delivery.delivery_person_id)
                .first()
            )
            if person and person.total_deliveries:
                old_avg = person.average_rating or 5.0
                n = person.total_deliveries
                person.average_rating = round(((old_avg * (n - 1)) + rating) / n, 2)

        self._db.commit()
        self._db.refresh(delivery)
        return delivery

    # ── Location update (mobile app) ──────────────────────────────────────────

    def update_location(
        self,
        delivery_person_id: str,
        lat: float,
        lng: float,
    ) -> DeliveryPerson:
        """Update real-time GPS coordinates for a delivery person."""
        person = (
            self._db.query(DeliveryPerson)
            .filter(DeliveryPerson.id == delivery_person_id)
            .first()
        )
        if not person:
            raise DeliveryPersonNotFound(delivery_person_id)

        person.location_lat = lat
        person.location_lng = lng
        person.location_updated_at = datetime.now(timezone.utc)
        self._db.commit()
        self._db.refresh(person)
        return person

    # ── Queries ───────────────────────────────────────────────────────────────

    def get(self, delivery_id: str) -> Delivery:
        return self._get_delivery(delivery_id)

    def get_by_order(self, order_id: str) -> Delivery:
        d = self._db.query(Delivery).filter(Delivery.order_id == order_id).first()
        if not d:
            raise DeliveryNotFound(order_id)
        return d

    def list_active(self) -> list[Delivery]:
        """Return deliveries currently in progress."""
        return (
            self._db.query(Delivery)
            .filter(
                Delivery.status.in_([
                    DeliveryStatus.assigned,
                    DeliveryStatus.picked_up,
                    DeliveryStatus.on_the_way,
                ])
            )
            .all()
        )

    # ── Delivery Person CRUD ──────────────────────────────────────────────────

    def list_persons(self, *, available_only: bool = False) -> list[DeliveryPerson]:
        q = self._db.query(DeliveryPerson).filter(DeliveryPerson.active == True)  # noqa: E712
        if available_only:
            q = q.filter(DeliveryPerson.status == DeliveryPersonStatus.available)
        return q.order_by(DeliveryPerson.name).all()

    def get_person(self, person_id: str) -> DeliveryPerson:
        return self._get_delivery_person(person_id)

    def create_person(
        self,
        name: str,
        phone: str,
        vehicle_type: str = "motorcycle",
    ) -> DeliveryPerson:
        from backend.models.delivery import VehicleType
        person = DeliveryPerson(
            id=str(uuid.uuid4()),
            name=name,
            phone=phone,
            vehicle_type=VehicleType(vehicle_type),
            status=DeliveryPersonStatus.offline,
            active=True,
        )
        self._db.add(person)
        self._db.commit()
        self._db.refresh(person)
        return person

    def set_person_status(self, person_id: str, status: str) -> DeliveryPerson:
        """Set availability status (available / offline). Use update_status for busy."""
        person = self._get_delivery_person(person_id)
        if status not in ("available", "offline"):
            raise ValueError(f"Invalid status '{status}'. Use 'available' or 'offline'.")
        person.status = DeliveryPersonStatus(status)
        self._db.commit()
        self._db.refresh(person)
        return person

    def deactivate_person(self, person_id: str) -> None:
        """Soft-delete a delivery person."""
        person = self._get_delivery_person(person_id)
        person.active = False
        self._db.commit()

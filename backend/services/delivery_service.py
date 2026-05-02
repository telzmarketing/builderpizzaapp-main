"""
DeliveryService — all delivery operations are centralized here.

RULE: no route or ERP integration may change delivery.status or
      delivery_person.status directly. Every change goes through
      DeliveryService which enforces the delivery state machine,
      keeps the order status in sync, and updates motoboy availability.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
from passlib.context import CryptContext

from backend.core.exceptions import (
    DeliveryNotFound, DeliveryPersonNotFound, DeliveryPersonUnavailable,
    OrderNotReadyForDelivery, DeliveryAlreadyAssigned, OrderNotFound,
    DomainError,
)
from backend.core.state_machine import delivery_sm, order_sm
from backend.core.events import (
    bus, DeliveryAssigned, DeliveryStatusChanged, DeliveryCompleted,
)
from backend.models.delivery import (
    Delivery, DeliveryEvent, DeliveryEarning, DeliveryPerson, DeliveryStatus,
    DeliveryPersonStatus, LogisticsSettings, GeocodeCache,
)
from backend.models.order import Order, OrderStatus

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


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

        # Generate confirmation code
        code = "".join(random.choices("0123456789", k=4))

        # Create or reuse delivery record
        if existing:
            delivery = existing
            delivery.delivery_person_id = delivery_person_id
            delivery.status = DeliveryStatus.assigned
            delivery.assigned_at = now
            delivery.estimated_minutes = estimated_minutes
            delivery.confirmation_code = code
            delivery.confirmed_by_code_at = None
        else:
            delivery = Delivery(
                id=str(uuid.uuid4()),
                order_id=order_id,
                delivery_person_id=delivery_person_id,
                status=DeliveryStatus.assigned,
                assigned_at=now,
                estimated_minutes=estimated_minutes,
                confirmation_code=code,
            )
            self._db.add(delivery)

        # Mark motoboy as busy
        person.status = DeliveryPersonStatus.busy

        # Advance order to 'on_the_way'
        order_sm.transition(order_id, order.status.value, "on_the_way")
        order.status = OrderStatus.on_the_way
        order.updated_at = now

        self._db.flush()

        # Record assignment event
        event = DeliveryEvent(
            id=str(uuid.uuid4()),
            delivery_id=delivery.id,
            event_type="assigned",
            description=f"Motoboy {person.name} atribuído. Código de confirmação: {code}.",
        )
        self._db.add(event)

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
                    from backend.services.customer_metrics_service import sync_customer_order_metrics
                    points = award_points_for_order(
                        order.customer_id, delivery.order_id, order.total, self._db
                    )
                    order.loyalty_points_earned = points
                    sync_customer_order_metrics(self._db, order.customer_id)

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

        # Auto-create earnings record if rate_per_delivery is configured
        try:
            settings_row = self._db.query(LogisticsSettings).filter(LogisticsSettings.id == "default").first()
            rate = (getattr(settings_row, "rate_per_delivery", None) or 0.0) if settings_row else 0.0
            if rate > 0 and delivery.delivery_person_id:
                earning = DeliveryEarning(
                    id=str(uuid.uuid4()),
                    delivery_id=delivery.id,
                    delivery_person_id=delivery.delivery_person_id,
                    amount=rate,
                    status="pending",
                    period_date=datetime.now(timezone.utc).date(),
                )
                self._db.add(earning)
        except Exception:
            pass  # never fail completion due to earnings issue

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
        *,
        email: str | None = None,
        cpf: str | None = None,
        cnh: str | None = None,
        pix_key: str | None = None,
        password: str | None = None,
    ) -> DeliveryPerson:
        from backend.models.delivery import VehicleType
        person = DeliveryPerson(
            id=str(uuid.uuid4()),
            name=name,
            phone=phone,
            vehicle_type=VehicleType(vehicle_type),
            status=DeliveryPersonStatus.offline,
            active=True,
            email=email,
            cpf=cpf,
            cnh=cnh,
            pix_key=pix_key,
            password_hash=_pwd_ctx.hash(password) if password else None,
        )
        self._db.add(person)
        self._db.commit()
        self._db.refresh(person)
        return person

    def update_person(self, person_id: str, **kwargs) -> DeliveryPerson:
        """Update mutable fields on a delivery person."""
        person = self._get_delivery_person(person_id)
        for key, value in kwargs.items():
            if value is None:
                continue
            if key == "password":
                person.password_hash = _pwd_ctx.hash(value)
            elif key == "vehicle_type":
                from backend.models.delivery import VehicleType
                person.vehicle_type = VehicleType(value) if isinstance(value, str) else value
            elif hasattr(person, key):
                setattr(person, key, value)
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

    # ── Driver App ────────────────────────────────────────────────────────────

    def driver_login(self, email: str, password: str) -> DeliveryPerson:
        """Authenticate a driver by email + password."""
        person = (
            self._db.query(DeliveryPerson)
            .filter(DeliveryPerson.email == email, DeliveryPerson.active == True)  # noqa: E712
            .first()
        )
        if not person or not person.password_hash:
            raise DomainError("Credenciais inválidas.", code="InvalidCredentials")
        if not _pwd_ctx.verify(password, person.password_hash):
            raise DomainError("Credenciais inválidas.", code="InvalidCredentials")
        return person

    def get_driver_deliveries(self, person_id: str) -> list[Delivery]:
        """Return active + recent deliveries for a specific driver (with order eagerly loaded)."""
        from sqlalchemy.orm import joinedload
        return (
            self._db.query(Delivery)
            .options(joinedload(Delivery.order))
            .filter(
                Delivery.delivery_person_id == person_id,
                Delivery.status.notin_(["failed", "cancelled"]),
            )
            .order_by(Delivery.created_at.desc())
            .limit(20)
            .all()
        )

    def get_logistics_overview(self) -> dict:
        """Return all motoboys on duty with their active deliveries + order addresses."""
        from sqlalchemy.orm import joinedload
        active_statuses = [
            DeliveryStatus.assigned,
            DeliveryStatus.picked_up,
            DeliveryStatus.on_the_way,
        ]
        active_deliveries = (
            self._db.query(Delivery)
            .options(joinedload(Delivery.order))
            .filter(Delivery.status.in_(active_statuses))
            .all()
        )
        # Group by delivery_person_id
        from collections import defaultdict
        by_person: dict[str, list] = defaultdict(list)
        person_ids = set()
        for d in active_deliveries:
            if d.delivery_person_id:
                by_person[d.delivery_person_id].append(d)
                person_ids.add(d.delivery_person_id)

        # Fetch all busy persons (include those with no active delivery but status=busy)
        busy_persons = (
            self._db.query(DeliveryPerson)
            .filter(
                DeliveryPerson.active == True,  # noqa: E712
                DeliveryPerson.status == DeliveryPersonStatus.busy,
            )
            .all()
        )
        all_person_ids = person_ids | {p.id for p in busy_persons}
        all_persons_map = {p.id: p for p in busy_persons}
        # Also fetch persons referenced in active deliveries but not in busy list
        missing_ids = person_ids - set(all_persons_map.keys())
        if missing_ids:
            extra = (
                self._db.query(DeliveryPerson)
                .filter(DeliveryPerson.id.in_(list(missing_ids)))
                .all()
            )
            for p in extra:
                all_persons_map[p.id] = p

        persons_on_duty = []
        for pid in all_person_ids:
            person = all_persons_map.get(pid)
            if person:
                persons_on_duty.append({
                    "person": person,
                    "active_deliveries": by_person.get(pid, []),
                })

        return {
            "persons_on_duty": persons_on_duty,
            "total_active": len(active_deliveries),
        }

    def confirm_delivery_code(self, delivery_id: str, code: str) -> Delivery:
        """Driver submits 4-digit code to confirm delivery completion."""
        delivery = self._get_delivery(delivery_id)
        if delivery.confirmation_code != code:
            raise DomainError("Código de confirmação inválido.", code="InvalidCode")
        if delivery.confirmed_by_code_at:
            return delivery  # already confirmed — idempotent
        now = datetime.now(timezone.utc)
        delivery.confirmed_by_code_at = now

        event = DeliveryEvent(
            id=str(uuid.uuid4()),
            delivery_id=delivery_id,
            event_type="confirmed_by_code",
            description="Entrega confirmada pelo código de confirmação.",
        )
        self._db.add(event)

        # Add to customer_timeline if customer exists
        try:
            order = self._get_order(delivery.order_id)
            if order.customer_id:
                self._db.execute(
                    text(
                        "INSERT INTO customer_timeline (id, customer_id, event_type, title, description, created_at)"
                        " VALUES (:id, :cid, :et, :t, :d, NOW())"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "cid": order.customer_id,
                        "et": "delivery_confirmed",
                        "t": "Entrega confirmada",
                        "d": f"Entrega do pedido #{delivery.order_id[:8].upper()} confirmada.",
                    },
                )
        except Exception:
            pass

        self._db.commit()
        self._db.refresh(delivery)
        return delivery

    # ── Logistics Settings ────────────────────────────────────────────────────

    def get_logistics_settings(self) -> LogisticsSettings:
        settings = self._db.query(LogisticsSettings).filter(LogisticsSettings.id == "default").first()
        if not settings:
            settings = LogisticsSettings(id="default")
            self._db.add(settings)
            self._db.commit()
            self._db.refresh(settings)
        return settings

    def update_logistics_settings(self, **kwargs) -> LogisticsSettings:
        settings = self.get_logistics_settings()
        for key, value in kwargs.items():
            if value is not None and hasattr(settings, key):
                setattr(settings, key, value)
        self._db.commit()
        self._db.refresh(settings)
        return settings

    # ── Phase 3 — Earnings ────────────────────────────────────────────────────

    def list_earnings(
        self,
        person_id: str | None = None,
        status: str | None = None,
        period_from=None,
        period_to=None,
    ) -> list[dict]:
        """List earnings with optional filters. Returns plain dicts to avoid lazy-load issues."""
        from sqlalchemy.orm import joinedload
        q = (
            self._db.query(DeliveryEarning)
            .options(joinedload(DeliveryEarning.delivery_person))
        )
        if person_id:
            q = q.filter(DeliveryEarning.delivery_person_id == person_id)
        if status:
            q = q.filter(DeliveryEarning.status == status)
        if period_from:
            q = q.filter(DeliveryEarning.period_date >= period_from)
        if period_to:
            q = q.filter(DeliveryEarning.period_date <= period_to)

        earnings = q.order_by(DeliveryEarning.created_at.desc()).all()
        return [
            {
                "id": e.id,
                "delivery_id": e.delivery_id,
                "delivery_person_id": e.delivery_person_id,
                "person_name": e.delivery_person.name if e.delivery_person else None,
                "person_phone": e.delivery_person.phone if e.delivery_person else None,
                "amount": e.amount,
                "status": e.status,
                "period_date": str(e.period_date) if e.period_date else None,
                "paid_at": e.paid_at.isoformat() if e.paid_at else None,
                "paid_by": e.paid_by,
                "notes": e.notes,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in earnings
        ]

    def bulk_pay_earnings(self, earning_ids: list[str], paid_by: str = "admin") -> int:
        """Mark a list of earnings as paid. Returns count of earnings actually updated."""
        now = datetime.now(timezone.utc)
        paid_count = 0
        for eid in earning_ids:
            earning = (
                self._db.query(DeliveryEarning)
                .filter(DeliveryEarning.id == eid, DeliveryEarning.status == "pending")
                .first()
            )
            if earning:
                earning.status = "paid"
                earning.paid_at = now
                earning.paid_by = paid_by
                paid_count += 1
        if paid_count > 0:
            self._db.commit()
        return paid_count

    # ── Phase 3 — Analytics ───────────────────────────────────────────────────

    def get_analytics(
        self,
        period_from=None,
        period_to=None,
        person_id: str | None = None,
    ) -> list[dict]:
        """Per-driver performance stats for the given period."""
        persons = self.list_persons()
        result = []

        for person in persons:
            if person_id and person.id != person_id:
                continue

            dq = self._db.query(Delivery).filter(Delivery.delivery_person_id == person.id)
            if period_from:
                dq = dq.filter(Delivery.delivered_at >= period_from)
            if period_to:
                dq = dq.filter(Delivery.delivered_at <= period_to)
            deliveries_in_period = dq.all()

            completed = [
                d for d in deliveries_in_period
                if d.status in (DeliveryStatus.delivered, DeliveryStatus.completed)
            ]
            failed = [
                d for d in deliveries_in_period
                if d.status in (DeliveryStatus.failed, DeliveryStatus.cancelled)
            ]
            total = len(completed) + len(failed)

            durations = []
            for d in completed:
                if d.assigned_at and d.delivered_at:
                    a = d.assigned_at if d.assigned_at.tzinfo else d.assigned_at.replace(tzinfo=timezone.utc)
                    b = d.delivered_at if d.delivered_at.tzinfo else d.delivered_at.replace(tzinfo=timezone.utc)
                    durations.append((b - a).total_seconds() / 60)

            ratings = [d.rating for d in completed if d.rating is not None]

            eq = self._db.query(DeliveryEarning).filter(DeliveryEarning.delivery_person_id == person.id)
            if period_from:
                eq = eq.filter(DeliveryEarning.period_date >= period_from)
            if period_to:
                eq = eq.filter(DeliveryEarning.period_date <= period_to)
            earnings = eq.all()

            result.append({
                "person_id": person.id,
                "person_name": person.name,
                "person_phone": person.phone,
                "vehicle_type": person.vehicle_type.value,
                "total_deliveries": len(completed),
                "avg_duration_minutes": round(sum(durations) / len(durations), 1) if durations else None,
                "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
                "completion_rate": round(len(completed) / total * 100, 1) if total > 0 else 100.0,
                "pending_earnings": round(sum(e.amount for e in earnings if e.status == "pending"), 2),
                "paid_earnings": round(sum(e.amount for e in earnings if e.status == "paid"), 2),
            })

        return sorted(result, key=lambda x: x["total_deliveries"], reverse=True)

    # ── Phase 3 — Delay Alerts ────────────────────────────────────────────────

    def get_alerts(self) -> list[dict]:
        """Return active deliveries past their ETA, sorted by most overdue first."""
        from sqlalchemy.orm import joinedload
        now = datetime.now(timezone.utc)

        active = (
            self._db.query(Delivery)
            .options(joinedload(Delivery.delivery_person), joinedload(Delivery.order))
            .filter(
                Delivery.status.in_([
                    DeliveryStatus.assigned,
                    DeliveryStatus.picked_up,
                    DeliveryStatus.on_the_way,
                ]),
                Delivery.assigned_at.isnot(None),
            )
            .all()
        )

        alerts = []
        for d in active:
            if not d.assigned_at or not d.estimated_minutes:
                continue
            assigned = d.assigned_at
            if assigned.tzinfo is None:
                assigned = assigned.replace(tzinfo=timezone.utc)
            deadline = assigned + timedelta(minutes=d.estimated_minutes)
            if deadline < now:
                overdue_minutes = int((now - deadline).total_seconds() / 60)
                alerts.append({
                    "id": d.id,
                    "order_id": d.order_id,
                    "delivery_person_id": d.delivery_person_id,
                    "person_name": d.delivery_person.name if d.delivery_person else None,
                    "person_phone": d.delivery_person.phone if d.delivery_person else None,
                    "status": d.status.value,
                    "assigned_at": d.assigned_at.isoformat() if d.assigned_at else None,
                    "estimated_minutes": d.estimated_minutes,
                    "overdue_minutes": overdue_minutes,
                    "delivery_street": d.order.delivery_street if d.order else None,
                })

        return sorted(alerts, key=lambda x: x["overdue_minutes"], reverse=True)

    # ── Phase 4 — Auto-assignment ─────────────────────────────────────────────

    def auto_assign_pending(self) -> list[dict]:
        """
        Auto-assign available drivers to unassigned eligible orders.
        Only runs when auto_assign is enabled in logistics settings.
        Returns list of {order_id, delivery_id, person_name} for each assignment made.
        """
        settings = self.get_logistics_settings()
        if not settings.auto_assign:
            return []

        from sqlalchemy import func

        # Orders eligible for assignment
        eligible_orders = (
            self._db.query(Order)
            .filter(Order.status.in_([OrderStatus.ready_for_pickup, OrderStatus.preparing]))
            .all()
        )
        if not eligible_orders:
            return []

        # Orders that already have an active delivery
        active_order_ids = {
            row[0] for row in self._db.query(Delivery.order_id).filter(
                Delivery.status.notin_([DeliveryStatus.failed, DeliveryStatus.cancelled])
            ).all()
        }
        unassigned = [o for o in eligible_orders if o.id not in active_order_ids]
        if not unassigned:
            return []

        # Available drivers
        available = (
            self._db.query(DeliveryPerson)
            .filter(
                DeliveryPerson.active == True,  # noqa: E712
                DeliveryPerson.status == DeliveryPersonStatus.available,
            )
            .all()
        )
        if not available:
            return []

        # Active delivery counts per driver (single query)
        counts_raw = (
            self._db.query(Delivery.delivery_person_id, func.count(Delivery.id))
            .filter(Delivery.status.in_([
                DeliveryStatus.assigned,
                DeliveryStatus.picked_up,
                DeliveryStatus.on_the_way,
            ]))
            .group_by(Delivery.delivery_person_id)
            .all()
        )
        active_counts: dict[str, int] = {row[0]: row[1] for row in counts_raw}

        assigned = []
        for order in unassigned:
            eligible_drivers = [
                p for p in available
                if active_counts.get(p.id, 0) < settings.max_concurrent_deliveries
            ]
            if not eligible_drivers:
                break  # all drivers at capacity

            best = min(eligible_drivers, key=lambda p: active_counts.get(p.id, 0))
            try:
                delivery = self.assign(
                    order.id,
                    best.id,
                    estimated_minutes=settings.default_estimated_minutes,
                )
                active_counts[best.id] = active_counts.get(best.id, 0) + 1
                assigned.append({
                    "order_id": order.id,
                    "delivery_id": delivery.id,
                    "person_name": best.name,
                })
            except Exception:
                continue

        return assigned

    # ── Phase 4 — Geocoding ───────────────────────────────────────────────────

    def geocode_address(self, query: str) -> dict:
        """
        Geocode an address string via Nominatim (OpenStreetMap).
        Results are cached in the geocode_cache table — Nominatim is only
        called once per unique address, respecting their usage policy.
        """
        import hashlib
        import urllib.request
        import urllib.parse
        import json as _json

        cache_key = hashlib.sha256(query.lower().strip().encode()).hexdigest()[:32]
        cached = self._db.query(GeocodeCache).filter(GeocodeCache.id == cache_key).first()
        if cached:
            return {"lat": cached.lat, "lng": cached.lng, "cached": True}

        lat, lng = None, None
        try:
            url = (
                "https://nominatim.openstreetmap.org/search"
                f"?q={urllib.parse.quote(query)}&format=json&limit=1&countrycodes=br"
            )
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "MoschettieriDelivery/1.0"},
            )
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = _json.loads(resp.read())
            if data:
                lat = float(data[0]["lat"])
                lng = float(data[0]["lon"])
        except Exception:
            pass

        try:
            entry = GeocodeCache(id=cache_key, query=query, lat=lat, lng=lng)
            self._db.add(entry)
            self._db.commit()
        except Exception:
            self._db.rollback()

        return {"lat": lat, "lng": lng, "cached": False}

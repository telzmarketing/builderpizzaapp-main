from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.exceptions import (
    DomainError,
    StrategicCapacityConflict,
    StrategicReservationIdempotencyConflict,
)
from backend.models.strategic_campaign import (
    StrategicCampaign,
    StrategicCapacitySlot,
    StrategicOffer,
    StrategicReservation,
)
from backend.models.order import Order, OrderStatus
from backend.models.customer import Customer
from backend.models.store_operation import StoreOperationSettings
from backend.schemas.strategic_campaign_capacity import (
    StrategicCampaignAvailabilityDateOut,
    StrategicCampaignAvailabilityOut,
    StrategicCampaignAvailabilitySlotOut,
    StrategicCapacitySlotCreate,
    StrategicCapacitySlotUpdate,
    StrategicReservationCreate,
    StrategicReservationRelease,
)


ACTIVE_RESERVATION_STATUSES = ("held", "confirmed")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class StrategicCampaignCapacityService:
    """Tenant-scoped capacity and reservation transactions for strategic campaigns."""

    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def _campaign(self, campaign_id: str) -> StrategicCampaign:
        row = self.db.query(StrategicCampaign).filter(
            StrategicCampaign.tenant_id == self.tenant_id,
            StrategicCampaign.id == campaign_id,
        ).first()
        if row is None:
            raise DomainError("Campanha estrategica nao encontrada.", code="StrategicCampaignNotFound")
        return row

    def _offer(self, campaign_id: str, offer_id: str | None, *, lock: bool = False) -> StrategicOffer | None:
        if offer_id is None:
            return None
        query = self.db.query(StrategicOffer).filter(
            StrategicOffer.tenant_id == self.tenant_id,
            StrategicOffer.campaign_id == campaign_id,
            StrategicOffer.id == offer_id,
            StrategicOffer.archived_at.is_(None),
        )
        if lock:
            query = query.with_for_update()
        row = query.first()
        if row is None:
            raise DomainError("Oferta estrategica nao encontrada na campanha.", code="StrategicOfferNotFound")
        return row

    def _slot(self, slot_id: str, *, lock: bool = False) -> StrategicCapacitySlot:
        query = self.db.query(StrategicCapacitySlot).filter(
            StrategicCapacitySlot.tenant_id == self.tenant_id,
            StrategicCapacitySlot.id == slot_id,
        )
        if lock:
            query = query.with_for_update()
        row = query.first()
        if row is None:
            raise DomainError("Slot de capacidade nao encontrado.", code="StrategicCapacitySlotNotFound")
        return row

    def _reservation(self, reservation_id: str, *, lock: bool = False) -> StrategicReservation:
        query = self.db.query(StrategicReservation).filter(
            StrategicReservation.tenant_id == self.tenant_id,
            StrategicReservation.id == reservation_id,
        )
        if lock:
            query = query.with_for_update()
        row = query.first()
        if row is None:
            raise DomainError("Reserva estrategica nao encontrada.", code="StrategicReservationNotFound")
        return row

    @staticmethod
    def _request_hash(campaign_id: str, payload: StrategicReservationCreate) -> str:
        canonical = {"campaign_id": campaign_id, **payload.model_dump(mode="json")}
        raw = json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _assert_same_request(row: StrategicReservation, request_hash: str) -> None:
        if row.request_hash != request_hash:
            raise StrategicReservationIdempotencyConflict(
                "A chave de idempotencia ja foi usada com outro payload.",
                code="StrategicReservationIdempotencyConflict",
            )

    def list_slots(self, campaign_id: str) -> list[StrategicCapacitySlot]:
        self._campaign(campaign_id)
        return self.db.query(StrategicCapacitySlot).filter(
            StrategicCapacitySlot.tenant_id == self.tenant_id,
            StrategicCapacitySlot.campaign_id == campaign_id,
        ).order_by(StrategicCapacitySlot.starts_at, StrategicCapacitySlot.id).all()

    def public_availability(
        self,
        campaign_id: str,
        offer_id: str | None = None,
        *,
        now: datetime | None = None,
    ) -> StrategicCampaignAvailabilityOut:
        """Return public campaign dates and slots without changing database state.

        Expired holds are excluded from the calculated usage, but are not
        released here. Expiration remains owned by the reservation lifecycle.
        """
        from backend.services.strategic_campaign_service import StrategicCampaignService
        from backend.services.store_operation_service import StoreOperationService

        campaign = StrategicCampaignService(self.db, self.tenant_id).get_public_by_id(campaign_id)
        if offer_id is not None:
            self._offer(campaign_id, offer_id)

        generated_at = _as_utc(now or _utc_now())
        settings = self.db.query(StoreOperationSettings).filter(
            StoreOperationSettings.tenant_id == self.tenant_id,
        ).first()
        timezone_name = settings.timezone if settings else "America/Sao_Paulo"
        try:
            zone = ZoneInfo(timezone_name)
        except Exception:
            timezone_name = "America/Sao_Paulo"
            zone = ZoneInfo(timezone_name)

        slots = self.db.query(StrategicCapacitySlot).filter(
            StrategicCapacitySlot.tenant_id == self.tenant_id,
            StrategicCapacitySlot.campaign_id == campaign_id,
        )
        if campaign.ends_at:
            slots = slots.filter(StrategicCapacitySlot.starts_at < _as_utc(campaign.ends_at))
        if offer_id is not None:
            slots = slots.filter(
                (StrategicCapacitySlot.offer_id == offer_id)
                | StrategicCapacitySlot.offer_id.is_(None),
            )
        rows = slots.order_by(StrategicCapacitySlot.starts_at, StrategicCapacitySlot.id).all()

        reservations = self.db.query(StrategicReservation).filter(
            StrategicReservation.tenant_id == self.tenant_id,
            StrategicReservation.campaign_id == campaign_id,
            StrategicReservation.status.in_(ACTIVE_RESERVATION_STATUSES),
        ).all()
        used_by_slot: dict[str, int] = defaultdict(int)
        for reservation in reservations:
            if reservation.status == "held" and (
                reservation.expires_at is None or _as_utc(reservation.expires_at) <= generated_at
            ):
                continue
            if offer_id is None or reservation.offer_id in {None, offer_id}:
                used_by_slot[reservation.slot_id] += reservation.quantity

        schedule = StoreOperationService(self.db, self.tenant_id)
        grouped: dict[object, list[StrategicCampaignAvailabilitySlotOut]] = defaultdict(list)
        for slot in rows:
            starts_at = _as_utc(slot.starts_at)
            ends_at = _as_utc(slot.ends_at)
            if starts_at <= generated_at or ends_at <= generated_at:
                continue
            capacity_used = used_by_slot.get(slot.id, 0)
            remaining = max(0, slot.capacity_total - capacity_used)
            schedule_available = True
            if settings is not None:
                local_start = starts_at.astimezone(zone)
                schedule_available, _, _ = schedule._is_open_at(
                    local_start,
                    settings,
                    ignore_manual=True,
                )
            reason = None
            if slot.blocked:
                reason = "blocked"
            elif remaining <= 0:
                reason = "capacity_exhausted"
            elif not schedule_available:
                reason = "outside_store_schedule"
            item = StrategicCampaignAvailabilitySlotOut(
                id=slot.id,
                offer_id=slot.offer_id,
                label=slot.label,
                starts_at=starts_at,
                ends_at=ends_at,
                local_date=starts_at.astimezone(zone).date(),
                capacity_total=slot.capacity_total,
                capacity_used=capacity_used,
                remaining_capacity=remaining,
                blocked=slot.blocked,
                schedule_available=schedule_available,
                available=reason is None,
                unavailable_reason=reason,
            )
            grouped[item.local_date].append(item)

        return StrategicCampaignAvailabilityOut(
            campaign_id=campaign_id,
            offer_id=offer_id,
            timezone=timezone_name,
            generated_at=generated_at,
            dates=[
                StrategicCampaignAvailabilityDateOut(date=day, slots=items)
                for day, items in sorted(grouped.items())
            ],
        )

    def create_slot(self, campaign_id: str, payload: StrategicCapacitySlotCreate) -> StrategicCapacitySlot:
        campaign = self._campaign(campaign_id)
        self._offer(campaign_id, payload.offer_id)
        starts_at = _as_utc(payload.starts_at)
        ends_at = _as_utc(payload.ends_at)
        if campaign.starts_at and starts_at < _as_utc(campaign.starts_at):
            raise DomainError("O slot nao pode iniciar antes da campanha.", code="StrategicCapacitySlotOutsideCampaign")
        if campaign.ends_at and ends_at > _as_utc(campaign.ends_at):
            raise DomainError("O slot nao pode terminar depois da campanha.", code="StrategicCapacitySlotOutsideCampaign")
        row = StrategicCapacitySlot(
            id=f"scs-{uuid.uuid4().hex[:16]}",
            tenant_id=self.tenant_id,
            campaign_id=campaign_id,
            offer_id=payload.offer_id,
            offer_scope=payload.offer_id or "*",
            label=payload.label,
            starts_at=starts_at,
            ends_at=ends_at,
            capacity_total=payload.capacity_total,
            capacity_used=0,
            blocked=payload.blocked,
        )
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise StrategicCapacityConflict(
                "Ja existe um slot para a mesma campanha, oferta e horario.",
                code="StrategicCapacitySlotConflict",
            ) from exc
        self.db.refresh(row)
        return row

    def update_slot(self, slot_id: str, payload: StrategicCapacitySlotUpdate) -> StrategicCapacitySlot:
        row = self._slot(slot_id, lock=True)
        campaign = self._campaign(row.campaign_id)
        data = payload.model_dump(exclude_unset=True)
        starts_at = _as_utc(data.get("starts_at", row.starts_at))
        ends_at = _as_utc(data.get("ends_at", row.ends_at))
        if ends_at <= starts_at:
            raise DomainError("O fim do slot deve ser posterior ao inicio.", code="InvalidStrategicCapacitySlotPeriod")
        if campaign.starts_at and starts_at < _as_utc(campaign.starts_at):
            raise DomainError("O slot nao pode iniciar antes da campanha.", code="StrategicCapacitySlotOutsideCampaign")
        if campaign.ends_at and ends_at > _as_utc(campaign.ends_at):
            raise DomainError("O slot nao pode terminar depois da campanha.", code="StrategicCapacitySlotOutsideCampaign")
        capacity_total = data.get("capacity_total", row.capacity_total)
        if capacity_total < row.capacity_used:
            raise StrategicCapacityConflict(
                "A capacidade total nao pode ficar abaixo da capacidade ja ocupada.",
                code="StrategicCapacityBelowUsage",
            )
        data["starts_at"] = starts_at
        data["ends_at"] = ends_at
        for field, value in data.items():
            setattr(row, field, value)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise StrategicCapacityConflict(
                "A alteracao conflita com outro slot da campanha.",
                code="StrategicCapacitySlotConflict",
            ) from exc
        self.db.refresh(row)
        return row

    def list_reservations(self, campaign_id: str, status: str | None = None) -> list[StrategicReservation]:
        self._campaign(campaign_id)
        query = self.db.query(StrategicReservation).filter(
            StrategicReservation.tenant_id == self.tenant_id,
            StrategicReservation.campaign_id == campaign_id,
        )
        if status:
            query = query.filter(StrategicReservation.status == status)
        return query.order_by(StrategicReservation.created_at.desc(), StrategicReservation.id).all()

    def create_reservation(
        self,
        campaign_id: str,
        payload: StrategicReservationCreate,
        *,
        now: datetime | None = None,
    ) -> StrategicReservation:
        now = _as_utc(now or _utc_now())
        request_hash = self._request_hash(campaign_id, payload)
        existing = self.db.query(StrategicReservation).filter(
            StrategicReservation.tenant_id == self.tenant_id,
            StrategicReservation.idempotency_key == payload.idempotency_key,
        ).first()
        if existing:
            self._assert_same_request(existing, request_hash)
            return existing

        self._campaign(campaign_id)
        slot = self._slot(payload.slot_id, lock=True)
        if slot.campaign_id != campaign_id:
            raise DomainError("O slot nao pertence a campanha.", code="StrategicCapacitySlotCampaignMismatch")
        if slot.offer_id is not None and payload.offer_id != slot.offer_id:
            raise DomainError("A oferta da reserva nao corresponde ao slot.", code="StrategicReservationOfferMismatch")
        if payload.offer_id is not None:
            from backend.services.strategic_offer_composition_service import StrategicOfferCompositionService
            composition = StrategicOfferCompositionService(self.db, self.tenant_id)
            published_campaign, offer = composition._published_offer(payload.offer_id, None, lock=True)
            if published_campaign.id != campaign_id:
                raise DomainError("A oferta da reserva nao pertence a campanha.", code="StrategicReservationOfferMismatch")
            if offer.max_per_customer is not None and not self.db.query(Customer).filter(
                Customer.tenant_id == self.tenant_id,
                Customer.id == payload.customer_reference,
            ).first():
                raise DomainError(
                    "Esta oferta exige um cliente cadastrado para reservar.",
                    code="StrategicOfferCustomerRequired",
                )
            composition._assert_purchase_limits(offer, payload.quantity, payload.customer_reference)

        # Re-check after acquiring the slot lock. This closes the race between
        # two requests carrying the same tenant-scoped idempotency key.
        existing = self.db.query(StrategicReservation).filter(
            StrategicReservation.tenant_id == self.tenant_id,
            StrategicReservation.idempotency_key == payload.idempotency_key,
        ).first()
        if existing:
            self._assert_same_request(existing, request_hash)
            return existing

        self._expire_held_for_slot(slot, now)
        if slot.blocked:
            raise StrategicCapacityConflict("O slot esta bloqueado.", code="StrategicCapacitySlotBlocked")
        if _as_utc(slot.ends_at) <= now:
            raise StrategicCapacityConflict("O slot ja foi encerrado.", code="StrategicCapacitySlotEnded")
        if slot.capacity_used + payload.quantity > slot.capacity_total:
            raise StrategicCapacityConflict("Capacidade insuficiente para a reserva.", code="StrategicCapacityExhausted")

        row = StrategicReservation(
            id=f"scr-{uuid.uuid4().hex[:16]}",
            tenant_id=self.tenant_id,
            campaign_id=campaign_id,
            offer_id=payload.offer_id,
            slot_id=slot.id,
            customer_reference=payload.customer_reference,
            quantity=payload.quantity,
            status="held",
            payment_mode=payload.payment_mode,
            amount_total=payload.amount_total,
            amount_paid=payload.amount_paid,
            idempotency_key=payload.idempotency_key,
            request_hash=request_hash,
            expires_at=now + timedelta(minutes=payload.hold_minutes),
        )
        slot.capacity_used += payload.quantity
        self.db.add(row)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            existing = self.db.query(StrategicReservation).filter(
                StrategicReservation.tenant_id == self.tenant_id,
                StrategicReservation.idempotency_key == payload.idempotency_key,
            ).first()
            if existing:
                self._assert_same_request(existing, request_hash)
                return existing
            raise StrategicCapacityConflict(
                "Nao foi possivel reservar a capacidade solicitada.",
                code="StrategicReservationConflict",
            ) from exc
        self.db.refresh(row)
        return row

    def confirm_reservation(self, reservation_id: str, *, now: datetime | None = None) -> StrategicReservation:
        now = _as_utc(now or _utc_now())
        row = self._reservation(reservation_id, lock=True)
        if row.status == "confirmed":
            return row
        if row.status != "held":
            raise DomainError("A reserva nao esta retida para confirmacao.", code="StrategicReservationNotHeld")
        slot = self._slot(row.slot_id, lock=True)
        if row.expires_at and _as_utc(row.expires_at) <= now:
            self._release_capacity(row, slot, "expired", now, "Retencao expirada antes da confirmacao.")
            self.db.commit()
            raise StrategicCapacityConflict("A retencao da reserva expirou.", code="StrategicReservationExpired")
        row.status = "confirmed"
        row.confirmed_at = now
        row.expires_at = None
        self.db.commit()
        self.db.refresh(row)
        return row

    def release_reservation(
        self,
        reservation_id: str,
        payload: StrategicReservationRelease,
        *,
        now: datetime | None = None,
    ) -> StrategicReservation:
        now = _as_utc(now or _utc_now())
        row = self._reservation(reservation_id, lock=True)
        if row.status in {"released", "expired", "cancelled"}:
            return row
        if row.order_id:
            order = self.db.query(Order).filter(
                Order.tenant_id == self.tenant_id,
                Order.id == row.order_id,
            ).first()
            order_status = getattr(getattr(order, "status", None), "value", getattr(order, "status", None))
            if order is not None and order_status not in {"cancelled", "refunded"}:
                raise DomainError(
                    "A reserva vinculada a um pedido ativo deve ser cancelada pelo fluxo do pedido.",
                    code="StrategicReservationHasActiveOrder",
                )
        slot = self._slot(row.slot_id, lock=True)
        target = "cancelled" if payload.cancelled else "released"
        self._release_capacity(row, slot, target, now, payload.reason)
        self.db.commit()
        self.db.refresh(row)
        return row

    def bind_confirmed_order(self, reservation_id: str, order_id: str) -> StrategicReservation:
        """Bind one confirmed reservation to its canonical tenant order.

        The reservation row is the concurrency boundary.  No order, payment,
        stock or CMV record is created here; those remain owned by OrderService.
        """
        row = self._reservation(reservation_id, lock=True)
        if row.status != "confirmed":
            raise DomainError(
                "Somente uma reserva confirmada pode ser vinculada ao pedido.",
                code="StrategicReservationNotConfirmed",
            )
        order = self.db.query(Order).filter(
            Order.tenant_id == self.tenant_id,
            Order.id == order_id,
            Order.archived_at.is_(None),
        ).with_for_update().first()
        if order is None:
            raise DomainError("Pedido nao encontrado.", code="OrderNotFound")
        if row.order_id:
            if row.order_id == order.id:
                return row
            raise StrategicCapacityConflict(
                "A reserva ja esta vinculada a outro pedido.",
                code="StrategicReservationOrderConflict",
            )
        if order.strategic_campaign_id != row.campaign_id or order.strategic_offer_id != row.offer_id:
            raise DomainError(
                "O pedido nao corresponde a campanha e oferta da reserva.",
                code="StrategicReservationOrderMismatch",
            )
        if not order.is_scheduled or order.scheduled_for is None:
            raise DomainError(
                "A reserva exige um pedido programado.",
                code="StrategicReservationOrderNotScheduled",
            )
        slot = self._slot(row.slot_id, lock=True)
        scheduled_for = _as_utc(order.scheduled_for)
        if scheduled_for < _as_utc(slot.starts_at) or scheduled_for >= _as_utc(slot.ends_at):
            raise DomainError(
                "O horario do pedido esta fora do slot reservado.",
                code="StrategicReservationOrderOutsideSlot",
            )
        ordered_quantity = sum(max(0, int(item.quantity or 0)) for item in order.items)
        if ordered_quantity != row.quantity:
            raise DomainError(
                "A quantidade do pedido nao corresponde a capacidade reservada.",
                code="StrategicReservationOrderQuantityMismatch",
            )
        existing = self.db.query(StrategicReservation).filter(
            StrategicReservation.tenant_id == self.tenant_id,
            StrategicReservation.order_id == order.id,
            StrategicReservation.id != row.id,
        ).first()
        if existing is not None:
            raise StrategicCapacityConflict(
                "O pedido ja esta vinculado a outra reserva.",
                code="StrategicOrderReservationConflict",
            )
        row.order_id = order.id
        snapshot = dict(order.strategic_offer_snapshot or {})
        snapshot["reservation"] = {
            "id": row.id,
            "slot_id": row.slot_id,
            "quantity": row.quantity,
            "payment_mode": row.payment_mode,
        }
        order.strategic_offer_snapshot = snapshot
        self.db.commit()
        self.db.refresh(row)
        return row

    def release_due_orders(
        self,
        *,
        actor_id: str = "strategic-scheduler",
        now: datetime | None = None,
        limit: int = 100,
    ) -> list[StrategicReservation]:
        """Release due paid strategic orders through the canonical KDS flow."""
        now = _as_utc(now or _utc_now())
        candidate_ids = [item[0] for item in self.db.query(StrategicReservation.id).join(
            Order,
            (Order.tenant_id == StrategicReservation.tenant_id)
            & (Order.id == StrategicReservation.order_id),
        ).filter(
            StrategicReservation.tenant_id == self.tenant_id,
            StrategicReservation.status == "confirmed",
            StrategicReservation.order_id.is_not(None),
            StrategicReservation.operational_released_at.is_(None),
            Order.archived_at.is_(None),
            Order.status.in_((OrderStatus.paid, OrderStatus.pago, OrderStatus.preparing)),
            Order.is_scheduled.is_(True),
            Order.scheduled_for.is_not(None),
            Order.scheduled_for <= now,
        ).order_by(Order.scheduled_for, StrategicReservation.id).limit(max(1, min(limit, 500))).all()]

        released: list[StrategicReservation] = []
        for reservation_id in candidate_ids:
            row = self._release_due_order(reservation_id, actor_id=actor_id, now=now)
            if row is not None:
                released.append(row)
        return released

    def _release_due_order(
        self,
        reservation_id: str,
        *,
        actor_id: str,
        now: datetime,
    ) -> StrategicReservation | None:
        row = self._reservation(reservation_id, lock=True)
        if row.operational_released_at is not None:
            return None
        order = self.db.query(Order).filter(
            Order.tenant_id == self.tenant_id,
            Order.id == row.order_id,
            Order.archived_at.is_(None),
        ).with_for_update().first()
        if order is None or row.status != "confirmed":
            return None
        status = getattr(order.status, "value", order.status)
        if status == OrderStatus.preparing.value:
            row.operational_released_at = now
            self.db.commit()
            self.db.refresh(row)
            return row
        if status not in {OrderStatus.paid.value, OrderStatus.pago.value}:
            return None
        if not order.is_scheduled or order.scheduled_for is None or _as_utc(order.scheduled_for) > now:
            return None

        # Persist the marker in the same transaction committed by the canonical
        # KDS/OrderService path.  A retry then observes either both effects or
        # neither, while KDS unit creation is itself idempotent.
        row.operational_released_at = now
        from backend.core.tenant_context import TenantContext, TenantSource
        from backend.services.kds_service import KdsService

        KdsService(
            self.db,
            TenantContext(
                tenant_id=self.tenant_id,
                source=TenantSource.JOB,
                correlation_id=f"strategic-release:{row.id}",
            ),
        ).start_preparation(order.id, actor_id=actor_id)
        self.db.refresh(row)
        return row

    def release_for_cancelled_order(self, order_id: str, *, now: datetime | None = None) -> None:
        """Return strategic capacity once when its canonical order is cancelled."""
        row = self.db.query(StrategicReservation).filter(
            StrategicReservation.tenant_id == self.tenant_id,
            StrategicReservation.order_id == order_id,
        ).with_for_update().first()
        if row is None or row.status not in ACTIVE_RESERVATION_STATUSES:
            return
        slot = self._slot(row.slot_id, lock=True)
        self._release_capacity(
            row,
            slot,
            "cancelled",
            _as_utc(now or _utc_now()),
            "Pedido vinculado cancelado.",
        )

    def expire_due(
        self,
        campaign_id: str,
        *,
        now: datetime | None = None,
        limit: int = 500,
    ) -> list[str]:
        self._campaign(campaign_id)
        now = _as_utc(now or _utc_now())
        rows = self.db.query(StrategicReservation).filter(
            StrategicReservation.tenant_id == self.tenant_id,
            StrategicReservation.campaign_id == campaign_id,
            StrategicReservation.status == "held",
            StrategicReservation.expires_at.is_not(None),
            StrategicReservation.expires_at <= now,
        ).order_by(StrategicReservation.slot_id, StrategicReservation.id).limit(limit).with_for_update(skip_locked=True).all()
        expired_ids: list[str] = []
        for row in rows:
            slot = self._slot(row.slot_id, lock=True)
            self._release_capacity(row, slot, "expired", now, "Retencao expirada automaticamente.")
            expired_ids.append(row.id)
        self.db.commit()
        return expired_ids

    def _expire_held_for_slot(self, slot: StrategicCapacitySlot, now: datetime) -> None:
        rows = self.db.query(StrategicReservation).filter(
            StrategicReservation.tenant_id == self.tenant_id,
            StrategicReservation.slot_id == slot.id,
            StrategicReservation.status == "held",
            StrategicReservation.expires_at.is_not(None),
            StrategicReservation.expires_at <= now,
        ).order_by(StrategicReservation.id).with_for_update().all()
        for row in rows:
            self._release_capacity(row, slot, "expired", now, "Retencao expirada automaticamente.")

    @staticmethod
    def _release_capacity(
        row: StrategicReservation,
        slot: StrategicCapacitySlot,
        status: str,
        now: datetime,
        reason: str,
    ) -> None:
        if row.status not in ACTIVE_RESERVATION_STATUSES:
            return
        if slot.capacity_used < row.quantity:
            raise DomainError(
                "Contador de capacidade inconsistente; liberacao interrompida.",
                code="StrategicCapacityInvariantViolation",
            )
        slot.capacity_used -= row.quantity
        row.status = status
        row.released_at = now
        row.release_reason = reason
        row.expires_at = None

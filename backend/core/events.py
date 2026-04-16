"""
Domain Event Bus — decouples services from ERP sync, notifications,
webhooks, and any other side effects.

Design:
  - Services publish events AFTER committing to the DB.
  - Handlers are registered at startup (main.py lifespan).
  - ERP handler, push-notification handler, etc. plug in here
    without touching any service code.

Example:
    from backend.core.events import bus

    # In main.py lifespan:
    bus.subscribe(OrderCreated, erp_sync_handler)
    bus.subscribe(OrderStatusChanged, push_notification_handler)

    # In a service:
    bus.publish(OrderCreated(order_id=order.id, total=order.total))
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Type

logger = logging.getLogger("events")


# ── Base event ────────────────────────────────────────────────────────────────

@dataclass
class DomainEvent:
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
        init=False,
    )

    @property
    def name(self) -> str:
        return self.__class__.__name__


# ── Order events ──────────────────────────────────────────────────────────────

@dataclass
class OrderCreated(DomainEvent):
    order_id: str
    customer_name: str
    total: float
    items_count: int
    delivery_city: str


@dataclass
class OrderStatusChanged(DomainEvent):
    order_id: str
    from_status: str
    to_status: str
    changed_by: str = "system"        # "system" | "admin" | "webhook"


@dataclass
class OrderCancelled(DomainEvent):
    order_id: str
    reason: str
    refund_required: bool = False


# ── Payment events ────────────────────────────────────────────────────────────

@dataclass
class PaymentCreated(DomainEvent):
    payment_id: str
    order_id: str
    method: str
    amount: float
    gateway: str


@dataclass
class PaymentConfirmed(DomainEvent):
    payment_id: str
    order_id: str
    amount: float
    gateway: str
    transaction_id: str


@dataclass
class PaymentFailed(DomainEvent):
    payment_id: str
    order_id: str
    reason: str


# ── Delivery events ───────────────────────────────────────────────────────────

@dataclass
class DeliveryAssigned(DomainEvent):
    delivery_id: str
    order_id: str
    delivery_person_id: str
    delivery_person_name: str
    estimated_minutes: int


@dataclass
class DeliveryStatusChanged(DomainEvent):
    delivery_id: str
    order_id: str
    from_status: str
    to_status: str


@dataclass
class DeliveryCompleted(DomainEvent):
    delivery_id: str
    order_id: str
    delivery_person_id: str
    duration_minutes: int


# ── Shipping events ───────────────────────────────────────────────────────────

@dataclass
class ShippingCalculated(DomainEvent):
    order_id: str | None
    city: str
    rule_name: str
    shipping_price: float
    free: bool


# ── Event Bus ─────────────────────────────────────────────────────────────────

Handler = Callable[[DomainEvent], None]


class EventBus:
    """
    Simple synchronous event bus.

    For async/queue-based delivery (Celery, Redis, SQS), replace
    _dispatch() with a task enqueue — the subscriber interface stays the same.
    """

    def __init__(self):
        self._handlers: dict[Type[DomainEvent], list[Handler]] = {}

    def subscribe(self, event_type: Type[DomainEvent], handler: Handler) -> None:
        """Register a handler for a specific event type."""
        self._handlers.setdefault(event_type, []).append(handler)
        logger.debug("Subscribed %s to %s", handler.__name__, event_type.__name__)

    def publish(self, event: DomainEvent) -> None:
        """
        Publish an event to all registered handlers.

        Handlers are called synchronously in registration order.
        A failing handler is logged but never breaks the caller.
        """
        handlers = self._handlers.get(type(event), [])
        if not handlers:
            logger.debug("Event %s published but has no subscribers.", event.name)
            return

        for handler in handlers:
            try:
                handler(event)
                logger.debug("Handler %s processed %s", handler.__name__, event.name)
            except Exception as exc:
                logger.error(
                    "Handler %s failed processing %s: %s",
                    handler.__name__, event.name, exc,
                    exc_info=True,
                )

    def subscribers(self) -> dict[str, list[str]]:
        """Introspection — returns event_name → [handler_names]."""
        return {
            evt.__name__: [h.__name__ for h in handlers]
            for evt, handlers in self._handlers.items()
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

bus = EventBus()


# ── Built-in ERP-ready handler stubs ─────────────────────────────────────────
# Register these in main.py lifespan to activate ERP sync.

def erp_order_created_handler(event: OrderCreated) -> None:
    """Sync new order to ERP / fiscal system."""
    logger.info(
        "[ERP] OrderCreated | id=%s | total=R$%.2f | city=%s",
        event.order_id, event.total, event.delivery_city,
    )
    # TODO: POST to ERP endpoint or write to shared DB table


def erp_order_status_handler(event: OrderStatusChanged) -> None:
    """Notify ERP of order status changes."""
    logger.info(
        "[ERP] OrderStatusChanged | id=%s | %s → %s",
        event.order_id, event.from_status, event.to_status,
    )
    # TODO: PATCH ERP order status


def erp_payment_confirmed_handler(event: PaymentConfirmed) -> None:
    """Trigger fiscal note emission when payment is confirmed."""
    logger.info(
        "[ERP] PaymentConfirmed | payment=%s | order=%s | R$%.2f",
        event.payment_id, event.order_id, event.amount,
    )
    # TODO: emit NF-e / NF-Se via ERP API


def erp_delivery_completed_handler(event: DeliveryCompleted) -> None:
    """Close delivery in ERP and release motoboy."""
    logger.info(
        "[ERP] DeliveryCompleted | delivery=%s | order=%s | %d min",
        event.delivery_id, event.order_id, event.duration_minutes,
    )
    # TODO: update ERP delivery record


def push_notification_handler(event: DomainEvent) -> None:
    """Send push notification to customer on key status changes."""
    messages: dict[str, str] = {
        "PaymentConfirmed":   "✅ Pagamento confirmado! Seu pedido está sendo preparado.",
        "OrderStatusChanged": "🍕 Atualização do seu pedido.",
        "DeliveryAssigned":   "🛵 Motoboy a caminho!",
        "DeliveryCompleted":  "🎉 Pedido entregue! Bom apetite.",
    }
    msg = messages.get(event.name)
    if msg:
        logger.info("[PUSH] %s → %s", event.name, msg)
        # TODO: integrate Firebase FCM / OneSignal

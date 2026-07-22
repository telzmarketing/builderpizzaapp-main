"""Canonical producers for the transversal automation event stream.

These helpers only enqueue durable events in the caller's current transaction.
They never commit, so the domain mutation and its automation event remain atomic.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.services.automation_event_service import AutomationEventService


class AutomationEventProducer:
    def __init__(self, db: Session, tenant_id: str | None):
        normalized = (tenant_id or "").strip()
        if not normalized:
            raise ValueError("tenant_id obrigatorio para publicar evento de automacao")
        self._events = AutomationEventService(db, normalized)

    def customer_created(self, customer: Any) -> str:
        return self._events.publish(
            event_key="customer.created", aggregate_type="customer", aggregate_id=customer.id,
            customer_id=customer.id, dedupe_key=f"customer.created:{customer.id}",
            payload={"customer_id": customer.id, "source": customer.source or "unknown"},
        )

    def customer_tag_assigned(self, assignment: Any) -> str:
        return self._events.publish(
            event_key="customer.tag_assigned", aggregate_type="customer_tag_assignment",
            aggregate_id=assignment.id, customer_id=assignment.customer_id,
            dedupe_key=f"customer.tag_assigned:{assignment.id}",
            payload={"customer_id": assignment.customer_id, "tag_id": assignment.tag_id,
                     "source": assignment.source or "unknown"},
        )

    def order_created(self, order: Any) -> str:
        status = order.status.value if hasattr(order.status, "value") else str(order.status)
        return self._events.publish(
            event_key="order.created", aggregate_type="order", aggregate_id=order.id,
            customer_id=order.customer_id, dedupe_key=f"order.created:{order.id}",
            payload={"order_id": order.id, "customer_id": order.customer_id,
                     "status": status, "total": float(order.total or 0)},
        )

    def order_status_changed(self, order: Any, old_status: str, new_status: str) -> str:
        return self._events.publish(
            event_key="order.status_changed", aggregate_type="order", aggregate_id=order.id,
            customer_id=order.customer_id,
            dedupe_key=f"order.status_changed:{order.id}:{old_status}:{new_status}",
            payload={"order_id": order.id, "customer_id": order.customer_id,
                     "from_status": old_status, "status": new_status},
        )

    def payment_confirmed(self, payment: Any, customer_id: str | None) -> str:
        return self._events.publish(
            event_key="payment.confirmed", aggregate_type="payment", aggregate_id=payment.id,
            customer_id=customer_id, dedupe_key=f"payment.confirmed:{payment.id}",
            payload={"payment_id": payment.id, "order_id": payment.order_id,
                     "customer_id": customer_id, "amount": float(payment.amount or 0)},
        )

    def loyalty_level_up(self, account: Any, old_level_id: str, new_level_id: str,
                         mutation_id: str) -> str:
        return self._events.publish(
            event_key="loyalty.level_up", aggregate_type="customer_loyalty", aggregate_id=account.id,
            customer_id=account.customer_id,
            dedupe_key=f"loyalty.level_up:{mutation_id}",
            payload={"customer_id": account.customer_id, "from_level_id": old_level_id,
                     "level_id": new_level_id, "total_points": int(account.total_points or 0)},
        )

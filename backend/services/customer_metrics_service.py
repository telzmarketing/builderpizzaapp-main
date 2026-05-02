"""CRM customer metric synchronization.

Keeps denormalized customer metrics in sync with the canonical orders table.
The CRM uses these fields for dashboards, dynamic groups and future AI analysis.
"""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.customer import Customer
from backend.models.order import Order, OrderStatus


CRM_REVENUE_ORDER_STATUSES = (
    OrderStatus.paid,
    OrderStatus.pago,
    OrderStatus.preparing,
    OrderStatus.ready_for_pickup,
    OrderStatus.on_the_way,
    OrderStatus.delivered,
)


def sync_customer_order_metrics(db: Session, customer_id: str | None) -> None:
    """Recalculate order metrics for one customer inside the current transaction."""
    if not customer_id:
        return

    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return

    total_orders, total_spent, first_order_at, last_order_at = (
        db.query(
            func.count(Order.id),
            func.coalesce(func.sum(Order.total), 0.0),
            func.min(Order.created_at),
            func.max(Order.created_at),
        )
        .filter(
            Order.customer_id == customer_id,
            Order.status.in_(CRM_REVENUE_ORDER_STATUSES),
        )
        .one()
    )

    total_orders = int(total_orders or 0)
    total_spent = float(total_spent or 0.0)

    customer.total_orders = total_orders
    customer.total_spent = round(total_spent, 2)
    customer.avg_ticket = round(total_spent / total_orders, 2) if total_orders else 0.0
    customer.first_order_at = first_order_at
    customer.last_order_at = last_order_at

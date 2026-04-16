"""
Order endpoints — shared by loja online and ERP.

All business logic lives in OrderService. These handlers only:
  1. Parse and validate the HTTP request.
  2. Call the service.
  3. Return a standardized JSON envelope.

Endpoints:
  POST   /orders              → create order (checkout)
  GET    /orders              → list orders
  GET    /orders/{id}         → get single order
  PUT    /orders/{id}/status  → advance status (state machine enforced)
  POST   /orders/{id}/cancel  → cancel order
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import ok, created, err
from backend.database import get_db
from backend.models.order import OrderStatus
from backend.schemas.order import CheckoutIn, OrderStatusUpdate
from backend.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])


# ── Create order ──────────────────────────────────────────────────────────────

@router.post("", status_code=201)
def create_order(body: CheckoutIn, db: Session = Depends(get_db)):
    """
    Create a new order from the shopping cart.

    Server-side responsibilities:
    - Recomputes all prices (prevents price manipulation)
    - Calculates shipping via ShippingService
    - Applies coupon via CouponService (if provided)
    - Persists Order, OrderItems and OrderItemFlavors atomically
    - Publishes OrderCreated event (ERP sync + push notification)

    Initial order status: **pending**
    Next step: POST /payments/create
    """
    try:
        svc = OrderService(db)
        order = svc.create_from_checkout(body)
        # Re-fetch with all relations loaded (items, flavors)
        order = svc.get(order.id)
        return created(order, "Pedido criado com sucesso.")
    except DomainError as exc:
        return err(exc)


# Alias kept for backward compatibility with existing front-end code
@router.post("/checkout", status_code=201, include_in_schema=False)
def checkout_alias(body: CheckoutIn, db: Session = Depends(get_db)):
    return create_order(body, db)


# ── List orders ───────────────────────────────────────────────────────────────

@router.get("")
def list_orders(
    status: OrderStatus | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    List orders with optional filters.

    Filters:
      ?status=pending|waiting_payment|paid|preparing|on_the_way|delivered|cancelled
      ?customer_id=<uuid>
      ?limit=50  (1–200)

    Used by both the loja (customer history) and ERP (kitchen queue).
    """
    try:
        orders = OrderService(db).list(
            status=status.value if status else None,
            customer_id=customer_id,
            limit=limit,
        )
        return ok(orders)
    except DomainError as exc:
        return err(exc)


# ── Get single order ──────────────────────────────────────────────────────────

@router.get("/{order_id}")
def get_order(order_id: str, db: Session = Depends(get_db)):
    """
    Retrieve a single order with all items, flavors, and payment info.
    Used by /order-tracking on the loja and the order detail screen on ERP.
    """
    try:
        return ok(OrderService(db).get(order_id))
    except DomainError as exc:
        return err(exc)


# ── Update status ─────────────────────────────────────────────────────────────

@router.put("/{order_id}/status")
def update_order_status(
    order_id: str,
    body: OrderStatusUpdate,
    db: Session = Depends(get_db),
):
    """
    Advance an order through its state machine.

    Valid flow:
      pending → waiting_payment → paid → preparing → on_the_way → delivered

    Any invalid transition returns HTTP 400 with code=InvalidStatusTransition.

    Called by:
      - ERP kitchen display (preparing, ready_for_pickup)
      - DeliveryService internally (on_the_way, delivered — avoid calling directly)
      - Admin panel (any manual override in allowed flow)
    """
    try:
        order = OrderService(db).change_status(
            order_id,
            body.status.value,
            changed_by="admin",
        )
        return ok(order, f"Status atualizado para '{body.status.value}'.")
    except DomainError as exc:
        return err(exc)


# PATCH alias — keeps existing integrations working
@router.patch("/{order_id}/status", include_in_schema=False)
def patch_order_status(order_id: str, body: OrderStatusUpdate, db: Session = Depends(get_db)):
    return update_order_status(order_id, body, db)


# ── Cancel ────────────────────────────────────────────────────────────────────

@router.post("/{order_id}/cancel")
def cancel_order(order_id: str, db: Session = Depends(get_db)):
    """
    Cancel an order. Valid from: pending, waiting_payment, paid, preparing.
    Terminal orders (delivered, cancelled, refunded) cannot be cancelled.
    """
    try:
        order = OrderService(db).cancel(order_id, changed_by="admin")
        return ok(order, "Pedido cancelado.")
    except DomainError as exc:
        return err(exc)

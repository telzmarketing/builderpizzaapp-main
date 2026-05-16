"""
Order endpoints shared by loja online and ERP.

All business logic lives in OrderService. These handlers only:
  1. Parse and validate the HTTP request.
  2. Call the service.
  3. Return a standardized JSON envelope.
"""
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import ok, created, err, err_msg
from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.routes.customer_access import require_customer_id_or_admin
from backend.routes.order_access import require_order_or_admin
from backend.models.order import Order, OrderStatus
from backend.models.admin import AdminUser
from backend.models.product import Product
from backend.schemas.order import CheckoutIn, OrderStatusUpdate
from backend.services.payment_service import PaymentService
from backend.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])


def _require_admin(request: Request, db: Session) -> AdminUser:
    return get_current_admin(
        authorization=request.headers.get("authorization"),
        db=db,
    )


def _build_product_lookup(db: Session, orders: list[Order]) -> dict[str, Product]:
    product_ids: set[str] = set()
    for order in orders:
        for item in order.items:
            product_ids.add(item.product_id)
            for flavor in item.flavors:
                product_ids.add(flavor.product_id)

    if not product_ids:
        return {}

    products = db.query(Product).filter(Product.id.in_(product_ids)).all()
    return {product.id: product for product in products}


def _serialize_order(order: Order, product_lookup: dict[str, Product]) -> dict:
    items = []
    for item in order.items:
        fallback_product = product_lookup.get(item.product_id)
        fallback_flavor = item.flavors[0] if item.flavors else None
        product_name = (
            fallback_product.name if fallback_product
            else fallback_flavor.flavor_name if fallback_flavor
            else ""
        )

        flavors = []
        for flavor in item.flavors:
            flavor_product = product_lookup.get(flavor.product_id)
            flavors.append({
                "product_id": flavor.product_id,
                "name": flavor.flavor_name,
                "price": flavor.flavor_price,
                "icon": flavor_product.icon if flavor_product else "",
            })

        items.append({
            "id": item.id,
            "product_id": item.product_id,
            "product_name": product_name,
            "quantity": item.quantity,
            "selected_size": item.selected_size,
            "selected_size_id": item.selected_size_id,
            "flavor_division": item.flavor_division,
            "flavor_count": item.flavor_count or item.flavor_division,
            "selected_crust_type_id": item.selected_crust_type_id,
            "selected_crust_type": item.selected_crust_type,
            "selected_drink_variant": item.selected_drink_variant,
            "notes": item.notes,
            "flavors": flavors,
            "add_ons": [],
            "unit_price": item.unit_price,
            "final_price": item.unit_price,
            "standard_unit_price": item.standard_unit_price,
            "applied_unit_price": item.applied_unit_price,
            "original_price": item.original_price,
            "is_gift": bool(item.is_gift),
            "gift_reason": item.gift_reason,
            "coupon_id": item.coupon_id,
            "coupon_code": item.coupon_code,
            "promotion_id": item.promotion_id,
            "promotion_name": item.promotion_name,
            "promotion_discount": item.promotion_discount or 0,
            "promotion_applied": bool(item.promotion_id),
            "promotion_blocked": bool(item.promotion_blocked),
            "promotion_block_reason": item.promotion_block_reason,
        })

    status = order.status.value if hasattr(order.status, "value") else str(order.status)
    delivery_summary = None
    try:
        d = order.delivery
        if d:
            dp = d.delivery_person
            delivery_summary = {
                "id": d.id,
                "status": d.status.value if hasattr(d.status, "value") else str(d.status),
                "delivery_person_id": d.delivery_person_id,
                "delivery_person_name": dp.name if dp else None,
                "assigned_at": d.assigned_at,
                "picked_up_at": d.picked_up_at,
                "delivered_at": d.delivered_at,
                "problem_report": d.problem_report,
                "problem_reported_at": d.problem_reported_at,
                "problem_resolved_at": d.problem_resolved_at,
                "admin_resolution_note": d.admin_resolution_note,
                "rating": d.rating,
                "rating_comment": d.rating_comment,
            }
    except Exception:
        pass
    return {
        "id": order.id,
        "customer_id": order.customer_id,
        "delivery_name": order.delivery_name,
        "delivery_phone": order.delivery_phone,
        "delivery_street": order.delivery_street,
        "delivery_city": order.delivery_city,
        "delivery_complement": order.delivery_complement,
        "status": status,
        "pedido_status": status,
        "payment_status": order.payment.status.value if order.payment else "pending",
        "payment_method": order.payment.method.value if order.payment else None,
        "payment_provider": order.payment.provider if order.payment else None,
        "pay_on_delivery": bool(order.payment.pay_on_delivery) if order.payment else False,
        "delivery_payment_method": order.payment.delivery_payment_method if order.payment else None,
        "cash_needs_change": order.payment.cash_needs_change if order.payment else None,
        "cash_change_for": order.payment.cash_change_for if order.payment else None,
        "external_reference": order.external_reference,
        "subtotal": order.subtotal,
        "shipping_fee": order.shipping_fee,
        "delivery_fee_original": order.delivery_fee_original or order.shipping_fee or 0,
        "delivery_fee_discount": order.delivery_fee_discount or 0,
        "delivery_fee_final": order.delivery_fee_final if order.delivery_fee_final is not None else order.shipping_fee,
        "free_shipping_applied": bool(order.free_shipping_applied),
        "discount": order.discount,
        "total": order.total,
        "estimated_time": order.estimated_time,
        "loyalty_points_earned": order.loyalty_points_earned,
        "is_scheduled": bool(order.is_scheduled),
        "scheduled_for": order.scheduled_for,
        "coupon_id": order.coupon_id,
        "items": items,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "paid_at": order.paid_at,
        "preparation_started_at": order.preparation_started_at,
        "out_for_delivery_at": order.out_for_delivery_at,
        "delivered_at": order.delivered_at,
        "target_delivery_minutes": order.target_delivery_minutes or 45,
        "total_time_minutes": order.total_time_minutes,
        "preparation_time_minutes": order.preparation_time_minutes,
        "delivery_time_minutes": order.delivery_time_minutes,
        "cancelled_by": order.cancelled_by,
        "cancellation_reason": order.cancellation_reason,
        "cancelled_at": order.cancelled_at,
        "delivery": delivery_summary,
    }


def _serialize_orders(db: Session, orders: list[Order]) -> list[dict]:
    product_lookup = _build_product_lookup(db, orders)
    return [_serialize_order(order, product_lookup) for order in orders]


@router.post("", status_code=201)
def create_order(body: CheckoutIn, db: Session = Depends(get_db)):
    if not body.customer_id:
        return err_msg(
            "É necessário ter uma conta cadastrada para fazer um pedido.",
            code="CustomerRequired",
            status_code=401,
        )
    try:
        svc = OrderService(db)
        order = svc.create_from_checkout(body)
        order = svc.get(order.id)
        return created(_serialize_orders(db, [order])[0], "Pedido criado com sucesso.")
    except DomainError as exc:
        return err(exc)

@router.post("/checkout", status_code=201, include_in_schema=False)
def checkout_alias(body: CheckoutIn, db: Session = Depends(get_db)):
    return create_order(body, db)


@router.get("")
def list_orders(
    request: Request,
    status: OrderStatus | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    try:
        if customer_id:
            require_customer_id_or_admin(
                customer_id,
                db,
                request.headers.get("authorization"),
                request.headers.get("x-customer-phone"),
                request.headers.get("x-customer-email"),
            )
        else:
            _require_admin(request, db)
        orders = OrderService(db).list(
            status=status.value if status else None,
            customer_id=customer_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
        return ok(_serialize_orders(db, orders))
    except DomainError as exc:
        return err(exc)


@router.get("/reports/operational")
def operational_report(
    days: int = 7,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    delivered = (
        db.query(Order)
        .filter(Order.status == OrderStatus.delivered, Order.delivered_at >= cutoff)
        .all()
    )
    if not delivered:
        return ok({
            "period_days": days,
            "total_orders": 0,
            "within_target": 0,
            "outside_target": 0,
            "pct_within_target": 0.0,
            "avg_total_minutes": None,
            "avg_preparation_minutes": None,
            "avg_delivery_minutes": None,
            "most_delayed": [],
        })
    total = len(delivered)
    within = [o for o in delivered if o.total_time_minutes is not None and o.total_time_minutes <= (o.target_delivery_minutes or 45)]
    outside = [o for o in delivered if o.total_time_minutes is not None and o.total_time_minutes > (o.target_delivery_minutes or 45)]
    timed = [o for o in delivered if o.total_time_minutes]
    avg_total = round(sum(o.total_time_minutes for o in timed) / max(len(timed), 1), 1) if timed else None
    prep_vals = [o.preparation_time_minutes for o in delivered if o.preparation_time_minutes]
    avg_prep = round(sum(prep_vals) / len(prep_vals), 1) if prep_vals else None
    del_vals = [o.delivery_time_minutes for o in delivered if o.delivery_time_minutes]
    avg_del = round(sum(del_vals) / len(del_vals), 1) if del_vals else None
    most_delayed = sorted(
        timed,
        key=lambda o: o.total_time_minutes,
        reverse=True,
    )[:5]
    return ok({
        "period_days": days,
        "total_orders": total,
        "within_target": len(within),
        "outside_target": len(outside),
        "pct_within_target": round(len(within) / total * 100, 1) if total else 0.0,
        "avg_total_minutes": avg_total,
        "avg_preparation_minutes": avg_prep,
        "avg_delivery_minutes": avg_del,
        "most_delayed": [
            {"id": o.id, "total_time_minutes": o.total_time_minutes, "target": o.target_delivery_minutes}
            for o in most_delayed
        ],
    })


@router.get("/{order_id}")
def get_order(order_id: str, request: Request, db: Session = Depends(get_db)):
    try:
        order = OrderService(db).get(order_id)
        require_order_or_admin(
            order,
            db,
            request.headers.get("authorization"),
            request.headers.get("x-customer-phone"),
            request.headers.get("x-customer-email"),
        )
        return ok(_serialize_orders(db, [order])[0])
    except DomainError as exc:
        return err(exc)


@router.get("/{order_id}/payment-status")
def get_order_payment_status(order_id: str, request: Request, db: Session = Depends(get_db)):
    try:
        order = OrderService(db).get(order_id)
        require_order_or_admin(
            order,
            db,
            request.headers.get("authorization"),
            request.headers.get("x-customer-phone"),
            request.headers.get("x-customer-email"),
        )
        return ok(PaymentService(db).payment_status(order_id))
    except DomainError as exc:
        return err(exc)


@router.put("/{order_id}/status")
def update_order_status(
    order_id: str,
    body: OrderStatusUpdate,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    try:
        order = OrderService(db).change_status(
            order_id,
            body.status.value,
            changed_by="admin",
        )
        return ok(_serialize_orders(db, [order])[0], f"Status atualizado para '{body.status.value}'.")
    except DomainError as exc:
        return err(exc)


@router.patch("/{order_id}/status", include_in_schema=False)
def patch_order_status(
    order_id: str,
    body: OrderStatusUpdate,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    return update_order_status(order_id, body, db)


@router.post("/{order_id}/cancel")
def cancel_order(
    order_id: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    try:
        order = OrderService(db).cancel(
            order_id,
            changed_by="admin",
            cancelled_by="admin",
            reason="Cancelado pelo administrador",
        )
        return ok(_serialize_orders(db, [order])[0], "Pedido cancelado.")
    except DomainError as exc:
        return err(exc)


@router.post("/{order_id}/customer-cancel")
def customer_cancel_order(
    order_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Permite que o próprio cliente cancele um pedido não pago."""
    try:
        order = OrderService(db).get(order_id)
        require_order_or_admin(
            order,
            db,
            request.headers.get("authorization"),
            request.headers.get("x-customer-phone"),
            request.headers.get("x-customer-email"),
        )
        # Só permite cancelar pedidos não pagos
        non_cancellable = {"paid", "pago", "preparing", "ready_for_pickup", "on_the_way", "delivered"}
        current = order.status.value if hasattr(order.status, "value") else str(order.status)
        if current in non_cancellable:
            return err_msg(
                "Pedido já está em preparo ou entregue e não pode ser cancelado.",
                code="OrderNotCancellable",
                status_code=422,
            )
        order = OrderService(db).cancel(
            order_id,
            changed_by="customer",
            cancelled_by="customer",
            reason="Cancelado pelo cliente",
        )
        return ok(_serialize_orders(db, [order])[0], "Pedido cancelado com sucesso.")
    except DomainError as exc:
        return err(exc)


@router.post("/auto-cancel-expired")
def auto_cancel_expired(
    hours: int = Query(default=2, ge=1, le=48),
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    """Trigger interno: cancela pedidos presos em pagamento_expirado há mais de N horas."""
    cancelled = OrderService(db).auto_cancel_expired(hours=hours)
    return ok({"cancelled_count": len(cancelled), "cancelled_ids": cancelled})

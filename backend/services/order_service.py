"""
OrderService — single authoritative source of truth for all order operations.

RULE: nothing outside this class may change an order's status or
      mutate its financial fields. The state machine enforces valid transitions.
      ERP and the loja both call these methods — never bypass them.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload

from backend.core.exceptions import (
    CartEmpty, OrderNotFound, OrderCancelled,
    ProductNotFound, PriceConflict,
    FlavorDivisionMismatch, MaxFlavorsExceeded,
)
from backend.core.state_machine import order_sm
from backend.core.events import (
    bus, OrderCreated, OrderStatusChanged, OrderCancelled as EvOrderCancelled,
)
from backend.models.order import Order, OrderItem, OrderItemFlavor, OrderStatus
from backend.models.product import Product, MultiFlavorsConfig, PricingRule
from backend.schemas.order import CheckoutIn, CartItemIn, FlavorIn, OrderStatusUpdate


# ── Pricing helpers (shared with front-end logic) ─────────────────────────────

def _compute_flavor_price(
    flavors: list[FlavorIn],
    division: int,
    rule: PricingRule,
) -> float:
    prices = [f.price for f in flavors]
    if not prices:
        return 0.0
    if rule == PricingRule.most_expensive:
        return max(prices)
    if rule == PricingRule.average:
        return sum(prices) / len(prices)
    # proportional: each slot pays its fraction
    return sum(p / division for p in prices)


class OrderService:
    """
    All order mutations go through this class.

    Instantiate per-request with the SQLAlchemy session:
        svc = OrderService(db)
    """

    def __init__(self, db: Session):
        self._db = db

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_order(self, order_id: str) -> Order:
        order = (
            self._db.query(Order)
            .options(joinedload(Order.items).joinedload("flavors"))
            .filter(Order.id == order_id)
            .first()
        )
        if not order:
            raise OrderNotFound(order_id)
        return order

    def _get_config(self) -> MultiFlavorsConfig:
        config = (
            self._db.query(MultiFlavorsConfig)
            .filter(MultiFlavorsConfig.id == "default")
            .first()
        )
        if not config:
            config = MultiFlavorsConfig(id="default")
            self._db.add(config)
            self._db.flush()
        return config

    def _validate_item(
        self,
        item: CartItemIn,
        config: MultiFlavorsConfig,
    ) -> tuple[float, list[Product]]:
        """
        Returns (server_unit_price, [Product per flavor]).
        Raises domain exceptions on any inconsistency.
        """
        if len(item.flavors) != item.flavor_division:
            raise FlavorDivisionMismatch(item.product_id, item.flavor_division, len(item.flavors))

        if item.flavor_division > config.max_flavors:
            raise MaxFlavorsExceeded(item.flavor_division, config.max_flavors)

        flavor_products: list[Product] = []
        for f in item.flavors:
            product = (
                self._db.query(Product)
                .filter(Product.id == f.product_id, Product.active == True)  # noqa: E712
                .first()
            )
            if not product:
                raise ProductNotFound(f.product_id)
            if abs(product.price - f.price) > 0.01:
                raise PriceConflict(product.name, f.price, product.price)
            flavor_products.append(product)

        server_price = round(
            _compute_flavor_price(item.flavors, item.flavor_division, config.pricing_rule), 2
        )
        return server_price, flavor_products

    # ── Public API ────────────────────────────────────────────────────────────

    def create_from_checkout(self, payload: CheckoutIn) -> Order:
        """
        Validate cart, recompute prices server-side, apply shipping + coupon,
        persist the order and fire OrderCreated event.

        Called by both the loja (REST endpoint) and ERP integrations.
        """
        if not payload.items:
            raise CartEmpty()

        config = self._get_config()

        # 1. Validate items and compute subtotal
        item_data: list[tuple[CartItemIn, float, list[Product]]] = []
        subtotal = 0.0
        for item in payload.items:
            unit_price, flavor_products = self._validate_item(item, config)
            subtotal += unit_price * item.quantity
            item_data.append((item, unit_price, flavor_products))
        subtotal = round(subtotal, 2)

        # 2. Shipping — delegated to ShippingService (lazy import avoids circular)
        from backend.services.shipping_service import ShippingService
        from backend.schemas.shipping import ShippingCalculateIn
        shipping_result = ShippingService(self._db).calculate(
            ShippingCalculateIn(city=payload.delivery.city, order_subtotal=subtotal)
        )
        shipping_fee = shipping_result.shipping_price

        # 3. Coupon
        discount = 0.0
        resolved_coupon_id: str | None = None
        if payload.coupon_code:
            from backend.services.coupon_service import CouponService
            from backend.schemas.coupon import CouponApplyIn
            coupon_result = CouponService(self._db).apply(
                CouponApplyIn(
                    code=payload.coupon_code,
                    order_subtotal=subtotal,
                    customer_id=payload.customer_id,
                    phone=payload.delivery.phone if payload.delivery else None,
                )
            )
            discount = coupon_result.discount_amount
            resolved_coupon_id = coupon_result.coupon_id

        # 4. Build order
        total = round(subtotal + shipping_fee - discount, 2)
        order = Order(
            id=f"order-{uuid.uuid4().hex[:8]}",
            customer_id=payload.customer_id,
            delivery_name=payload.delivery.name,
            delivery_phone=payload.delivery.phone,
            delivery_street=payload.delivery.street,
            delivery_city=payload.delivery.city,
            delivery_complement=payload.delivery.complement,
            status=OrderStatus.pending,
            coupon_id=resolved_coupon_id,
            subtotal=subtotal,
            shipping_fee=shipping_fee,
            discount=discount,
            total=total,
            estimated_time=40,
        )
        self._db.add(order)
        self._db.flush()

        # 5. Order items and flavor breakdown
        for item, unit_price, flavor_products in item_data:
            oi = OrderItem(
                id=str(uuid.uuid4()),
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                selected_size=item.selected_size,
                flavor_division=item.flavor_division,
                unit_price=unit_price,
                total_price=round(unit_price * item.quantity, 2),
            )
            self._db.add(oi)
            self._db.flush()
            for idx, (flavor_in, product) in enumerate(zip(item.flavors, flavor_products)):
                self._db.add(OrderItemFlavor(
                    id=str(uuid.uuid4()),
                    order_item_id=oi.id,
                    product_id=product.id,
                    flavor_name=product.name,
                    flavor_price=product.price,
                    position=idx,
                ))

        # 6. Record coupon usage
        if resolved_coupon_id:
            from backend.services.coupon_service import CouponService
            CouponService(self._db).record_usage(
                coupon_id=resolved_coupon_id,
                customer_id=payload.customer_id,
                phone=payload.delivery.phone if payload.delivery else None,
                order_id=order.id,
            )

        self._db.commit()
        self._db.refresh(order)

        # 7. Publish event (after commit — DB is consistent)
        bus.publish(OrderCreated(
            order_id=order.id,
            customer_name=payload.delivery.name,
            total=order.total,
            items_count=sum(i.quantity for i in payload.items),
            delivery_city=payload.delivery.city,
        ))

        return order

    def change_status(
        self,
        order_id: str,
        new_status: str,
        *,
        changed_by: str = "system",
    ) -> Order:
        """
        The ONLY way to change an order status.
        Validates via state machine, persists, fires events, awards loyalty.
        """
        order = self._get_order(order_id)
        current = order.status.value if hasattr(order.status, "value") else str(order.status)

        # State machine validates transition (raises InvalidStatusTransition if invalid)
        order_sm.transition(order_id, current, new_status)

        old_status = current
        order.status = OrderStatus(new_status)
        order.updated_at = datetime.now(timezone.utc)
        self._db.commit()

        bus.publish(OrderStatusChanged(
            order_id=order_id,
            from_status=old_status,
            to_status=new_status,
            changed_by=changed_by,
        ))

        # Award loyalty points when delivered
        if new_status == "delivered" and order.customer_id:
            from backend.services.loyalty_service import award_points_for_order
            points = award_points_for_order(
                order.customer_id, order_id, order.total, self._db
            )
            order.loyalty_points_earned = points
            self._db.commit()

        self._db.refresh(order)
        return order

    def cancel(self, order_id: str, *, reason: str = "", changed_by: str = "system") -> Order:
        """Cancels an order through the state machine."""
        order = self.change_status(order_id, "cancelled", changed_by=changed_by)
        bus.publish(EvOrderCancelled(
            order_id=order_id,
            reason=reason,
            refund_required=order.payment is not None,
        ))
        return order

    def get(self, order_id: str) -> Order:
        return self._get_order(order_id)

    def list(
        self,
        *,
        status: str | None = None,
        customer_id: str | None = None,
        limit: int = 50,
    ) -> list[Order]:
        q = self._db.query(Order)
        if status:
            q = q.filter(Order.status == OrderStatus(status))
        if customer_id:
            q = q.filter(Order.customer_id == customer_id)
        return q.order_by(Order.created_at.desc()).limit(limit).all()

    def recalculate_total(self, order_id: str) -> Order:
        """
        Re-runs price calculation for an existing order.
        Useful when an admin changes a product price and needs to sync the ERP.
        Only allowed when status is 'pending'.
        """
        order = self._get_order(order_id)
        if order.status != OrderStatus.pending:
            raise OrderCancelled(order_id)  # reusing as "immutable" signal

        subtotal = sum(item.unit_price * item.quantity for item in order.items)
        order.subtotal = round(subtotal, 2)
        order.total = round(order.subtotal + order.shipping_fee - order.discount, 2)
        self._db.commit()
        self._db.refresh(order)
        return order

"""
OrderService — single authoritative source of truth for all order operations.

RULE: nothing outside this class may change an order's status or
      mutate its financial fields. The state machine enforces valid transitions.
      ERP and the loja both call these methods — never bypass them.
"""
from __future__ import annotations

import random
import string
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session, joinedload

from backend.core.exceptions import (
    CartEmpty, OrderNotFound, OrderCancelled,
    ProductNotFound, PriceConflict,
    FlavorDivisionMismatch, MaxFlavorsExceeded,
    DomainError,
)
from backend.core.state_machine import order_sm
from backend.core.events import (
    bus, OrderCreated, OrderStatusChanged, OrderCancelled as EvOrderCancelled,
)
from backend.models.order import Order, OrderItem, OrderItemFlavor, OrderStatus
from backend.models.payment import Payment, PaymentMethod, PaymentStatus
from backend.models.product import Product, MultiFlavorsConfig, PricingRule, ProductCrustType, ProductDrinkVariant, ProductSize
from backend.models.customer import Address, Customer as CustomerModel
from backend.schemas.order import CheckoutIn, CartItemIn, FlavorIn, OrderStatusUpdate
from backend.services.customer_metrics_service import sync_customer_order_metrics
from backend.services.product_pricing_service import ProductPriceResult, ProductPricingService, normalize_crust_price_addition


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


def _normalize_crust_price_addition(price_addition: float | None, product_base_price: float | None) -> float:
    return normalize_crust_price_addition(price_addition, product_base_price)


class OrderService:
    """
    All order mutations go through this class.

    Instantiate per-request with the SQLAlchemy session:
        svc = OrderService(db)
    """

    def __init__(self, db: Session):
        self._db = db

    # ── Internal helpers ──────────────────────────────────────────────────────

    _ORDER_CODE_CHARS = string.ascii_uppercase + string.digits  # A-Z + 0-9

    def _generate_order_code(self) -> str:
        for _ in range(20):
            code = "".join(random.choices(self._ORDER_CODE_CHARS, k=4))
            exists = self._db.query(Order).filter(Order.order_code == code).first()
            if not exists:
                return code
        return "".join(random.choices(self._ORDER_CODE_CHARS, k=6))

    def _get_order(self, order_id: str) -> Order:
        order = (
            self._db.query(Order)
            .options(joinedload(Order.items).joinedload(OrderItem.flavors))
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

    def _save_first_delivery_address(self, payload: CheckoutIn) -> None:
        if not payload.customer_id or not payload.delivery or payload.delivery.is_pickup:
            return
        if not payload.delivery.street or not payload.delivery.city:
            return
        has_address = (
            self._db.query(Address.id)
            .filter(Address.customer_id == payload.customer_id)
            .first()
            is not None
        )
        if has_address:
            return
        self._db.add(Address(
            id=str(uuid.uuid4()),
            customer_id=payload.customer_id,
            label="Primeiro pedido",
            street=payload.delivery.street.strip(),
            number=None,
            complement=payload.delivery.complement,
            neighborhood=payload.delivery.neighborhood,
            city=payload.delivery.city.strip(),
            zip_code=payload.delivery.zip_code,
            is_default=True,
        ))

    def _validate_item(
        self,
        item: CartItemIn,
        config: MultiFlavorsConfig,
    ) -> tuple[float, list[Product], ProductPriceResult, ProductSize | None, ProductCrustType | None]:
        """
        Returns (server_unit_price, [Product per flavor]).
        Raises domain exceptions on any inconsistency.

        Pricing: size_price (authoritative from DB) + crust/drink variant additions.
        Falls back to product.price when no size is configured for this product.
        """
        if len(item.flavors) != item.flavor_division:
            raise FlavorDivisionMismatch(item.product_id, item.flavor_division, len(item.flavors))

        if item.flavor_division > config.max_flavors:
            raise MaxFlavorsExceeded(item.flavor_division, config.max_flavors)

        # Fetch size price server-side (authoritative — client-submitted prices are ignored when size found)
        size_base_price: float | None = None
        selected_size_obj: ProductSize | None = None
        if item.selected_size_id:
            selected_size_obj = (
                self._db.query(ProductSize)
                .filter(ProductSize.id == item.selected_size_id,
                        ProductSize.product_id == item.product_id,
                        ProductSize.active == True)  # noqa: E712
                .first()
            )
            if selected_size_obj:
                size_base_price = selected_size_obj.price

        flavor_products: list[Product] = []
        slot_prices: list[float] = []

        for f in item.flavors:
            product = (
                self._db.query(Product)
                .filter(Product.id == f.product_id, Product.active == True)  # noqa: E712
                .first()
            )
            if not product:
                raise ProductNotFound(f.product_id)

            if size_base_price is not None:
                # Size-based: server price is authoritative, ignore client f.price
                slot_prices.append(size_base_price)
            else:
                # No size configured: validate submitted price against product base price
                if abs(product.price - f.price) > 0.01:
                    raise PriceConflict(product.name, f.price, product.price)
                slot_prices.append(product.price)

            flavor_products.append(product)

        # Apply pricing rule across slots
        division = item.flavor_division
        rule = config.pricing_rule
        if not slot_prices:
            server_price = 0.0
        elif rule == PricingRule.most_expensive:
            server_price = max(slot_prices)
        elif rule == PricingRule.average:
            server_price = sum(slot_prices) / len(slot_prices)
        else:  # proportional
            server_price = sum(p / division for p in slot_prices)
        server_price = round(server_price, 2)

        # Add crust type price addition if provided
        selected_crust_obj: ProductCrustType | None = None
        if item.selected_crust_type_id:
            selected_crust_obj = (
                self._db.query(ProductCrustType)
                .filter(ProductCrustType.id == item.selected_crust_type_id,
                        ProductCrustType.product_id == item.product_id,
                        ProductCrustType.active == True)  # noqa: E712
                .first()
            )
            if selected_crust_obj:
                primary_product = next((p for p in flavor_products if p.id == item.product_id), flavor_products[0] if flavor_products else None)
                crust_addition = _normalize_crust_price_addition(
                    selected_crust_obj.price_addition,
                    primary_product.price if primary_product else None,
                )
                if crust_addition > 0:
                    server_price = round(server_price + crust_addition, 2)

        # Add drink variant price addition if provided
        if item.selected_drink_variant_id:
            variant = (
                self._db.query(ProductDrinkVariant)
                .filter(ProductDrinkVariant.id == item.selected_drink_variant_id,
                        ProductDrinkVariant.product_id == item.product_id,
                        ProductDrinkVariant.active == True)  # noqa: E712
                .first()
            )
            if variant and variant.price_addition > 0:
                server_price = round(server_price + variant.price_addition, 2)

        primary_product = next((p for p in flavor_products if p.id == item.product_id), flavor_products[0] if flavor_products else None)
        if primary_product:
            pricing = ProductPricingService(self._db).calculate(
                product=primary_product,
                size=selected_size_obj,
                crust=selected_crust_obj,
                standard_price_override=server_price,
                flavor_count=item.flavor_division,
                flavor_product_ids=[flavor.product_id for flavor in item.flavors],
            )
            server_price = pricing.final_price
        else:
            pricing = ProductPriceResult(standard_price=server_price, final_price=server_price)

        return server_price, flavor_products, pricing, selected_size_obj, selected_crust_obj

    # ── Public API ────────────────────────────────────────────────────────────

    def quote_checkout(self, payload: CheckoutIn) -> dict:
        """Validate cart and calculate totals without creating an order."""
        if not payload.items:
            raise CartEmpty()

        if payload.customer_id:
            if not self._db.query(CustomerModel).filter(CustomerModel.id == payload.customer_id).first():
                raise DomainError(
                    "Conta nao encontrada. Faca login novamente para continuar.",
                    code="CustomerNotFound",
                )

        from backend.services.store_operation_service import StoreOperationService

        StoreOperationService(self._db).validate_order_allowed(
            is_scheduled=payload.delivery.is_scheduled if payload.delivery else False,
            scheduled_for=payload.delivery.scheduled_for if payload.delivery else None,
        )

        config = self._get_config()
        items: list[dict] = []
        subtotal = 0.0
        for item in payload.items:
            unit_price, flavor_products, pricing, size_obj, crust_obj = self._validate_item(item, config)
            line_total = round(unit_price * item.quantity, 2)
            subtotal += line_total
            items.append({
                "product_id": item.product_id,
                "quantity": item.quantity,
                "selected_size": item.selected_size,
                "selected_size_id": size_obj.id if size_obj else item.selected_size_id,
                "selected_crust_type_id": crust_obj.id if crust_obj else item.selected_crust_type_id,
                "selected_crust_type": item.selected_crust_type_name,
                "selected_drink_variant": item.selected_drink_variant_name,
                "unit_price": unit_price,
                "line_total": line_total,
                "standard_unit_price": pricing.standard_price,
                "promotion_applied": pricing.promotion_applied,
                "promotion_id": pricing.promotion_id,
                "promotion_name": pricing.promotion_name,
                "promotion_discount": pricing.discount_amount,
                "promotion_blocked": pricing.promotion_blocked,
                "promotion_block_reason": pricing.promotion_block_reason,
                "flavors": [
                    {"product_id": product.id, "name": product.name, "price": product.price}
                    for product in flavor_products
                ],
            })
        subtotal = round(subtotal, 2)

        from backend.services.shipping_service import ShippingService
        from backend.schemas.shipping_v2 import ShippingCalculateIn

        shipping_result = ShippingService(self._db).calculate(
            ShippingCalculateIn(
                city=payload.delivery.city,
                neighborhood=payload.delivery.neighborhood,
                zip_code=payload.delivery.zip_code,
                order_subtotal=subtotal,
                is_pickup=payload.delivery.is_pickup,
                is_scheduled=payload.delivery.is_scheduled,
            )
        )
        if not shipping_result.available:
            raise DomainError(shipping_result.message or "Entrega indisponivel para este pedido.")

        discount = 0.0
        coupon_payload = None
        delivery_fee_final = round(shipping_result.shipping_price, 2)
        if payload.coupon_code:
            from backend.services.coupon_service import CouponService
            from backend.schemas.coupon import CouponApplyIn
            coupon_result = CouponService(self._db).apply(
                CouponApplyIn(
                    code=payload.coupon_code,
                    order_subtotal=subtotal,
                    delivery_fee=shipping_result.shipping_price,
                    customer_id=payload.customer_id,
                    phone=payload.delivery.phone if payload.delivery else None,
                )
            )
            if not coupon_result.valid:
                raise DomainError(coupon_result.message, code="InvalidCoupon")
            coupon_payload = coupon_result.model_dump()
            discount = coupon_result.discount_amount
            delivery_fee_final = coupon_result.delivery_fee_final

        total = round(subtotal + delivery_fee_final - discount, 2)
        return {
            "items": items,
            "subtotal": subtotal,
            "shipping": shipping_result.model_dump(),
            "coupon": coupon_payload,
            "discount": discount,
            "delivery_fee_final": delivery_fee_final,
            "total": total,
            "payment_method": payload.payment_method,
        }

    def create_from_checkout(self, payload: CheckoutIn) -> Order:
        """
        Validate cart, recompute prices server-side, apply shipping + coupon,
        persist the order and fire OrderCreated event.

        Called by both the loja (REST endpoint) and ERP integrations.
        """
        if not payload.items:
            raise CartEmpty()

        if payload.customer_id:
            if not self._db.query(CustomerModel).filter(CustomerModel.id == payload.customer_id).first():
                raise DomainError(
                    "Conta não encontrada. Faça login novamente para continuar.",
                    code="CustomerNotFound",
                )

        from backend.services.store_operation_service import StoreOperationService

        StoreOperationService(self._db).validate_order_allowed(
            is_scheduled=payload.delivery.is_scheduled if payload.delivery else False,
            scheduled_for=payload.delivery.scheduled_for if payload.delivery else None,
        )

        config = self._get_config()

        # 1. Validate items and compute subtotal
        item_data: list[tuple[CartItemIn, float, list[Product], ProductPriceResult, ProductSize | None, ProductCrustType | None]] = []
        subtotal = 0.0
        for item in payload.items:
            unit_price, flavor_products, pricing, size_obj, crust_obj = self._validate_item(item, config)
            subtotal += unit_price * item.quantity
            item_data.append((item, unit_price, flavor_products, pricing, size_obj, crust_obj))
        subtotal = round(subtotal, 2)

        # 2. Shipping — delegated to ShippingService (lazy import avoids circular)
        from backend.services.shipping_service import ShippingService
        from backend.schemas.shipping_v2 import ShippingCalculateIn
        shipping_result = ShippingService(self._db).calculate(
            ShippingCalculateIn(
                city=payload.delivery.city,
                neighborhood=payload.delivery.neighborhood,
                zip_code=payload.delivery.zip_code,
                order_subtotal=subtotal,
                is_pickup=payload.delivery.is_pickup,
                is_scheduled=payload.delivery.is_scheduled,
            )
        )
        if not shipping_result.available:
            raise DomainError(shipping_result.message or "Entrega indisponível para este pedido.")
        shipping_fee = shipping_result.shipping_price

        # 3. Coupon
        discount = 0.0
        resolved_coupon_id: str | None = None
        coupon_code: str | None = None
        gift_result = None
        delivery_fee_original = round(shipping_fee, 2)
        delivery_fee_discount = 0.0
        delivery_fee_final = round(shipping_fee, 2)
        free_shipping_applied = False
        if payload.coupon_code:
            from backend.services.coupon_service import CouponService
            from backend.schemas.coupon import CouponApplyIn
            coupon_result = CouponService(self._db).apply(
                CouponApplyIn(
                    code=payload.coupon_code,
                    order_subtotal=subtotal,
                    delivery_fee=shipping_fee,
                    customer_id=payload.customer_id,
                    phone=payload.delivery.phone if payload.delivery else None,
                )
            )
            if not coupon_result.valid:
                raise DomainError(coupon_result.message, code="InvalidCoupon")
            discount = coupon_result.discount_amount
            resolved_coupon_id = coupon_result.coupon_id
            coupon_code = coupon_result.coupon_code
            gift_result = coupon_result.gift
            delivery_fee_original = coupon_result.delivery_fee_original
            delivery_fee_discount = coupon_result.delivery_fee_discount
            delivery_fee_final = coupon_result.delivery_fee_final
            free_shipping_applied = coupon_result.free_shipping_applied

        # 4. Build order
        total = round(subtotal + delivery_fee_final - discount, 2)
        order_id = f"order-{uuid.uuid4().hex[:8]}"
        external_reference = order_id
        order_code = self._generate_order_code()
        order = Order(
            id=order_id,
            order_code=order_code,
            external_reference=external_reference,
            customer_id=payload.customer_id,
            delivery_name=payload.delivery.name,
            delivery_phone=payload.delivery.phone,
            delivery_street=payload.delivery.street,
            delivery_city=payload.delivery.city,
            delivery_complement=payload.delivery.complement,
            status=OrderStatus.aguardando_pagamento,
            coupon_id=resolved_coupon_id,
            campaign_id=payload.campaign_id,
            utm_source=payload.utm_source,
            utm_medium=payload.utm_medium,
            utm_campaign=payload.utm_campaign,
            utm_content=payload.utm_content,
            utm_term=payload.utm_term,
            session_id=payload.session_id,
            landing_page=payload.landing_page,
            referrer=payload.referrer,
            subtotal=subtotal,
            shipping_fee=delivery_fee_final,
            delivery_fee_original=delivery_fee_original,
            delivery_fee_discount=delivery_fee_discount,
            delivery_fee_final=delivery_fee_final,
            free_shipping_applied=free_shipping_applied,
            discount=discount,
            total=total,
            estimated_time=shipping_result.estimated_time,
            is_scheduled=payload.delivery.is_scheduled,
            scheduled_for=payload.delivery.scheduled_for,
        )
        self._db.add(order)
        self._db.flush()
        self._save_first_delivery_address(payload)

        payment_method = PaymentMethod(payload.payment_method) if payload.payment_method in PaymentMethod._value2member_map_ else PaymentMethod.pix
        self._db.add(Payment(
            id=str(uuid.uuid4()),
            order_id=order.id,
            method=payment_method,
            status=PaymentStatus.pending,
            amount=total,
            gateway="mercadopago",
            provider="mercado_pago",
            external_reference=external_reference,
        ))
        self._db.flush()

        # 5. Order items and flavor breakdown
        for item, unit_price, flavor_products, pricing, size_obj, crust_obj in item_data:
            oi = OrderItem(
                id=str(uuid.uuid4()),
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                selected_size=item.selected_size,
                selected_size_id=size_obj.id if size_obj else item.selected_size_id,
                flavor_division=item.flavor_division,
                flavor_count=item.flavor_division,
                selected_crust_type_id=crust_obj.id if crust_obj else item.selected_crust_type_id,
                selected_crust_type=item.selected_crust_type_name,
                selected_drink_variant=item.selected_drink_variant_name,
                notes=item.notes,
                unit_price=unit_price,
                total_price=round(unit_price * item.quantity, 2),
                standard_unit_price=pricing.standard_price,
                applied_unit_price=pricing.final_price,
                original_price=pricing.standard_price,
                is_gift=False,
                promotion_id=pricing.promotion_id,
                promotion_name=pricing.promotion_name,
                promotion_discount=pricing.discount_amount,
                promotion_blocked=pricing.promotion_blocked,
                promotion_block_reason=pricing.promotion_block_reason,
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

        if gift_result:
            gift_item = OrderItem(
                id=str(uuid.uuid4()),
                order_id=order.id,
                product_id=gift_result.product_id,
                quantity=gift_result.quantity,
                selected_size="Brinde",
                selected_size_id=None,
                flavor_division=1,
                flavor_count=1,
                unit_price=0.0,
                total_price=0.0,
                standard_unit_price=gift_result.original_price,
                applied_unit_price=0.0,
                original_price=gift_result.original_price,
                is_gift=True,
                gift_reason="coupon",
                coupon_id=resolved_coupon_id,
                coupon_code=coupon_code,
                notes=f"Brinde do cupom {coupon_code}" if coupon_code else "Brinde do cupom",
            )
            self._db.add(gift_item)

        # 6. Record coupon usage
        if resolved_coupon_id:
            from backend.services.coupon_service import CouponService
            CouponService(self._db).record_usage(
                coupon_id=resolved_coupon_id,
                customer_id=payload.customer_id,
                phone=payload.delivery.phone if payload.delivery else None,
                order_id=order.id,
            )

        sync_customer_order_metrics(self._db, order.customer_id)
        self._db.commit()
        self._db.refresh(order)

        if payload.session_id:
            try:
                from backend.schemas.paid_traffic import TrackingEventIn
                from backend.services.paid_traffic_service import PaidTrafficService
                from backend.database import SessionLocal

                with SessionLocal() as tracking_db:
                    PaidTrafficService(tracking_db).record_event(TrackingEventIn(
                        session_id=payload.session_id,
                        campaign_id=payload.campaign_id,
                        event_type="order_created",
                        value=order.total,
                        path=payload.landing_page,
                        landing_page=payload.landing_page,
                        referrer=payload.referrer,
                        utm_source=payload.utm_source,
                        utm_medium=payload.utm_medium,
                        utm_campaign=payload.utm_campaign,
                        utm_content=payload.utm_content,
                        utm_term=payload.utm_term,
                        metadata={"order_id": order.id},
                    ))
            except Exception:
                pass

        # 7. Publish event (after commit — DB is consistent)
        bus.publish(OrderCreated(
            order_id=order.id,
            customer_name=payload.delivery.name,
            total=order.total,
            items_count=sum(i.quantity for i in payload.items) + (gift_result.quantity if gift_result else 0),
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

        now = datetime.now(timezone.utc)
        if new_status in ("paid", "pago") and not order.paid_at:
            order.paid_at = now
        if new_status == "preparing" and not order.preparation_started_at:
            order.preparation_started_at = now
        if new_status == "on_the_way" and not order.out_for_delivery_at:
            order.out_for_delivery_at = now
        if new_status == "delivered" and not order.delivered_at:
            order.delivered_at = now
            if order.paid_at:
                order.total_time_minutes = int((now - order.paid_at).total_seconds() / 60)
            if order.out_for_delivery_at:
                order.delivery_time_minutes = int((now - order.out_for_delivery_at).total_seconds() / 60)
            if order.paid_at and order.out_for_delivery_at:
                order.preparation_time_minutes = int((order.out_for_delivery_at - order.paid_at).total_seconds() / 60)
            elif order.preparation_started_at and order.out_for_delivery_at:
                order.preparation_time_minutes = int((order.out_for_delivery_at - order.preparation_started_at).total_seconds() / 60)

        self._db.flush()
        sync_customer_order_metrics(self._db, order.customer_id)
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
            self._db.flush()
            sync_customer_order_metrics(self._db, order.customer_id)
            self._db.commit()

        self._db.refresh(order)
        return order

    def cancel(
        self,
        order_id: str,
        *,
        reason: str = "",
        changed_by: str = "system",
        cancelled_by: str = "system",
    ) -> Order:
        """Cancels an order through the state machine, recording who cancelled."""
        order = self.change_status(order_id, "cancelled", changed_by=changed_by)
        now = datetime.now(timezone.utc)
        order.cancelled_by = cancelled_by
        order.cancellation_reason = reason or None
        order.cancelled_at = now
        self._db.flush()
        self._db.commit()
        self._db.refresh(order)
        bus.publish(EvOrderCancelled(
            order_id=order_id,
            reason=reason,
            refund_required=order.payment is not None,
        ))
        return order

    def auto_cancel_expired(self, *, hours: int = 2) -> list[str]:
        """Cancel all orders stuck in pagamento_expirado for longer than `hours` hours."""
        from backend.models.order import OrderStatus as OS
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        expired_orders = (
            self._db.query(Order)
            .filter(
                Order.status == OS.pagamento_expirado,
                Order.updated_at <= cutoff,
                Order.cancelled_by.is_(None),
            )
            .all()
        )
        cancelled_ids: list[str] = []
        for order in expired_orders:
            try:
                self.cancel(
                    order.id,
                    reason="PIX não pago — cancelado automaticamente pelo sistema",
                    changed_by="system",
                    cancelled_by="system",
                )
                cancelled_ids.append(order.id)
            except Exception:
                pass
        return cancelled_ids

    def get(self, order_id: str) -> Order:
        return self._get_order(order_id)

    def list(
        self,
        *,
        status: str | None = None,
        customer_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
    ) -> list[Order]:
        q = self._db.query(Order).options(joinedload(Order.items).joinedload(OrderItem.flavors))
        if status:
            q = q.filter(Order.status == OrderStatus(status))
        if customer_id:
            q = q.filter(Order.customer_id == customer_id)
        if date_from:
            q = q.filter(Order.created_at >= date_from)
        if date_to:
            q = q.filter(Order.created_at <= date_to)
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

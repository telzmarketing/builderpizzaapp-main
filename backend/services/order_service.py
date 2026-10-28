"""
OrderService — single authoritative source of truth for all order operations.

RULE: nothing outside this class may change an order's status or
      mutate its financial fields. The state machine enforces valid transitions.
      ERP and the loja both call these methods — never bypass them.
"""
from __future__ import annotations

import random
import string
import unicodedata
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.core.exceptions import (
    CartEmpty, OrderNotFound, OrderCancelled,
    ProductNotFound, PriceConflict,
    FlavorDivisionMismatch, MaxFlavorsExceeded,
    FixedFlavorCombinationNotAllowed,
    DomainError,
)
from backend.core.state_machine import order_sm, payment_sm
from backend.core.tenant_context import TenantContext, TenantSource
from backend.core.tenant_ownership import (
    assign_tenant_on_create,
    customers_orders_enforcement_enabled,
    identity_catalog_enforcement_enabled,
    operations_enforcement_enabled,
    scope_query_to_tenant,
)
from backend.core.events import (
    bus, OrderCreated, OrderStatusChanged, OrderCancelled as EvOrderCancelled, PaymentConfirmed,
)
from backend.models.order import Order, OrderItem, OrderItemFlavor, OrderStatus
from backend.models.payment import Payment, PaymentMethod, PaymentStatus
from backend.models.payment_config import PaymentGatewayConfig
from backend.models.paid_traffic import CampaignLink, TrafficCampaign
from backend.models.product import Product, MultiFlavorsConfig, PricingRule, ProductCrustType, ProductDrinkVariant, ProductSize
from backend.models.customer import Address, Customer as CustomerModel
from backend.schemas.order import CheckoutIn, CartItemIn, FlavorIn, OrderStatusUpdate
from backend.services.customer_metrics_service import sync_customer_order_metrics
from backend.services.product_pricing_service import ProductPriceResult, ProductPricingService, normalize_crust_price_addition
from backend.services.product_category_service import effective_capabilities


# ── Pricing helpers (shared with front-end logic) ─────────────────────────────

def _driver_delivery_fee_snapshot(shipping_result, *, is_pickup: bool, sales_channel: str) -> float | None:
    if is_pickup or sales_channel == "dine_in" or shipping_result.shipping_type != "by_distance":
        return None
    return round(shipping_result.shipping_price, 2)


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


def _clip_text(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_len]


def _normalize_size_label(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return (
        unicodedata.normalize("NFD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def _normalize_category_text(value: str | None) -> str:
    return (
        unicodedata.normalize("NFD", str(value or ""))
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
        .strip()
    )


def _is_fixed_flavor_combination(product: Product | None) -> bool:
    if not product:
        return False
    return "combinacoes de sabores" in {
        _normalize_category_text(product.category),
        _normalize_category_text(product.subcategory),
    }


def _product_price_for_selected_size(product: Product, selected_size: ProductSize) -> float:
    selected_label = _normalize_size_label(selected_size.label)
    if selected_label:
        matching_size = next(
            (
                size
                for size in product.sizes
                if size.active and _normalize_size_label(size.label) == selected_label
            ),
            None,
        )
        if matching_size:
            return float(matching_size.price)
    if product.id == selected_size.product_id:
        return float(selected_size.price)
    return float(product.price)


class OrderService:
    """
    All order mutations go through this class.

    Instantiate per-request with the SQLAlchemy session:
        svc = OrderService(db)
    """

    def __init__(self, db: Session, tenant_context: TenantContext | None = None):
        self._db = db
        self._tenant_context = tenant_context
        support_scoped = (
            tenant_context is not None
            and tenant_context.source == TenantSource.SUPPORT
        )
        self._orders_tenant_enabled = customers_orders_enforcement_enabled() or support_scoped
        self._catalog_tenant_enabled = identity_catalog_enforcement_enabled() or support_scoped
        self._operations_tenant_enabled = operations_enforcement_enabled() or support_scoped

    def _resource_context(self, enabled: bool):
        if self._tenant_context is None and enabled:
            from backend.core.tenant_context import TenantContextMissing
            raise TenantContextMissing("Contexto de tenant obrigatorio.")
        return self._tenant_context or TenantContext(tenant_id="tenant-legacy-default", source=TenantSource.JOB)

    def _tenant_query(self, model, *, catalog: bool = False):
        enabled = self._catalog_tenant_enabled if catalog else self._orders_tenant_enabled
        return scope_query_to_tenant(self._db.query(model), model, self._resource_context(enabled), enabled=True)

    def _own(self, resource, *, catalog: bool = False):
        enabled = self._catalog_tenant_enabled if catalog else self._orders_tenant_enabled
        return assign_tenant_on_create(resource, self._resource_context(enabled), enabled=True)

    def _operation_query(self, model):
        return scope_query_to_tenant(self._db.query(model), model, self._resource_context(self._operations_tenant_enabled), enabled=True)

    # ── Internal helpers ──────────────────────────────────────────────────────

    _ORDER_CODE_CHARS = string.ascii_uppercase + string.digits  # A-Z + 0-9

    def _generate_order_code(self) -> str:
        for _ in range(20):
            code = "".join(random.choices(self._ORDER_CODE_CHARS, k=4))
            exists = self._tenant_query(Order).filter(Order.order_code == code).first()
            if not exists:
                return code
        return "".join(random.choices(self._ORDER_CODE_CHARS, k=6))

    def _get_order(self, order_id: str) -> Order:
        order = (
            self._tenant_query(Order)
            .options(joinedload(Order.items).joinedload(OrderItem.flavors))
            .filter(Order.id == order_id)
            .first()
        )
        if not order:
            raise OrderNotFound(order_id)
        return order

    def _get_config(self) -> MultiFlavorsConfig:
        config_id = (
            f"multi-flavors-{self._tenant_context.tenant_id}"
            if self._tenant_context and (self._catalog_tenant_enabled or self._tenant_context.tenant_id != "tenant-legacy-default")
            else "default"
        )
        config = (
            self._tenant_query(MultiFlavorsConfig, catalog=True)
            .filter(MultiFlavorsConfig.id == config_id)
            .first()
        )
        if not config:
            config = MultiFlavorsConfig(id=config_id)
            self._own(config, catalog=True)
            self._db.add(config)
            self._db.flush()
        return config

    def _resolve_campaign_id(self, campaign_id: str | None, utm_campaign: str | None) -> str | None:
        candidate = _clip_text(campaign_id, 120)
        if candidate:
            query = self._db.query(TrafficCampaign.id).filter(TrafficCampaign.id == candidate)
            if self._tenant_context:
                query = query.filter(TrafficCampaign.tenant_id == self._tenant_context.tenant_id)
            exists = query.first()
            if exists:
                return candidate

        utm = _clip_text(utm_campaign, 200)
        if utm:
            query = self._db.query(CampaignLink).filter(CampaignLink.utm_campaign == utm)
            if self._tenant_context:
                query = query.filter(CampaignLink.tenant_id == self._tenant_context.tenant_id)
            link = query.first()
            if link:
                return link.campaign_id

        return None

    def _tracking_fields(self, payload: CheckoutIn) -> dict[str, str | None]:
        utm_campaign = _clip_text(payload.utm_campaign, 200)
        return {
            "campaign_id": self._resolve_campaign_id(payload.campaign_id, utm_campaign),
            "utm_source": _clip_text(payload.utm_source, 100),
            "utm_medium": _clip_text(payload.utm_medium, 100),
            "utm_campaign": utm_campaign,
            "utm_content": _clip_text(payload.utm_content, 200),
            "utm_term": _clip_text(payload.utm_term, 200),
            "session_id": _clip_text(payload.session_id, 120),
            "landing_page": _clip_text(payload.landing_page, 4000),
            "referrer": _clip_text(payload.referrer, 4000),
        }

    def _save_first_delivery_address(self, payload: CheckoutIn) -> None:
        if not payload.customer_id or not payload.delivery or payload.delivery.is_pickup:
            return
        if not payload.delivery.street or not payload.delivery.city:
            return
        has_address = (
            self._tenant_query(Address)
            .with_entities(Address.id)
            .filter(Address.customer_id == payload.customer_id)
            .first()
            is not None
        )
        if has_address:
            return
        address = Address(
            id=str(uuid.uuid4()),
            customer_id=payload.customer_id,
            label="Primeiro pedido",
            street=_clip_text(payload.delivery.street, 300) or "",
            number=None,
            complement=_clip_text(payload.delivery.complement, 100),
            neighborhood=_clip_text(payload.delivery.neighborhood, 100),
            city=_clip_text(payload.delivery.city, 100) or "",
            zip_code=_clip_text(payload.delivery.zip_code, 20),
            is_default=True,
        )
        self._own(address)
        self._db.add(address)

    def _validate_item(self, item: CartItemIn, config: MultiFlavorsConfig, *, channel: str = "delivery"):
        """Resolve selections and prices from the tenant catalog; client labels are hints only."""
        if len(item.flavors) != item.flavor_division:
            raise FlavorDivisionMismatch(item.product_id, item.flavor_division, len(item.flavors))
        if item.flavor_division > config.max_flavors:
            raise MaxFlavorsExceeded(item.flavor_division, config.max_flavors)
        product = self._tenant_query(Product, catalog=True).filter(Product.id == item.product_id, Product.active == True).first()
        if not product or product.product_type == "brinde":
            raise ProductNotFound(item.product_id)
        capabilities = effective_capabilities(self._db, product, self._tenant_context)
        visible = "visible_dine_in" if channel == "dine_in" else "visible_delivery"
        if not getattr(product, visible, True):
            raise DomainError("Produto indisponivel neste canal.", code="ProductChannelUnavailable")
        if item.selected_size_id and not capabilities["enable_sizes"]:
            raise DomainError("Este produto nao permite selecionar tamanho.", code="SizesUnavailable")
        if item.selected_crust_type_id and not capabilities["enable_dough"]:
            raise DomainError("Este produto nao permite selecionar massa.", code="DoughUnavailable")
        if item.selected_border_id and not capabilities["enable_border"]:
            raise DomainError("Este produto nao permite selecionar borda.", code="BorderUnavailable")
        if item.flavor_division > 1 and product.product_type not in {None, "pizza"}:
            raise DomainError("Este produto nao aceita multiplos sabores.", code="InvalidFlavorProductType")
        if _is_fixed_flavor_combination(product) and (item.flavor_division != 1 or item.flavors[0].product_id != product.id):
            raise FixedFlavorCombinationNotAllowed(product.name)

        def option(model, option_id, label):
            if not option_id:
                return None
            row = self._tenant_query(model, catalog=True).filter(model.id == option_id, model.product_id == product.id, model.active == True).first()
            if row is None:
                raise DomainError(f"{label} inexistente, inativo ou de outro produto.", code="InvalidProductOption")
            return row

        size = option(ProductSize, item.selected_size_id, "Tamanho") if capabilities["enable_sizes"] else None
        if size is None and capabilities["enable_sizes"] and any(candidate.active for candidate in product.sizes):
            raise DomainError("Selecione um tamanho valido.", code="ProductSizeRequired")
        crust = option(ProductCrustType, item.selected_crust_type_id, "Massa") if capabilities["enable_dough"] else None
        border = option(ProductCrustType, item.selected_border_id, "Borda") if capabilities["enable_border"] else None
        variant = option(ProductDrinkVariant, item.selected_drink_variant_id, "Variante")

        # Generic product options are authoritative for products that have an
        # explicit configuration. Client labels and prices are display hints;
        # the server resolves the tenant-owned rows and calculates the delta.
        option_price_addition = 0.0
        active_groups = [group for group in getattr(product, "option_groups", []) if group.active] if capabilities["enable_product_options"] else []
        if active_groups:
            selections_by_group: dict[str, list] = {}
            for selection in item.option_selections:
                selections_by_group.setdefault(selection.group_id, []).append(selection)
            known_group_ids = {group.id for group in active_groups}
            if any(group_id not in known_group_ids for group_id in selections_by_group):
                raise DomainError("Grupo de opcoes invalido para este produto.", code="InvalidProductOptionGroup")
            normalized_selections = []
            for group in active_groups:
                selections = selections_by_group.get(group.id, [])
                selected_count = sum(selection.quantity for selection in selections) if group.selection_type == "quantity" else len(selections)
                minimum = max(1 if group.required else 0, group.min_selections)
                if selected_count < minimum or (group.max_selections > 0 and selected_count > group.max_selections):
                    raise DomainError(f"Revise as opcoes obrigatorias de {group.name}.", code="InvalidProductOptionSelection")
                if group.selection_type == "single" and len(selections) > 1:
                    raise DomainError(f"Escolha apenas uma opcao em {group.name}.", code="InvalidProductOptionSelection")
                if group.selection_type == "text":
                    if len(selections) > 1 or (selections and not (selections[0].label or "").strip()):
                        raise DomainError(f"Texto invalido em {group.name}.", code="InvalidProductOptionSelection")
                    if selections:
                        normalized_selections.append({
                            "group_id": group.id,
                            "group_name": group.name,
                            "option_id": None,
                            "label": (selections[0].label or "").strip()[:300],
                            "quantity": 1,
                            "price_addition": 0,
                        })
                    continue
                seen_options: set[str] = set()
                for selection in selections:
                    if not selection.option_id or selection.option_id in seen_options:
                        raise DomainError(f"Opcao invalida em {group.name}.", code="InvalidProductOptionSelection")
                    selected_option = next((candidate for candidate in group.options if candidate.id == selection.option_id and candidate.active), None)
                    if selected_option is None:
                        raise DomainError(f"Opcao inexistente ou inativa em {group.name}.", code="InvalidProductOptionSelection")
                    seen_options.add(selected_option.id)
                    quantity = selection.quantity if group.selection_type == "quantity" else 1
                    option_price_addition += float(selected_option.price_addition or 0) * quantity
                    normalized_selections.append({
                        "group_id": group.id,
                        "group_name": group.name,
                        "option_id": selected_option.id,
                        "label": selected_option.name,
                        "quantity": quantity,
                        "price_addition": round(float(selected_option.price_addition or 0) * quantity, 2),
                    })
            item.option_selections = normalized_selections
        elif item.option_selections:
            raise DomainError("Este produto nao possui opcoes configuraveis.", code="ProductOptionsUnavailable")
        flavors = []
        prices = []
        filters = {_normalize_category_text(value) for value in (config.flavor_category_filters or [])}
        for flavor in item.flavors:
            row = self._tenant_query(Product, catalog=True).filter(Product.id == flavor.product_id, Product.active == True).first()
            if row is None or row.product_type == "brinde" or not getattr(row, visible, True):
                raise ProductNotFound(flavor.product_id)
            if item.flavor_division == 1 and row.id != product.id:
                raise DomainError("Sabor unico deve corresponder ao produto.", code="InvalidPrimaryFlavor")
            if item.flavor_division > 1:
                if row.product_type not in {None, "pizza"} or _is_fixed_flavor_combination(row):
                    raise DomainError("Produto invalido como sabor.", code="InvalidFlavorProductType")
                if filters and not ({_normalize_category_text(row.category), _normalize_category_text(row.subcategory)} & filters):
                    raise DomainError("Sabor fora das categorias permitidas.", code="FlavorCategoryUnavailable")
            flavors.append(row)
            if size:
                matching = next((candidate for candidate in row.sizes if candidate.active and _normalize_size_label(candidate.label) == _normalize_size_label(size.label)), None)
                if matching is None:
                    raise DomainError("Tamanho indisponivel para um dos sabores.", code="FlavorSizeUnavailable")
                prices.append(float(matching.price))
            else:
                prices.append(ProductPricingService.product_channel_price(row, channel))
        if product.id not in [row.id for row in flavors]:
            raise DomainError("O produto principal deve integrar a composicao.", code="InvalidPrimaryFlavor")
        rule = config.pricing_rule
        server_price = _compute_flavor_price(
            [FlavorIn(product_id=row.id, name=row.name, price=price, icon=row.icon or "") for row, price in zip(flavors, prices)],
            item.flavor_division,
            rule,
        )
        server_price += option_price_addition
        if crust:
            server_price += normalize_crust_price_addition(crust.price_addition, product.price)
        pricing = ProductPricingService(self._db, self._tenant_context).calculate(
            product=product, size=size, crust=crust, border=border, drink_variant=variant,
            channel=channel, standard_price_override=round(server_price, 2), flavor_count=item.flavor_division,
        )
        if not capabilities["enable_promotions"]:
            pricing = ProductPriceResult(standard_price=pricing.standard_price, final_price=pricing.standard_price)
        item.selected_size = size.label if size else "Unico"
        item.selected_crust_type_name = crust.name if crust else None
        item.selected_border_name = border.name if border else None
        item.selected_drink_variant_name = variant.name if variant else None
        return pricing.final_price, flavors, pricing, size, crust

    @staticmethod
    def _validate_expected_total(expected_total: float | None, total: float) -> None:
        if expected_total is not None and abs(round(expected_total, 2) - round(total, 2)) > 0.009:
            raise DomainError(f"O total mudou para R$ {total:.2f}. Revise o pedido antes de confirmar.", code="CheckoutPriceChanged")

    def _validate_inventory_items(self, items: list[CartItemIn]) -> None:
        from backend.services.inventory_service import ProductInventoryAvailabilityService
        ProductInventoryAvailabilityService(
            self._db, tenant_id=self._tenant_context.tenant_id if self._tenant_context else None,
            tenant_context=self._tenant_context,
        ).validate_cart_items(items)

    def _collect_promotion_gifts(
        self,
        item_data: list[tuple[CartItemIn, float, list[Product], ProductPriceResult, ProductSize | None, ProductCrustType | None]],
    ) -> list[dict]:
        gifts: dict[tuple[str, str], dict] = {}
        for item, _, _, pricing, _, _ in item_data:
            if not pricing.promotion_applied or not pricing.gift_enabled or not pricing.gift_product_id:
                continue
            product = (
                self._tenant_query(Product, catalog=True)
                .filter(Product.id == pricing.gift_product_id, Product.active == True)  # noqa: E712
                .first()
            )
            if not product:
                continue
            key = (pricing.promotion_id or "", product.id)
            quantity = max(1, int(pricing.gift_quantity or 1)) * item.quantity
            if key not in gifts:
                gifts[key] = {
                    "product_id": product.id,
                    "quantity": 0,
                    "original_price": round(float(product.price), 2),
                    "promotion_id": pricing.promotion_id,
                    "promotion_name": pricing.promotion_name or "Promocao",
                }
            gifts[key]["quantity"] += quantity
        return list(gifts.values())

    # ── Public API ────────────────────────────────────────────────────────────

    def quote_checkout(self, payload: CheckoutIn) -> dict:
        """Validate cart and calculate totals without creating an order."""
        if not payload.items:
            raise CartEmpty()

        if payload.customer_id:
            if not self._tenant_query(CustomerModel).filter(CustomerModel.id == payload.customer_id).first():
                raise DomainError(
                    "Conta nao encontrada. Faca login novamente para continuar.",
                    code="CustomerNotFound",
                )

        from backend.services.store_operation_service import StoreOperationService

        StoreOperationService(self._db, self._tenant_context.tenant_id if self._tenant_context else "default").validate_order_allowed(
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
                "selected_border_id": item.selected_border_id,
                "selected_border_name": item.selected_border_name,
                "selected_drink_variant_id": item.selected_drink_variant_id,
                "selected_drink_variant": item.selected_drink_variant_name,
                "unit_price": unit_price,
                "line_total": line_total,
                "standard_unit_price": pricing.standard_price,
                "promotion_applied": pricing.promotion_applied,
                "promotion_id": pricing.promotion_id,
                "promotion_name": pricing.promotion_name,
                "promotion_discount": pricing.discount_amount,
                "promotion_free_shipping": pricing.free_shipping,
                "promotion_gift_enabled": pricing.gift_enabled,
                "promotion_gift_product_id": pricing.gift_product_id,
                "promotion_gift_quantity": pricing.gift_quantity,
                "promotion_gift_name": pricing.gift_name,
                "promotion_gift_icon": pricing.gift_icon,
                "promotion_blocks_other_coupons": pricing.blocks_other_coupons,
                "promotion_blocked": pricing.promotion_blocked,
                "promotion_block_reason": pricing.promotion_block_reason,
                "flavors": [
                    {"product_id": product.id, "name": product.name, "price": product.price}
                    for product in flavor_products
                ],
            })
        self._validate_inventory_items(payload.items)
        subtotal = round(subtotal, 2)

        from backend.services.shipping_service import ShippingService
        from backend.schemas.shipping_v2 import ShippingCalculateIn

        shipping_result = ShippingService(self._db, self._tenant_context).calculate(
            ShippingCalculateIn(
                city=payload.delivery.city,
                street=payload.delivery.street,
                neighborhood=payload.delivery.neighborhood,
                zip_code=payload.delivery.zip_code,
                order_subtotal=subtotal,
                is_pickup=payload.delivery.is_pickup,
                is_scheduled=payload.delivery.is_scheduled,
                distance_km=payload.delivery.distance_km,
            )
        )
        if not shipping_result.available:
            raise DomainError(shipping_result.message or "Entrega indisponivel para este pedido.")

        discount = 0.0
        coupon_payload = None
        promotion_free_shipping = any(item.get("promotion_free_shipping") for item in items)
        coupon_blocker = next((item for item in items if item.get("promotion_blocks_other_coupons")), None)
        delivery_fee_final = round(shipping_result.shipping_price, 2)
        if payload.coupon_code:
            if coupon_blocker:
                raise DomainError(
                    f"O produto em promocao {coupon_blocker.get('promotion_name') or ''} nao permite usar cupom neste pedido.".strip(),
                    code="CouponBlockedByProductPromotion",
                )
            from backend.services.coupon_service import CouponService
            from backend.schemas.coupon import CouponApplyIn
            coupon_result = CouponService(self._db, self._tenant_context).apply(
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
        if promotion_free_shipping:
            delivery_fee_final = 0.0

        total = round(subtotal + delivery_fee_final - discount, 2)
        cash_change_amount = None
        if (
            payload.payment_method == "pay_on_delivery"
            and payload.delivery_payment_method == "cash"
            and payload.cash_needs_change
            and payload.cash_change_for is not None
        ):
            if payload.cash_change_for <= total:
                raise DomainError(
                    "O valor para troco deve ser maior que o total do pedido.",
                    code="InvalidCashChange",
                )
            cash_change_amount = round(payload.cash_change_for - total, 2)
        return {
            "items": items,
            "subtotal": subtotal,
            "shipping": shipping_result.model_dump(),
            "coupon": coupon_payload,
            "discount": discount,
            "delivery_fee_final": delivery_fee_final,
            "promotion_free_shipping_applied": promotion_free_shipping,
            "total": total,
            "payment_method": payload.payment_method,
            "cash_change_amount": cash_change_amount,
        }

    def create_from_checkout(
        self,
        payload: CheckoutIn,
        *,
        sales_channel: str = "delivery",
        payment_status: str = "pending",
        payment_source: str | None = None,
        external_reference_override: str | None = None,
        created_by_admin_id: str | None = None,
    ) -> Order:
        """
        Validate cart, recompute prices server-side, apply shipping + coupon,
        persist the order and fire OrderCreated event.

        Called by both the loja (REST endpoint) and ERP integrations.
        """
        if not payload.items:
            raise CartEmpty()
        if sales_channel not in {"counter", "delivery", "pickup", "dine_in"}:
            raise DomainError("Canal de venda invalido.", code="InvalidSalesChannel")
        if payment_status not in {"pending", "approved", "paid"}:
            raise DomainError("Situacao de pagamento invalida.", code="InvalidPaymentStatus")
        payment_approved = payment_status in {"approved", "paid"}
        if payment_approved and payment_source not in {None, "manual"}:
            raise DomainError("Pagamento aprovado exige uma origem validada.", code="PaymentEvidenceRequired")

        if payload.customer_id:
            if not self._tenant_query(CustomerModel).filter(CustomerModel.id == payload.customer_id).first():
                raise DomainError(
                    "Conta não encontrada. Faça login novamente para continuar.",
                    code="CustomerNotFound",
                )

        from backend.services.store_operation_service import StoreOperationService

        StoreOperationService(self._db, self._tenant_context.tenant_id if self._tenant_context else "default").validate_order_allowed(
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
        self._validate_inventory_items(payload.items)
        subtotal = round(subtotal, 2)
        coupon_blocker = next((pricing for _, _, _, pricing, _, _ in item_data if pricing.blocks_other_coupons), None)
        promotion_free_shipping = any(pricing.free_shipping for _, _, _, pricing, _, _ in item_data)
        promotion_gifts = self._collect_promotion_gifts(item_data)

        # 2. Shipping — delegated to ShippingService (lazy import avoids circular)
        from backend.services.shipping_service import ShippingService
        from backend.schemas.shipping_v2 import ShippingCalculateIn
        shipping_result = ShippingService(self._db, self._tenant_context).calculate(
            ShippingCalculateIn(
                city=payload.delivery.city,
                street=payload.delivery.street,
                neighborhood=payload.delivery.neighborhood,
                zip_code=payload.delivery.zip_code,
                order_subtotal=subtotal,
                is_pickup=payload.delivery.is_pickup,
                is_scheduled=payload.delivery.is_scheduled,
                distance_km=payload.delivery.distance_km,
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
            if coupon_blocker:
                raise DomainError(
                    f"O produto em promocao {coupon_blocker.promotion_name or ''} nao permite usar cupom neste pedido.".strip(),
                    code="CouponBlockedByProductPromotion",
                )
            from backend.services.coupon_service import CouponService
            from backend.schemas.coupon import CouponApplyIn
            coupon_result = CouponService(self._db, self._tenant_context).apply(
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

        if promotion_free_shipping and shipping_fee > 0:
            delivery_fee_original = round(shipping_fee, 2)
            delivery_fee_discount = delivery_fee_original
            delivery_fee_final = 0.0
            free_shipping_applied = True

        total = round(subtotal + delivery_fee_final - discount, 2)
        self._validate_expected_total(payload.expected_total, total)
        is_pay_on_delivery = payload.payment_method == "pay_on_delivery"
        delivery_payment_method = (payload.delivery_payment_method or "").strip().lower() if is_pay_on_delivery else None
        if is_pay_on_delivery:
            payment_config_query = self._db.query(PaymentGatewayConfig).filter(
                PaymentGatewayConfig.tenant_id == self._resource_context(self._orders_tenant_enabled).tenant_id
            )
            payment_config = payment_config_query.first()
            if payment_config and not payment_config.accept_cash:
                raise DomainError("Pagamento na entrega esta indisponivel no momento.", code="PaymentMethodDisabled")
        if is_pay_on_delivery and delivery_payment_method not in {"cash", "card"}:
            raise DomainError("Escolha se o pagamento na entrega sera em cartao ou dinheiro.", code="InvalidDeliveryPaymentMethod")
        cash_needs_change = bool(payload.cash_needs_change) if delivery_payment_method == "cash" else None
        cash_change_for = float(payload.cash_change_for or 0) if cash_needs_change else None
        if cash_change_for is not None and cash_change_for <= total:
            raise DomainError("O valor para troco deve ser maior que o total do pedido.", code="InvalidCashChange")

        payment_method = (
            PaymentMethod.cash
            if is_pay_on_delivery
            else PaymentMethod(payload.payment_method) if payload.payment_method in PaymentMethod._value2member_map_ else PaymentMethod.pix
        )

        # 4. Build order
        order_id = f"order-{uuid.uuid4().hex[:8]}"
        external_reference = external_reference_override or order_id
        order_code = self._generate_order_code()
        tracking = self._tracking_fields(payload)
        order = Order(
            id=order_id,
            order_code=order_code,
            external_reference=external_reference,
            customer_id=payload.customer_id,
            created_by_admin_id=created_by_admin_id,
            delivery_name=_clip_text(payload.delivery.name, 200) or "",
            delivery_phone=_clip_text(payload.delivery.phone, 30) or "",
            delivery_street=_clip_text(payload.delivery.street, 300) or "",
            delivery_city=_clip_text(payload.delivery.city, 100) or "",
            delivery_complement=_clip_text(payload.delivery.complement, 100),
            status=(OrderStatus.paid if (is_pay_on_delivery or payment_approved)
                    else OrderStatus.aguardando_pagamento),
            coupon_id=resolved_coupon_id,
            campaign_id=tracking["campaign_id"],
            utm_source=tracking["utm_source"],
            utm_medium=tracking["utm_medium"],
            utm_campaign=tracking["utm_campaign"],
            utm_content=tracking["utm_content"],
            utm_term=tracking["utm_term"],
            session_id=tracking["session_id"],
            landing_page=tracking["landing_page"],
            referrer=tracking["referrer"],
            fulfillment_type="pickup" if payload.delivery.is_pickup else "delivery",
            sales_channel=sales_channel,
            subtotal=subtotal,
            shipping_fee=delivery_fee_final,
            delivery_fee_original=delivery_fee_original,
            delivery_fee_discount=delivery_fee_discount,
            delivery_fee_final=delivery_fee_final,
            driver_delivery_fee=_driver_delivery_fee_snapshot(
                shipping_result,
                is_pickup=payload.delivery.is_pickup,
                sales_channel=sales_channel,
            ),
            free_shipping_applied=free_shipping_applied,
            discount=discount,
            total=total,
            estimated_time=shipping_result.estimated_time,
            is_scheduled=payload.delivery.is_scheduled,
            scheduled_for=payload.delivery.scheduled_for,
        )
        self._own(order)
        self._db.add(order)
        self._db.flush()
        self._save_first_delivery_address(payload)

        payment = Payment(
            id=str(uuid.uuid4()),
            order_id=order.id,
            method=payment_method,
            status=PaymentStatus.approved if payment_approved else PaymentStatus.pending,
            amount=total,
            gateway="on_delivery" if is_pay_on_delivery else ("manual" if payment_source == "manual" else "mercadopago"),
            provider="on_delivery" if is_pay_on_delivery else ("manual" if payment_source == "manual" else "mercado_pago"),
            external_reference=external_reference,
            currency="BRL",
            pay_on_delivery=is_pay_on_delivery,
            delivery_payment_method=delivery_payment_method,
            cash_needs_change=cash_needs_change,
            cash_change_for=cash_change_for,
            # For pay-on-delivery, the order is accepted for operations even
            # though the Payment remains pending until the courier collects it.
            # paid_at marks this operational confirmation timestamp for the
            # one-minute confirmation projection in the orders board.
            paid_at=datetime.now(timezone.utc) if (is_pay_on_delivery or payment_approved) else None,
        )
        self._own(payment)
        self._db.add(payment)
        self._db.flush()

        # 5. Order items and flavor breakdown
        from backend.services.cmv_snapshot_service import CmvOrderItemContext, OrderCmvSnapshotService

        cmv_contexts: list[CmvOrderItemContext] = []
        for item_position, (item, unit_price, flavor_products, pricing, size_obj, crust_obj) in enumerate(item_data):
            oi = OrderItem(
                id=str(uuid.uuid4()),
                order_id=order.id,
                product_id=item.product_id,
                position=item_position,
                quantity=item.quantity,
                selected_size=_clip_text(item.selected_size, 50),
                selected_size_id=size_obj.id if size_obj else item.selected_size_id,
                flavor_division=item.flavor_division,
                flavor_count=item.flavor_division,
                selected_crust_type_id=crust_obj.id if crust_obj else item.selected_crust_type_id,
                selected_crust_type=_clip_text(item.selected_crust_type_name, 100),
                selected_border_id=item.selected_border_id,
                selected_border_name=_clip_text(item.selected_border_name, 100),
                selected_drink_variant_id=item.selected_drink_variant_id,
                selected_drink_variant=_clip_text(item.selected_drink_variant_name, 100),
                notes=item.notes,
                add_ons=list(item.add_ons),
                option_selections=list(item.option_selections),
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
            self._own(oi)
            self._db.add(oi)
            self._db.flush()
            cmv_contexts.append(CmvOrderItemContext(order_item=oi, cart_item=item))
            for idx, (flavor_in, product) in enumerate(zip(item.flavors, flavor_products)):
                flavor = OrderItemFlavor(
                    id=str(uuid.uuid4()),
                    order_item_id=oi.id,
                    product_id=product.id,
                    flavor_name=product.name,
                    flavor_price=product.price,
                    position=idx,
                )
                self._own(flavor)
                self._db.add(flavor)

        if gift_result:
            gift_item = OrderItem(
                id=str(uuid.uuid4()),
                order_id=order.id,
                product_id=gift_result.product_id,
                position=len(cmv_contexts),
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
            self._own(gift_item)
            self._db.add(gift_item)
            self._db.flush()
            cmv_contexts.append(CmvOrderItemContext(order_item=gift_item))

        for gift in promotion_gifts:
            gift_item = OrderItem(
                id=str(uuid.uuid4()),
                order_id=order.id,
                product_id=gift["product_id"],
                position=len(cmv_contexts),
                quantity=gift["quantity"],
                selected_size="Brinde",
                selected_size_id=None,
                flavor_division=1,
                flavor_count=1,
                unit_price=0.0,
                total_price=0.0,
                standard_unit_price=gift["original_price"],
                applied_unit_price=0.0,
                original_price=gift["original_price"],
                is_gift=True,
                gift_reason="product_promotion",
                promotion_id=gift["promotion_id"],
                promotion_name=gift["promotion_name"],
                notes=f"Brinde da promocao {gift['promotion_name']}",
            )
            self._own(gift_item)
            self._db.add(gift_item)
            self._db.flush()
            cmv_contexts.append(CmvOrderItemContext(order_item=gift_item))

        OrderCmvSnapshotService(
            self._db,
            tenant_id=order.tenant_id,
            tenant_context=self._tenant_context,
        ).create_for_order(order, cmv_contexts)

        # 6. Record coupon usage
        if resolved_coupon_id:
            from backend.services.coupon_service import CouponService
            CouponService(self._db, self._tenant_context).record_usage(
                coupon_id=resolved_coupon_id,
                customer_id=payload.customer_id,
                phone=payload.delivery.phone if payload.delivery else None,
                order_id=order.id,
            )

        sync_customer_order_metrics(self._db, order.customer_id, tenant_id=order.tenant_id)
        from backend.services.automation_event_producer import AutomationEventProducer
        AutomationEventProducer(self._db, order.tenant_id).order_created(order)
        self._db.commit()
        self._db.refresh(order)

        if tracking["session_id"]:
            try:
                from backend.schemas.paid_traffic import TrackingEventIn
                from backend.services.paid_traffic_service import PaidTrafficService
                from backend.database import SessionLocal

                with SessionLocal() as tracking_db:
                    PaidTrafficService(tracking_db).record_event(TrackingEventIn(
                        session_id=tracking["session_id"],
                        campaign_id=tracking["campaign_id"],
                        event_type="order_created",
                        value=order.total,
                        path=tracking["landing_page"],
                        landing_page=tracking["landing_page"],
                        referrer=tracking["referrer"],
                        utm_source=tracking["utm_source"],
                        utm_medium=tracking["utm_medium"],
                        utm_campaign=tracking["utm_campaign"],
                        utm_content=tracking["utm_content"],
                        utm_term=tracking["utm_term"],
                        metadata={"order_id": order.id},
                    ))
            except Exception:
                pass

        # 7. Publish event (after commit — DB is consistent)
        self._notify_new_order_whatsapp(order)
        bus.publish(OrderCreated(
            order_id=order.id,
            customer_name=payload.delivery.name,
            total=order.total,
            items_count=sum(i.quantity for i in payload.items) + (gift_result.quantity if gift_result else 0),
            delivery_city=payload.delivery.city,
            tenant_id=order.tenant_id,
        ))

        return order

    def _notify_new_order_whatsapp(self, order: Order) -> None:
        try:
            from backend.services.order_whatsapp_notification_service import OrderWhatsAppNotificationService

            OrderWhatsAppNotificationService(
                self._db,
                self._tenant_context.tenant_id if self._tenant_context else None,
            ).notify_new_order(order)
        except Exception:
            self._db.rollback()
            pass

    def create_from_table_session(self, table_session_id: str, *, payment_method: str = "cash") -> Order:
        """
        Materialize a dine-in table session as a real order.

        Salao keeps its own operational comanda, but the finalized kitchen/order
        record still goes through the central OrderService and the shared orders
        table so BI, CRM and reports can filter by sales_channel=dine_in.
        """
        from backend.models.salao import TableSession

        session = (
            self._operation_query(TableSession)
            .options(joinedload(TableSession.items), joinedload(TableSession.table))
            .filter(TableSession.id == table_session_id)
            .with_for_update(of=TableSession)
            .first()
        )
        if not session:
            raise DomainError("Comanda nao encontrada.", code="TableSessionNotFound")
        if self._tenant_query(Order).filter(Order.table_session_id == table_session_id).first():
            raise DomainError("Esta comanda ja gerou um pedido do salao.", code="TableSessionOrderAlreadyExists")
        if not session.items:
            raise DomainError("Adicione itens na comanda antes de gerar o pedido.", code="TableSessionEmpty")
        from backend.services.salao_service import TableSessionService
        table_service = TableSessionService(self._db, self._tenant_context)
        carts = []
        for row in session.items:
            values = {key: getattr(row, key) for key in (
                "product_id", "quantity", "selected_size_id", "selected_crust_type_id", "selected_border_id",
                "selected_drink_variant_id", "flavor_division", "flavors",
            )}
            _, row.unit_price, configuration = table_service._configuration(values)
            for key, value in configuration.items():
                setattr(row, key, value)
            row.total_price = round(row.unit_price * row.quantity, 2)
            carts.append(CartItemIn(product_id=row.product_id, quantity=row.quantity, selected_size=row.selected_size or "Unico",
                selected_size_id=row.selected_size_id, selected_crust_type_id=row.selected_crust_type_id,
                selected_border_id=row.selected_border_id, selected_drink_variant_id=row.selected_drink_variant_id,
                flavor_division=row.flavor_division, flavors=row.flavors, final_price=row.unit_price))
        self._validate_inventory_items(carts)


        method = PaymentMethod(payment_method) if payment_method in PaymentMethod._value2member_map_ else PaymentMethod.cash
        subtotal = round(sum((item.total_price or 0.0) for item in session.items), 2)
        service_fee = round(float(session.service_fee or 0.0), 2)
        discount = round(float(session.discount or 0.0), 2)
        total = round(max(0.0, subtotal + service_fee - discount), 2)
        table_label = f"Mesa {session.table.number}" if session.table else "Salao"
        now = datetime.now(timezone.utc)

        order_id = f"order-{uuid.uuid4().hex[:8]}"
        order = Order(
            id=order_id,
            order_code=self._generate_order_code(),
            external_reference=order_id,
            customer_id=session.customer_id,
            delivery_name=table_label,
            delivery_phone="",
            delivery_street="Atendimento no salao",
            delivery_city="Salao",
            delivery_complement=session.waiter_name,
            status=OrderStatus.preparing,
            sales_channel="dine_in",
            fulfillment_type="dine_in",
            table_id=session.table_id,
            table_session_id=session.id,
            subtotal=subtotal,
            shipping_fee=service_fee,
            delivery_fee_original=service_fee,
            delivery_fee_discount=0.0,
            delivery_fee_final=service_fee,
            free_shipping_applied=False,
            discount=discount,
            total=total,
            estimated_time=0,
            notes=session.notes,
            preparation_started_at=now,
            target_delivery_minutes=0,
        )
        self._own(order)
        self._db.add(order)
        self._db.flush()

        from backend.services.cmv_snapshot_service import CmvOrderItemContext, OrderCmvSnapshotService

        items_count = 0
        cmv_contexts: list[CmvOrderItemContext] = []
        for item_position, item in enumerate(session.items):
            items_count += int(item.quantity or 0)
            order_item = OrderItem(
                id=str(uuid.uuid4()),
                order_id=order.id,
                product_id=item.product_id,
                position=item_position,
                quantity=item.quantity,
                selected_size=item.selected_size or "Salao",
                selected_size_id=item.selected_size_id,
                flavor_division=item.flavor_division,
                flavor_count=item.flavor_division,
                selected_crust_type_id=item.selected_crust_type_id,
                selected_crust_type=item.selected_crust_type_name,
                selected_border_id=item.selected_border_id,
                selected_border_name=item.selected_border_name,
                selected_drink_variant_id=item.selected_drink_variant_id,
                selected_drink_variant=item.selected_drink_variant_name,
                notes=item.notes,
                unit_price=item.unit_price,
                total_price=item.total_price,
                standard_unit_price=item.unit_price,
                applied_unit_price=item.unit_price,
                original_price=item.unit_price,
                is_gift=False,
            )
            self._own(order_item)
            self._db.add(order_item)
            self._db.flush()
            for position, flavor in enumerate(item.flavors or []):
                self._db.add(self._own(OrderItemFlavor(
                    id=str(uuid.uuid4()), order_item_id=order_item.id,
                    product_id=flavor["product_id"], flavor_name=flavor["name"],
                    flavor_price=flavor["price"], position=position,
                )))
            cmv_contexts.append(CmvOrderItemContext(order_item=order_item))

        payment = Payment(
            id=str(uuid.uuid4()),
            order_id=order.id,
            method=method,
            status=PaymentStatus.pending,
            amount=total,
            gateway="dine_in",
            provider="salao",
            external_reference=order.external_reference,
            currency="BRL",
            pay_on_delivery=False,
        )
        self._own(payment)
        self._db.add(payment)

        session.subtotal = subtotal
        session.total = total
        session.status = "pending_payment"
        session.updated_at = now
        OrderCmvSnapshotService(
            self._db,
            tenant_id=order.tenant_id,
            tenant_context=self._tenant_context,
        ).create_for_order(order, cmv_contexts)
        self._db.flush()
        self._consume_inventory_for_effective_sale(order.id)
        sync_customer_order_metrics(self._db, order.customer_id, tenant_id=order.tenant_id)
        from backend.services.automation_event_producer import AutomationEventProducer
        AutomationEventProducer(self._db, order.tenant_id).order_created(order)
        self._db.commit()
        self._db.refresh(order)

        self._notify_new_order_whatsapp(order)

        bus.publish(OrderCreated(
            order_id=order.id,
            customer_name=table_label,
            total=order.total,
            items_count=items_count,
            delivery_city="Salao",
            tenant_id=order.tenant_id,
        ))
        return order

    def confirm_table_session_payment(self, table_session_id: str, *, payment_method: str = "cash") -> Order:
        """Confirm dine-in payment, close the table session and make BI revenue effective."""
        from backend.models.salao import TableSession

        order = (
            self._tenant_query(Order)
            .options(joinedload(Order.payment), joinedload(Order.table_session))
            .filter(Order.table_session_id == table_session_id, Order.sales_channel == "dine_in")
            .first()
        )
        if not order:
            order = self.create_from_table_session(table_session_id, payment_method=payment_method)
            order = (
                self._tenant_query(Order)
                .options(joinedload(Order.payment), joinedload(Order.table_session))
                .filter(Order.id == order.id)
                .first()
            )
        session = self._operation_query(TableSession).filter(TableSession.id == table_session_id).with_for_update().first()
        if not order or not session:
            raise DomainError("Comanda ou pedido do salao nao encontrado.", code="DineInOrderNotFound")

        method = PaymentMethod(payment_method) if payment_method in PaymentMethod._value2member_map_ else PaymentMethod.cash
        payment = order.payment or Payment(
            id=str(uuid.uuid4()),
            order_id=order.id,
            method=method,
            status=PaymentStatus.pending,
            amount=order.total,
            gateway="dine_in",
            provider="salao",
            external_reference=order.external_reference or order.id,
            currency="BRL",
        )
        self._own(payment)
        if payment.status not in {PaymentStatus.pending, PaymentStatus.approved, PaymentStatus.paid}:
            raise DomainError("Somente pagamentos pendentes podem ser confirmados.", code="PaymentNotPending")

        now = datetime.now(timezone.utc)
        if payment.status == PaymentStatus.pending:
            payment_sm.transition(payment.id, payment.status.value, PaymentStatus.approved.value)
            payment.status = PaymentStatus.approved
            payment.method = method
            payment.gateway = "dine_in"
            payment.provider = "salao"
            payment.amount = order.total
            payment.transaction_id = payment.transaction_id or f"SALAO-{uuid.uuid4().hex[:8].upper()}"
            payment.external_reference = payment.external_reference or order.external_reference or order.id
            payment.paid_at = payment.paid_at or now
            payment.updated_at = now
            self._db.add(payment)

        order.paid_at = order.paid_at or now
        order.updated_at = now
        session.status = "paid"
        session.closed_at = session.closed_at or now
        session.updated_at = now
        if session.table:
            session.table.status = "cleaning"

        self._db.flush()
        sync_customer_order_metrics(self._db, order.customer_id, tenant_id=order.tenant_id)
        from backend.services.automation_event_producer import AutomationEventProducer
        AutomationEventProducer(self._db, order.tenant_id).payment_confirmed(
            payment, order.customer_id
        )
        self._db.commit()
        self._db.refresh(order)

        bus.publish(PaymentConfirmed(
            payment_id=payment.id,
            order_id=order.id,
            amount=payment.amount,
            gateway=payment.gateway,
            transaction_id=payment.transaction_id or "",
            tenant_id=payment.tenant_id,
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

        if order.fulfillment_type == "dine_in" and new_status == "on_the_way":
            raise DomainError("Pedido do salao deve ser servido sem rota de entrega.", code="DineInDeliveryNotAllowed")

        if new_status == "preparing" and current in {"paid", "pago", "ready_for_pickup"} and not changed_by.startswith("kds:"):
            raise DomainError("A entrada ou o retorno à cozinha deve ser confirmado pelo KDS.", code="KdsActionRequired")

        if new_status in {"ready_for_pickup", "on_the_way"}:
            from backend.services.kds_production_service import ensure_kds_units_ready
            ensure_kds_units_ready(self._db, order.tenant_id, order.id)
        if new_status == "ready_for_pickup":
            from backend.models.kds_production import ProductionUnit, ProductionAttempt
            units = self._db.query(ProductionUnit).filter(
                ProductionUnit.tenant_id == order.tenant_id,
                ProductionUnit.order_id == order.id,
            ).all()
            if units:
                if not changed_by.startswith("kds:"):
                    raise DomainError("O KDS deve confirmar todas as unidades antes de liberar o pedido.", code="KdsActionRequired")
                expected_units = sum(max(0, int(item.quantity or 0)) for item in order.items)
                if len(units) != expected_units:
                    raise DomainError("A fila de produção não contém todas as unidades físicas do pedido.", code="KdsUnitsIncomplete")
                attempts = self._db.query(ProductionAttempt).filter(
                    ProductionAttempt.tenant_id == order.tenant_id,
                    ProductionAttempt.production_unit_id.in_([unit.id for unit in units]),
                ).order_by(ProductionAttempt.production_unit_id, ProductionAttempt.attempt_number).all()
                latest_by_unit = {}
                for attempt in attempts:
                    latest_by_unit[attempt.production_unit_id] = attempt
                if any(
                    unit.state != "ready"
                    or latest_by_unit.get(unit.id) is None
                    or latest_by_unit[unit.id].state != "ready"
                    for unit in units
                ):
                    raise DomainError("Todas as unidades físicas precisam estar prontas no KDS.", code="KdsUnitsPending")

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
        if new_status == "ready_for_pickup" and not order.ready_for_pickup_at:
            order.ready_for_pickup_at = now
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
        # Returning a ready order to the kitchen preserves its prior stock
        # consumption. Rework attempts consume their own frozen composition.
        if new_status == "preparing" and current != "ready_for_pickup":
            self._consume_inventory_for_effective_sale(order.id)
        if new_status in {"cancelled", "refunded"}:
            self._reverse_inventory_for_cancelled_sale(order.id)
        sync_customer_order_metrics(self._db, order.customer_id, tenant_id=order.tenant_id)
        from backend.services.automation_event_producer import AutomationEventProducer
        AutomationEventProducer(self._db, order.tenant_id).order_status_changed(
            order, old_status, new_status
        )
        self._db.commit()

        bus.publish(OrderStatusChanged(
            order_id=order_id,
            from_status=old_status,
            to_status=new_status,
            changed_by=changed_by,
            tenant_id=order.tenant_id,
        ))

        # Award loyalty points when delivered
        if new_status == "delivered" and order.customer_id:
            from backend.services.loyalty_service import award_points_for_order
            points = award_points_for_order(
                order.customer_id, order_id, order.total, self._db
            )
            order.loyalty_points_earned = points
            self._db.flush()
            sync_customer_order_metrics(self._db, order.customer_id, tenant_id=order.tenant_id)
            self._db.commit()

        self._db.refresh(order)
        return order

    def complete_customer_pickup(
        self,
        order_id: str,
        *,
        changed_by: str = "system",
    ) -> Order:
        """Complete a pickup without opening a delivery-flow status shortcut.

        ``ready_for_pickup -> delivered`` is intentionally absent from the
        global state graph.  Only an order explicitly owned by the pickup flow
        may use this operation.
        """
        order = self._get_order(order_id)
        current = order.status.value if hasattr(order.status, "value") else str(order.status)
        if order.fulfillment_type != "pickup":
            raise DomainError(
                "Somente pedidos para retirada podem usar esta acao.",
                code="KdsPickupOnly",
            )
        if current != OrderStatus.ready_for_pickup.value:
            raise DomainError(
                "O pedido para retirada ainda nao esta pronto.",
                code="KdsPickupNotReady",
            )

        order_sm.complete_local_fulfillment(order.id, current, fulfillment_type=order.fulfillment_type)
        now = datetime.now(timezone.utc)
        order.status = OrderStatus.delivered
        order.updated_at = now
        order.delivered_at = order.delivered_at or now
        if order.paid_at:
            order.total_time_minutes = int((now - order.paid_at).total_seconds() / 60)
        self._db.flush()
        sync_customer_order_metrics(self._db, order.customer_id, tenant_id=order.tenant_id)
        from backend.services.automation_event_producer import AutomationEventProducer
        AutomationEventProducer(self._db, order.tenant_id).order_status_changed(
            order, current, OrderStatus.delivered.value
        )
        self._db.commit()

        bus.publish(OrderStatusChanged(
            order_id=order_id,
            from_status=current,
            to_status=OrderStatus.delivered.value,
            changed_by=changed_by,
            tenant_id=order.tenant_id,
        ))
        if order.customer_id:
            from backend.services.loyalty_service import award_points_for_order
            points = award_points_for_order(
                order.customer_id, order_id, order.total, self._db
            )
            order.loyalty_points_earned = points
            self._db.flush()
            sync_customer_order_metrics(self._db, order.customer_id, tenant_id=order.tenant_id)
            self._db.commit()

        self._db.refresh(order)
        return order

    def serve_table_session(self, session_id: str, *, changed_by: str = "system") -> Order:
        order = self._tenant_query(Order).filter(Order.table_session_id == session_id, Order.fulfillment_type == "dine_in").first()
        if not order:
            raise DomainError("Pedido do salao nao encontrado.", code="DineInOrderNotFound")
        return self.serve_dine_in(order.id, changed_by=changed_by)

    def serve_dine_in(self, order_id: str, *, changed_by: str = "system") -> Order:
        order = self._get_order(order_id)
        if order.fulfillment_type != "dine_in":
            raise DomainError("Somente pedidos do salao podem ser servidos.", code="DineInOnly")
        current = order.status.value if hasattr(order.status, "value") else str(order.status)
        order_sm.complete_local_fulfillment(order.id, current, fulfillment_type="dine_in")
        now = datetime.now(timezone.utc)
        order.status = OrderStatus.delivered
        order.delivered_at = now
        order.updated_at = now
        self._db.flush()
        sync_customer_order_metrics(self._db, order.customer_id, tenant_id=order.tenant_id)
        from backend.services.automation_event_producer import AutomationEventProducer
        AutomationEventProducer(self._db, order.tenant_id).order_status_changed(order, current, "delivered")
        self._db.commit()
        bus.publish(OrderStatusChanged(order_id=order.id, from_status=current, to_status="delivered", changed_by=changed_by, tenant_id=order.tenant_id))
        self._db.refresh(order)
        return order

    def _consume_inventory_for_effective_sale(self, order_id: str) -> None:
        from backend.services.inventory_service import InventoryService

        order = self._get_order(order_id)
        InventoryService(self._db, order.tenant_id, self._tenant_context).consume_order_sale(order_id)

    def _reverse_inventory_for_cancelled_sale(self, order_id: str) -> None:
        from backend.services.inventory_service import InventoryService

        order = self._get_order(order_id)
        InventoryService(self._db, order.tenant_id, self._tenant_context).reverse_order_sale(order_id)

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
            tenant_id=order.tenant_id,
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

    def delete(self, order_id: str) -> None:
        order = self._get_order(order_id)

        from backend.models.agente_whatsapp import AgenteWhatsAppEvent
        from backend.models.customer_event import CustomerEvent
        from backend.models.delivery import Delivery, DeliveryEarning, DeliveryEvent
        from backend.models.inventory import InventoryStockMovement
        from backend.models.loyalty import LoyaltyBenefitUsage, LoyaltyTransaction
        from backend.models.store_notification import StoreNotificationCaptured, StoreNotificationImpression
        from backend.models.upsell import OrderUpsell, UpsellEvent

        has_inventory_movements = (
            self._db.query(InventoryStockMovement.id)
            .filter(
                InventoryStockMovement.source_type.in_(["order_sale", "foundation_order_sale", "order_sale_reversal", "order_sale_loss"]),
                InventoryStockMovement.tenant_id == order.tenant_id,
                InventoryStockMovement.source_id == order_id,
            )
            .first()
        )
        if has_inventory_movements:
            raise DomainError(
                "Pedido possui movimentacao de estoque e nao pode ser excluido fisicamente. Cancele ou estorne pelo fluxo operacional.",
                code="OrderHasInventoryMovements",
            )

        delivery = self._db.query(Delivery).filter(Delivery.order_id == order_id).first()
        if delivery:
            self._db.query(DeliveryEarning).filter(DeliveryEarning.delivery_id == delivery.id).delete(synchronize_session=False)
            self._db.query(DeliveryEvent).filter(DeliveryEvent.delivery_id == delivery.id).delete(synchronize_session=False)
            self._db.delete(delivery)

        self._db.query(Payment).filter(Payment.order_id == order_id).delete(synchronize_session=False)
        self._db.query(OrderUpsell).filter(OrderUpsell.order_id == order_id).delete(synchronize_session=False)
        self._db.query(StoreNotificationCaptured).filter(StoreNotificationCaptured.order_id == order_id).delete(synchronize_session=False)

        for model in (
            AgenteWhatsAppEvent,
            CustomerEvent,
            LoyaltyBenefitUsage,
            LoyaltyTransaction,
            StoreNotificationImpression,
            UpsellEvent,
        ):
            self._db.query(model).filter(model.order_id == order_id).update(
                {"order_id": None},
                synchronize_session=False,
            )

        self._db.delete(order)
        try:
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise DomainError(
                "Pedido possui registros operacionais vinculados e nao pode ser excluido fisicamente. Cancele o pedido pelo fluxo operacional.",
                code="OrderHasOperationalRecords",
            ) from exc

    def list(
        self,
        *,
        status: str | None = None,
        customer_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sales_channel: str | None = None,
        limit: int = 50,
    ) -> list[Order]:
        q = self._tenant_query(Order).options(joinedload(Order.items).joinedload(OrderItem.flavors))
        if status:
            q = q.filter(Order.status == OrderStatus(status))
        if customer_id:
            q = q.filter(Order.customer_id == customer_id)
        if sales_channel:
            q = q.filter(Order.sales_channel == sales_channel)
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

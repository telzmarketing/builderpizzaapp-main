from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import ValidationError
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.models.agente_whatsapp import AgenteWhatsAppEvent, AgenteWhatsAppSession, AgenteWhatsAppToolCall
from backend.models.customer import Address, Customer
from backend.models.order import Order
from backend.models.product import Product, ProductCrustType, ProductDrinkVariant, ProductSize
from backend.models.product_promotion import ProductPromotion
from backend.models.promotion import Promotion
from backend.schemas.order import CartItemIn, CheckoutIn, FlavorIn
from backend.schemas.payment import PaymentCreate
from backend.schemas.coupon import CouponApplyIn
from backend.schemas.shipping_v2 import ShippingCalculateIn
from backend.services.coupon_service import CouponService
from backend.services.customer_identity_service import CustomerIdentityService, is_system_lead_email, normalize_phone
from backend.services.loyalty_service import get_available_benefits, get_customer_account
from backend.services.order_service import OrderService
from backend.services.payment_service import PaymentService
from backend.services.product_pricing_service import ProductPricingService
from backend.services.shipping_service import ShippingService


def _json_dump(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, default=str)


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


class AgenteWhatsAppToolService:
    """Safe backend tool layer used by AGENTE WHATSAPP.

    Read tools expose ERP data. Mutating sales tools require explicit customer
    confirmation and delegate all business rules to the existing services.
    """

    def __init__(self, db: Session):
        self._db = db
        self._handlers: dict[str, Callable[[dict[str, Any], dict[str, Any]], Any]] = {
            "buscar_cliente_por_telefone": self._buscar_cliente_por_telefone,
            "buscar_produtos": self._buscar_produtos,
            "buscar_produto_por_nome": self._buscar_produto_por_nome,
            "buscar_promocoes": self._buscar_promocoes,
            "calcular_frete": self._calcular_frete,
            "validar_cupom": self._validar_cupom,
            "consultar_status_pedido": self._consultar_status_pedido,
            "consultar_pagamento": self._consultar_pagamento,
            "buscar_enderecos": self._buscar_enderecos,
            "buscar_ultimo_pedido": self._buscar_ultimo_pedido,
            "buscar_fidelidade": self._buscar_fidelidade,
            "validar_item_pedido": self._validar_item_pedido,
            "simular_checkout": self._simular_checkout,
            "criar_pedido": self._criar_pedido,
            "gerar_pagamento": self._gerar_pagamento,
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "buscar_cliente_por_telefone",
                "description": "Localiza o cliente/lead usando o telefone do WhatsApp.",
                "category": "clientes",
                "input_schema": {"type": "object", "required": ["phone"], "properties": {"phone": {"type": "string"}}},
                "mutates_data": False,
                "enabled": True,
            },
            {
                "name": "buscar_produtos",
                "description": "Lista produtos reais do cardapio com tamanhos, massas, bebidas e precos atuais.",
                "category": "cardapio",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "active_only": {"type": "boolean", "default": True},
                        "product_type": {"type": "string"},
                        "search": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
                    },
                },
                "mutates_data": False,
                "enabled": True,
            },
            {
                "name": "buscar_produto_por_nome",
                "description": "Busca um produto especifico por nome e retorna detalhes comerciais.",
                "category": "cardapio",
                "input_schema": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}},
                "mutates_data": False,
                "enabled": True,
            },
            {
                "name": "buscar_promocoes",
                "description": "Lista promocoes ativas cadastradas no ERP e nos produtos.",
                "category": "marketing",
                "input_schema": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}}},
                "mutates_data": False,
                "enabled": True,
            },
            {
                "name": "calcular_frete",
                "description": "Calcula frete usando as regras oficiais de entrega.",
                "category": "logistica",
                "input_schema": {
                    "type": "object",
                    "required": ["city"],
                    "properties": {
                        "city": {"type": "string"},
                        "neighborhood": {"type": "string"},
                        "zip_code": {"type": "string"},
                        "order_subtotal": {"type": "number", "default": 0},
                        "is_pickup": {"type": "boolean", "default": False},
                    },
                },
                "mutates_data": False,
                "enabled": True,
            },
            {
                "name": "validar_cupom",
                "description": "Valida cupom e calcula beneficios sem registrar uso.",
                "category": "marketing",
                "input_schema": {
                    "type": "object",
                    "required": ["code", "order_subtotal"],
                    "properties": {
                        "code": {"type": "string"},
                        "order_subtotal": {"type": "number"},
                        "delivery_fee": {"type": "number", "default": 0},
                        "customer_id": {"type": "string"},
                        "phone": {"type": "string"},
                    },
                },
                "mutates_data": False,
                "enabled": True,
            },
            {
                "name": "consultar_status_pedido",
                "description": "Consulta status operacional de um pedido real.",
                "category": "pedidos",
                "input_schema": {"type": "object", "required": ["order_id"], "properties": {"order_id": {"type": "string"}}},
                "mutates_data": False,
                "enabled": True,
            },
            {
                "name": "consultar_pagamento",
                "description": "Consulta pagamento vinculado a um pedido real.",
                "category": "financeiro",
                "input_schema": {"type": "object", "required": ["order_id"], "properties": {"order_id": {"type": "string"}}},
                "mutates_data": False,
                "enabled": True,
            },
            {
                "name": "buscar_enderecos",
                "description": "Lista enderecos salvos de um cliente.",
                "category": "clientes",
                "input_schema": {"type": "object", "required": ["customer_id"], "properties": {"customer_id": {"type": "string"}}},
                "mutates_data": False,
                "enabled": True,
            },
            {
                "name": "buscar_ultimo_pedido",
                "description": "Retorna o ultimo pedido do cliente para recompra ou atendimento.",
                "category": "pedidos",
                "input_schema": {"type": "object", "required": ["customer_id"], "properties": {"customer_id": {"type": "string"}}},
                "mutates_data": False,
                "enabled": True,
            },
            {
                "name": "buscar_fidelidade",
                "description": "Consulta pontos, nivel e beneficios de fidelidade do cliente.",
                "category": "fidelidade",
                "input_schema": {"type": "object", "required": ["customer_id"], "properties": {"customer_id": {"type": "string"}}},
                "mutates_data": False,
                "enabled": True,
            },
            {
                "name": "validar_item_pedido",
                "description": "Monta um item de carrinho valido usando produtos, tamanhos, massas e sabores reais.",
                "category": "pedidos",
                "input_schema": {
                    "type": "object",
                    "required": ["product_id"],
                    "properties": {
                        "product_id": {"type": "string"},
                        "quantity": {"type": "integer", "minimum": 1, "default": 1},
                        "selected_size_id": {"type": "string"},
                        "selected_crust_type_id": {"type": "string"},
                        "selected_drink_variant_id": {"type": "string"},
                        "flavor_product_ids": {"type": "array", "items": {"type": "string"}},
                        "notes": {"type": "string"},
                    },
                },
                "mutates_data": False,
                "requires_confirmation": False,
                "enabled": True,
            },
            {
                "name": "simular_checkout",
                "description": "Valida carrinho, frete e cupom antes de criar pedido.",
                "category": "pedidos",
                "input_schema": {"type": "object", "required": ["checkout"], "properties": {"checkout": {"type": "object"}}},
                "mutates_data": False,
                "requires_confirmation": False,
                "enabled": True,
            },
            {
                "name": "criar_pedido",
                "description": "Cria pedido real no ERP apos confirmacao explicita do cliente.",
                "category": "pedidos",
                "input_schema": {
                    "type": "object",
                    "required": ["checkout", "customer_confirmed", "confirmation_text"],
                    "properties": {
                        "checkout": {"type": "object"},
                        "phone": {"type": "string"},
                        "customer_confirmed": {"type": "boolean"},
                        "confirmation_text": {"type": "string"},
                    },
                },
                "mutates_data": True,
                "requires_confirmation": True,
                "enabled": True,
            },
            {
                "name": "gerar_pagamento",
                "description": "Gera pagamento real para pedido existente apos confirmacao explicita do cliente.",
                "category": "financeiro",
                "input_schema": {
                    "type": "object",
                    "required": ["order_id", "customer_confirmed", "confirmation_text"],
                    "properties": {
                        "order_id": {"type": "string"},
                        "payment_method": {"type": "string", "default": "pix"},
                        "payer": {"type": "object"},
                        "customer_confirmed": {"type": "boolean"},
                        "confirmation_text": {"type": "string"},
                    },
                },
                "mutates_data": True,
                "requires_confirmation": True,
                "enabled": True,
            },
        ]

    def execute_tool(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        session_id: str | None = None,
        customer_id: str | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        context: dict[str, Any] = {"session_id": None, "customer_id": None}
        log_id = str(uuid.uuid4())
        success = False
        data: Any = None
        error: str | None = None

        try:
            context = self._resolve_context(session_id=session_id, customer_id=customer_id)
            handler = self._handlers.get(tool_name)
            if not handler:
                raise ValueError("Ferramenta nao cadastrada para o AGENTE WHATSAPP.")
            data = handler(arguments or {}, context)
            success = True
        except (ValueError, ValidationError, DomainError) as exc:
            error = getattr(exc, "message", None) or str(exc)
        except Exception as exc:  # defensive audit boundary for admin tool testing
            error = f"Falha ao executar ferramenta: {exc}"

        latency_ms = int((time.perf_counter() - started) * 1000)
        self._db.add(
            AgenteWhatsAppToolCall(
                id=log_id,
                session_id=context.get("session_id"),
                customer_id=context.get("customer_id"),
                tool_name=tool_name,
                status="success" if success else "error",
                arguments_json=_json_dump(arguments or {}),
                result_json=_json_dump(data if success else {}),
                error=error,
                latency_ms=latency_ms,
            )
        )
        self._db.flush()
        return {
            "log_id": log_id,
            "tool_name": tool_name,
            "success": success,
            "data": data if success else None,
            "error": error,
            "latency_ms": latency_ms,
        }

    def _resolve_context(self, *, session_id: str | None, customer_id: str | None) -> dict[str, Any]:
        session = None
        if session_id:
            session = self._db.query(AgenteWhatsAppSession).filter(AgenteWhatsAppSession.id == session_id).first()
            if not session:
                raise ValueError("Sessao do AGENTE WHATSAPP nao encontrada.")
            customer_id = customer_id or session.customer_id
        if customer_id:
            exists = self._db.query(Customer.id).filter(Customer.id == customer_id).first()
            if not exists:
                raise ValueError("Cliente nao encontrado.")
        return {"session_id": session.id if session else None, "customer_id": customer_id}

    def _buscar_cliente_por_telefone(self, args: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
        phone = args.get("phone")
        if not phone:
            raise ValueError("Informe o telefone.")
        customer = CustomerIdentityService(self._db).find_by_phone(str(phone), channel="whatsapp")
        if not customer:
            customer = CustomerIdentityService(self._db).find_by_phone(str(phone))
        if not customer:
            return {"found": False, "phone": normalize_phone(str(phone))}
        return {"found": True, "customer": self._customer_payload(customer)}

    def _buscar_produtos(self, args: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
        limit = max(1, min(int(args.get("limit") or 20), 50))
        q = self._db.query(Product)
        if args.get("active_only", True):
            q = q.filter(Product.active == True)  # noqa: E712
        product_type = (args.get("product_type") or "").strip()
        if product_type:
            q = q.filter(Product.product_type == product_type)
        search = (args.get("search") or "").strip()
        if search:
            like = f"%{search}%"
            q = q.filter(or_(Product.name.ilike(like), Product.description.ilike(like), Product.category.ilike(like)))
        products = q.order_by(Product.name.asc()).limit(limit).all()
        return {"items": [self._product_payload(product) for product in products], "count": len(products)}

    def _buscar_produto_por_nome(self, args: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
        name = (args.get("name") or "").strip()
        if not name:
            raise ValueError("Informe o nome do produto.")
        like = f"%{name}%"
        product = (
            self._db.query(Product)
            .filter(Product.active == True, Product.name.ilike(like))  # noqa: E712
            .order_by(Product.name.asc())
            .first()
        )
        if not product:
            return {"found": False, "name": name}
        return {"found": True, "product": self._product_payload(product, include_promotions=True)}

    def _buscar_promocoes(self, args: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
        limit = max(1, min(int(args.get("limit") or 20), 50))
        now = datetime.now(timezone.utc)
        banners = (
            self._db.query(Promotion)
            .filter(
                Promotion.active == True,  # noqa: E712
                or_(Promotion.valid_from == None, Promotion.valid_from <= now),  # noqa: E711
                or_(Promotion.valid_until == None, Promotion.valid_until >= now),  # noqa: E711
            )
            .order_by(Promotion.created_at.desc())
            .limit(limit)
            .all()
        )
        product_promotions = (
            self._db.query(ProductPromotion)
            .join(Product, Product.id == ProductPromotion.product_id)
            .filter(ProductPromotion.active == True, Product.active == True)  # noqa: E712
            .order_by(ProductPromotion.created_at.desc())
            .limit(limit)
            .all()
        )
        return {
            "promotions": [
                {
                    "id": promo.id,
                    "title": promo.title,
                    "subtitle": promo.subtitle,
                    "description": promo.description,
                    "validity_text": promo.validity_text,
                }
                for promo in banners
            ],
            "product_promotions": [
                {
                    "id": promo.id,
                    "name": promo.name,
                    "product_id": promo.product_id,
                    "product_name": promo.product.name if promo.product else None,
                    "discount_type": promo.discount_type,
                    "default_value": promo.default_value,
                    "start_time": promo.start_time,
                    "end_time": promo.end_time,
                    "start_date": promo.start_date,
                    "end_date": promo.end_date,
                }
                for promo in product_promotions
            ],
        }

    def _calcular_frete(self, args: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
        payload = ShippingCalculateIn.model_validate(args)
        result = ShippingService(self._db).calculate(payload)
        return result.model_dump()

    def _validar_cupom(self, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        payload_data = dict(args)
        if context.get("customer_id") and not payload_data.get("customer_id"):
            payload_data["customer_id"] = context["customer_id"]
        payload = CouponApplyIn.model_validate(payload_data)
        return CouponService(self._db).apply(payload).model_dump()

    def _consultar_status_pedido(self, args: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
        order = self._order_by_id(args.get("order_id"))
        self._ensure_order_matches_context(order, _context)
        return self._order_payload(order, include_items=True)

    def _consultar_pagamento(self, args: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
        order_id = args.get("order_id")
        if not order_id:
            raise ValueError("Informe o ID do pedido.")
        self._ensure_order_matches_context(self._order_by_id(order_id), _context)
        return PaymentService(self._db).payment_status(str(order_id))

    def _buscar_enderecos(self, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        customer_id = args.get("customer_id") or context.get("customer_id")
        if not customer_id:
            raise ValueError("Informe o cliente.")
        rows = (
            self._db.query(Address)
            .filter(Address.customer_id == str(customer_id))
            .order_by(Address.is_default.desc(), Address.created_at.desc())
            .all()
        )
        return {
            "items": [
                {
                    "id": row.id,
                    "label": row.label,
                    "street": row.street,
                    "number": row.number,
                    "complement": row.complement,
                    "neighborhood": row.neighborhood,
                    "city": row.city,
                    "state": row.state,
                    "zip_code": row.zip_code,
                    "is_default": bool(row.is_default),
                }
                for row in rows
            ],
            "count": len(rows),
        }

    def _buscar_ultimo_pedido(self, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        customer_id = args.get("customer_id") or context.get("customer_id")
        if not customer_id:
            raise ValueError("Informe o cliente.")
        order = (
            self._db.query(Order)
            .filter(Order.customer_id == str(customer_id))
            .order_by(Order.created_at.desc())
            .first()
        )
        if not order:
            return {"found": False, "customer_id": customer_id}
        return {"found": True, "order": self._order_payload(order, include_items=True)}

    def _buscar_fidelidade(self, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        customer_id = args.get("customer_id") or context.get("customer_id")
        if not customer_id:
            raise ValueError("Informe o cliente.")
        account = get_customer_account(str(customer_id), self._db)
        benefits = get_available_benefits(str(customer_id), self._db)
        if not account:
            return {"found": False, "customer_id": customer_id, "benefits": []}
        return {
            "found": True,
            "account": {
                "id": account.id,
                "customer_id": account.customer_id,
                "total_points": account.total_points,
                "lifetime_points": account.lifetime_points,
                "rollover_points": account.rollover_points,
                "level_id": account.level_id,
                "level_name": account.level.name if account.level else None,
                "cycle_start_date": account.cycle_start_date,
                "cycle_end_date": account.cycle_end_date,
                "benefit_expiration_date": account.benefit_expiration_date,
            },
            "benefits": [
                {
                    "id": benefit.id,
                    "label": benefit.label,
                    "description": benefit.description,
                    "benefit_type": _enum_value(benefit.benefit_type),
                    "value": benefit.value,
                    "min_order_value": benefit.min_order_value,
                    "usage_limit": benefit.usage_limit,
                    "stackable": bool(benefit.stackable),
                }
                for benefit in benefits
            ],
        }

    def _validar_item_pedido(self, args: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
        product = self._active_product(args.get("product_id"))
        quantity = max(1, int(args.get("quantity") or 1))
        size = self._resolve_size(product, args.get("selected_size_id"))
        crust = self._resolve_crust(product, args.get("selected_crust_type_id"))
        drink_variant = self._resolve_drink_variant(product, args.get("selected_drink_variant_id"))
        flavor_ids = args.get("flavor_product_ids") or [product.id]
        if not isinstance(flavor_ids, list):
            raise ValueError("flavor_product_ids deve ser uma lista.")
        flavors = [self._active_product(str(flavor_id)) for flavor_id in flavor_ids]
        if not flavors:
            raise ValueError("Informe pelo menos um sabor/produto.")

        cart_item = CartItemIn(
            product_id=product.id,
            quantity=quantity,
            selected_size=size.label if size else (args.get("selected_size") or "Unico"),
            selected_size_id=size.id if size else None,
            flavor_division=len(flavors),
            flavors=[FlavorIn(product_id=row.id, name=row.name, price=row.price, icon=row.icon or "") for row in flavors],
            final_price=0,
            selected_crust_type_id=crust.id if crust else None,
            selected_crust_type_name=crust.name if crust else None,
            selected_drink_variant_id=drink_variant.id if drink_variant else None,
            selected_drink_variant_name=drink_variant.name if drink_variant else None,
            notes=args.get("notes"),
        )
        unit_price, flavor_products, pricing, size_obj, crust_obj = OrderService(self._db)._validate_item(
            cart_item,
            OrderService(self._db)._get_config(),
        )
        payload = cart_item.model_dump()
        payload["final_price"] = unit_price
        payload["selected_size_id"] = size_obj.id if size_obj else payload.get("selected_size_id")
        payload["selected_crust_type_id"] = crust_obj.id if crust_obj else payload.get("selected_crust_type_id")
        return {
            "cart_item": payload,
            "unit_price": unit_price,
            "line_total": round(unit_price * quantity, 2),
            "pricing": {
                "standard_price": pricing.standard_price,
                "final_price": pricing.final_price,
                "promotion_applied": pricing.promotion_applied,
                "promotion_id": pricing.promotion_id,
                "promotion_name": pricing.promotion_name,
                "discount_amount": pricing.discount_amount,
                "promotion_blocked": pricing.promotion_blocked,
                "promotion_block_reason": pricing.promotion_block_reason,
            },
            "flavors": [{"product_id": row.id, "name": row.name, "price": row.price} for row in flavor_products],
        }

    def _simular_checkout(self, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        checkout = self._checkout_from_args(args, context)
        quote = OrderService(self._db).quote_checkout(checkout)
        return {"checkout": checkout.model_dump(), "quote": quote}

    def _criar_pedido(self, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        self._require_customer_confirmation(args, "criar pedido")
        checkout = self._checkout_from_args(args, context)
        order = OrderService(self._db).create_from_checkout(checkout)
        self._record_event(
            context,
            event_type="agente_whatsapp_order_created",
            order_id=order.id,
            payload={"order_id": order.id, "total": order.total, "confirmation_text": args.get("confirmation_text")},
        )
        return {"order": self._order_payload(order, include_items=True)}

    def _gerar_pagamento(self, args: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        self._require_customer_confirmation(args, "gerar pagamento")
        order = self._order_by_id(args.get("order_id"))
        self._ensure_order_matches_context(order, context)
        payment_method = args.get("payment_method") or (_enum_value(order.payment.method) if order.payment else "pix")
        payload = PaymentCreate(
            order_id=order.id,
            amount=order.total,
            payment_method=payment_method,
            payer=args.get("payer") if isinstance(args.get("payer"), dict) else None,
            formData={
                "payment_method_id": payment_method,
                "payer": args.get("payer") if isinstance(args.get("payer"), dict) else {},
            },
        )
        payment = PaymentService(self._db).create(payload)
        self._record_event(
            context,
            event_type="agente_whatsapp_payment_created",
            order_id=order.id,
            payload={
                "order_id": order.id,
                "payment_id": payment.id,
                "payment_method": _enum_value(payment.method),
                "confirmation_text": args.get("confirmation_text"),
            },
        )
        return {"payment": payment.model_dump(), "payment_status": PaymentService(self._db).payment_status(order.id)}

    def _checkout_from_args(self, args: dict[str, Any], context: dict[str, Any]) -> CheckoutIn:
        payload = dict(args.get("checkout") or args)
        customer_id = payload.get("customer_id") or context.get("customer_id")
        delivery = dict(payload.get("delivery") or {})
        phone = payload.get("phone") or args.get("phone") or delivery.get("phone")
        if not customer_id and phone:
            customer, _created = CustomerIdentityService(self._db).get_or_create_whatsapp_lead(
                phone=str(phone),
                name=delivery.get("name"),
                source="agente_whatsapp",
            )
            customer_id = customer.id
        if customer_id:
            payload["customer_id"] = customer_id
            context["customer_id"] = customer_id
        if context.get("session_id") and not payload.get("session_id"):
            payload["session_id"] = context["session_id"]
        if phone and not delivery.get("phone"):
            delivery["phone"] = str(phone)
        if delivery:
            payload["delivery"] = delivery
        return CheckoutIn.model_validate(payload)

    def _require_customer_confirmation(self, args: dict[str, Any], action: str) -> None:
        if args.get("customer_confirmed") is not True:
            raise ValueError(f"Confirmacao explicita do cliente obrigatoria para {action}.")
        if not str(args.get("confirmation_text") or "").strip():
            raise ValueError("Informe o texto/mensagem de confirmacao do cliente.")

    def _record_event(
        self,
        context: dict[str, Any],
        *,
        event_type: str,
        order_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._db.add(
            AgenteWhatsAppEvent(
                id=str(uuid.uuid4()),
                session_id=context.get("session_id"),
                customer_id=context.get("customer_id"),
                order_id=order_id,
                event_type=event_type,
                source="agente_whatsapp_tool",
                payload_json=_json_dump(payload or {}),
            )
        )
        self._db.flush()

    def _active_product(self, product_id: Any) -> Product:
        if not product_id:
            raise ValueError("Informe o produto.")
        product = self._db.query(Product).filter(Product.id == str(product_id), Product.active == True).first()  # noqa: E712
        if not product:
            raise ValueError("Produto nao encontrado ou inativo.")
        return product

    def _resolve_size(self, product: Product, size_id: Any) -> ProductSize | None:
        if size_id:
            size = (
                self._db.query(ProductSize)
                .filter(ProductSize.id == str(size_id), ProductSize.product_id == product.id, ProductSize.active == True)  # noqa: E712
                .first()
            )
            if not size:
                raise ValueError("Tamanho nao encontrado para o produto.")
            return size
        return next((size for size in product.sizes if size.active and size.is_default), None) or next(
            (size for size in product.sizes if size.active),
            None,
        )

    def _resolve_crust(self, product: Product, crust_id: Any) -> ProductCrustType | None:
        if not crust_id:
            return None
        crust = (
            self._db.query(ProductCrustType)
            .filter(ProductCrustType.id == str(crust_id), ProductCrustType.product_id == product.id, ProductCrustType.active == True)  # noqa: E712
            .first()
        )
        if not crust:
            raise ValueError("Massa/borda nao encontrada para o produto.")
        return crust

    def _resolve_drink_variant(self, product: Product, variant_id: Any) -> ProductDrinkVariant | None:
        if not variant_id:
            return None
        variant = (
            self._db.query(ProductDrinkVariant)
            .filter(ProductDrinkVariant.id == str(variant_id), ProductDrinkVariant.product_id == product.id, ProductDrinkVariant.active == True)  # noqa: E712
            .first()
        )
        if not variant:
            raise ValueError("Variacao de bebida nao encontrada para o produto.")
        return variant

    def _order_by_id(self, order_id: Any) -> Order:
        if not order_id:
            raise ValueError("Informe o ID do pedido.")
        order_ref = str(order_id).strip()
        order = self._db.query(Order).filter(or_(Order.id == order_ref, Order.order_code == order_ref)).first()
        if not order:
            raise ValueError("Pedido nao encontrado.")
        return order

    @staticmethod
    def _ensure_order_matches_context(order: Order, context: dict[str, Any]) -> None:
        customer_id = context.get("customer_id")
        if customer_id and order.customer_id and order.customer_id != customer_id:
            raise ValueError("Pedido nao pertence ao cliente da conversa.")

    def _customer_payload(self, customer: Customer) -> dict[str, Any]:
        return {
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "email": None if is_system_lead_email(customer.email) else customer.email,
            "profile_level": "complete" if customer.password_hash and not is_system_lead_email(customer.email) else "lead",
            "crm_status": customer.crm_status,
            "source": customer.source,
            "total_orders": customer.total_orders or 0,
            "total_spent": customer.total_spent or 0,
            "avg_ticket": customer.avg_ticket or 0,
            "last_order_at": customer.last_order_at,
            "created_at": customer.created_at,
        }

    def _product_payload(self, product: Product, *, include_promotions: bool = False) -> dict[str, Any]:
        default_size = next((size for size in product.sizes if size.active and size.is_default), None)
        if not default_size:
            default_size = next((size for size in product.sizes if size.active), None)
        quote = ProductPricingService(self._db).calculate(product=product, size=default_size)
        payload = {
            "id": product.id,
            "name": product.name,
            "description": product.description,
            "price": product.price,
            "current_price": quote.final_price,
            "standard_price": quote.standard_price,
            "promotion_applied": quote.promotion_applied,
            "promotion_name": quote.promotion_name,
            "category": product.category,
            "subcategory": product.subcategory,
            "product_type": product.product_type,
            "active": bool(product.active),
            "sizes": [self._size_payload(size) for size in product.sizes if size.active],
            "crust_types": [self._crust_payload(crust) for crust in product.crust_types if crust.active],
            "drink_variants": [self._drink_payload(variant) for variant in product.drink_variants if variant.active],
        }
        if include_promotions:
            payload["promotions"] = [
                {
                    "id": promo.id,
                    "name": promo.name,
                    "discount_type": promo.discount_type,
                    "default_value": promo.default_value,
                    "start_time": promo.start_time,
                    "end_time": promo.end_time,
                    "active": bool(promo.active),
                }
                for promo in product.promotions
                if promo.active
            ]
        return payload

    def _order_payload(self, order: Order, *, include_items: bool = False) -> dict[str, Any]:
        payload = {
            "id": order.id,
            "order_code": order.order_code,
            "customer_id": order.customer_id,
            "status": _enum_value(order.status),
            "payment_status": _enum_value(order.payment.status) if order.payment else "pending",
            "subtotal": order.subtotal,
            "shipping_fee": order.shipping_fee,
            "discount": order.discount,
            "total": order.total,
            "estimated_time": order.estimated_time,
            "delivery_name": order.delivery_name,
            "delivery_phone": order.delivery_phone,
            "delivery_city": order.delivery_city,
            "delivery_street": order.delivery_street,
            "created_at": order.created_at,
            "paid_at": order.paid_at,
            "preparation_started_at": order.preparation_started_at,
            "out_for_delivery_at": order.out_for_delivery_at,
            "delivered_at": order.delivered_at,
            "cancelled_at": order.cancelled_at,
        }
        if include_items:
            payload["items"] = [
                {
                    "id": item.id,
                    "product_id": item.product_id,
                    "product_name": self._product_name(item.product_id),
                    "quantity": item.quantity,
                    "selected_size": item.selected_size,
                    "selected_crust_type": item.selected_crust_type,
                    "selected_drink_variant": item.selected_drink_variant,
                    "unit_price": item.unit_price,
                    "total_price": item.total_price,
                    "promotion_name": item.promotion_name,
                    "is_gift": bool(item.is_gift),
                    "flavors": [
                        {
                            "product_id": flavor.product_id,
                            "name": flavor.flavor_name,
                            "price": flavor.flavor_price,
                        }
                        for flavor in item.flavors
                    ],
                }
                for item in order.items
            ]
        return payload

    def _product_name(self, product_id: str | None) -> str | None:
        if not product_id:
            return None
        row = self._db.query(Product.name).filter(Product.id == product_id).first()
        return row[0] if row else None

    @staticmethod
    def _size_payload(size: ProductSize) -> dict[str, Any]:
        return {
            "id": size.id,
            "label": size.label,
            "description": size.description,
            "price": size.price,
            "is_default": bool(size.is_default),
            "sort_order": size.sort_order,
        }

    @staticmethod
    def _crust_payload(crust: ProductCrustType) -> dict[str, Any]:
        return {
            "id": crust.id,
            "name": crust.name,
            "price_addition": crust.price_addition,
            "sort_order": crust.sort_order,
        }

    @staticmethod
    def _drink_payload(variant: ProductDrinkVariant) -> dict[str, Any]:
        return {
            "id": variant.id,
            "name": variant.name,
            "price_addition": variant.price_addition,
            "sort_order": variant.sort_order,
        }

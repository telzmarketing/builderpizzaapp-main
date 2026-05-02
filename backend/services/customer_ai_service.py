from __future__ import annotations

import json
import re
import unicodedata
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.models.crm import (
    CustomerAIProfile,
    CustomerAISuggestion,
    CustomerTag,
    CustomerTagAssignment,
)
from backend.models.customer import Customer
from backend.models.customer_event import CustomerEvent
from backend.models.order import Order, OrderItem, OrderItemFlavor
from backend.models.product import Product


PAID_STATUSES = {
    "paid",
    "pago",
    "preparing",
    "ready_for_pickup",
    "on_the_way",
    "delivered",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or "item"


def _status(order: Order) -> str:
    return order.status.value if hasattr(order.status, "value") else str(order.status)


def _safe_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _load_json(value: str | None, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return fallback


def _timeline(db: Session, customer_id: str, event_type: str, title: str, description: str | None = None, metadata: dict | None = None) -> None:
    db.execute(
        text(
            """
            INSERT INTO customer_timeline (id, customer_id, event_type, title, description, metadata_json, created_at)
            VALUES (:id, :customer_id, :event_type, :title, :description, :metadata_json, :created_at)
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "customer_id": customer_id,
            "event_type": event_type,
            "title": title,
            "description": description,
            "metadata_json": _safe_json(metadata or {}),
            "created_at": _now(),
        },
    )


def _top(counter: Counter, limit: int = 5) -> list[dict[str, Any]]:
    return [{"name": name, "count": count} for name, count in counter.most_common(limit) if name]


def _confidence(high: bool = False, low: bool = False) -> str:
    if high:
        return "high"
    if low:
        return "low"
    return "medium"


def _profile_to_dict(profile: CustomerAIProfile) -> dict[str, Any]:
    return {
        "id": profile.id,
        "customer_id": profile.customer_id,
        "profile_summary": profile.profile_summary,
        "segment": profile.segment,
        "preferences": _load_json(profile.preferences_json, {}),
        "behavior": _load_json(profile.behavior_json, {}),
        "churn_risk": profile.churn_risk,
        "repurchase_probability": profile.repurchase_probability,
        "average_ticket": profile.average_ticket,
        "best_contact_day": profile.best_contact_day,
        "best_contact_hour": profile.best_contact_hour,
        "next_best_action": profile.next_best_action,
        "recommended_offer": profile.recommended_offer,
        "recommended_message": profile.recommended_message,
        "analysis_source": profile.analysis_source,
        "model_version": profile.model_version,
        "generated_at": profile.generated_at,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def _suggestion_to_dict(suggestion: CustomerAISuggestion) -> dict[str, Any]:
    return {
        "id": suggestion.id,
        "customer_id": suggestion.customer_id,
        "suggestion_type": suggestion.suggestion_type,
        "name": suggestion.name,
        "slug": suggestion.slug,
        "reason": suggestion.reason,
        "confidence": suggestion.confidence,
        "status": suggestion.status,
        "target_id": suggestion.target_id,
        "source": suggestion.source,
        "created_at": suggestion.created_at,
        "updated_at": suggestion.updated_at,
        "resolved_at": suggestion.resolved_at,
    }


def get_customer_ai_profile(db: Session, customer_id: str) -> dict[str, Any] | None:
    profile = db.query(CustomerAIProfile).filter(CustomerAIProfile.customer_id == customer_id).first()
    return _profile_to_dict(profile) if profile else None


def list_customer_ai_suggestions(db: Session, customer_id: str, status: str = "pending") -> list[dict[str, Any]]:
    query = db.query(CustomerAISuggestion).filter(CustomerAISuggestion.customer_id == customer_id)
    if status != "all":
        query = query.filter(CustomerAISuggestion.status == status)
    suggestions = query.order_by(CustomerAISuggestion.created_at.desc()).all()
    return [_suggestion_to_dict(suggestion) for suggestion in suggestions]


def analyze_customer_profile(db: Session, customer_id: str) -> dict[str, Any]:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise ValueError("Cliente nao encontrado.")

    orders = (
        db.query(Order)
        .filter(Order.customer_id == customer_id)
        .order_by(Order.created_at.asc())
        .all()
    )
    paid_orders = [order for order in orders if _status(order) in PAID_STATUSES]
    events = db.query(CustomerEvent).filter(CustomerEvent.customer_id == customer_id).all()

    total_orders = len(paid_orders)
    total_spent = sum(float(order.total or 0) for order in paid_orders)
    average_ticket = total_spent / total_orders if total_orders else 0.0
    last_order = paid_orders[-1] if paid_orders else None

    product_counter: Counter = Counter()
    category_counter: Counter = Counter()
    flavor_counter: Counter = Counter()
    size_counter: Counter = Counter()
    crust_counter: Counter = Counter()
    drink_counter: Counter = Counter()

    item_rows = (
        db.query(OrderItem, Product)
        .join(Order, OrderItem.order_id == Order.id)
        .outerjoin(Product, OrderItem.product_id == Product.id)
        .filter(Order.customer_id == customer_id)
        .all()
    )
    item_ids: list[str] = []
    for item, product in item_rows:
        item_ids.append(item.id)
        if product:
            product_counter[product.name] += item.quantity or 1
            if product.category:
                category_counter[product.category] += item.quantity or 1
        if item.selected_size:
            size_counter[item.selected_size] += item.quantity or 1
        if item.selected_crust_type:
            crust_counter[item.selected_crust_type] += item.quantity or 1
        if item.selected_drink_variant:
            drink_counter[item.selected_drink_variant] += item.quantity or 1

    if item_ids:
        flavors = db.query(OrderItemFlavor).filter(OrderItemFlavor.order_item_id.in_(item_ids)).all()
        for flavor in flavors:
            flavor_counter[flavor.flavor_name] += 1

    weekday_counter: Counter = Counter()
    hour_counter: Counter = Counter()
    weekday_names = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]
    for order in paid_orders:
        if order.created_at:
            weekday_counter[weekday_names[order.created_at.weekday()]] += 1
            hour_counter[f"{order.created_at.hour:02d}:00"] += 1

    event_types = Counter(event.event_type for event in events)
    cart_abandonments = event_types.get("cart_abandoned", 0)
    checkout_abandonments = event_types.get("checkout_abandoned", 0)
    visits_without_purchase = max(event_types.get("site_opened", 0) - total_orders, 0)
    chatbot_interactions = sum(count for event_type, count in event_types.items() if event_type.startswith("chatbot_"))
    coupon_events = sum(count for event_type, count in event_types.items() if event_type.startswith("coupon_"))
    campaign_events = sum(count for event_type, count in event_types.items() if event_type.startswith("campaign_"))

    days_since_last_order = None
    if last_order and last_order.created_at:
        days_since_last_order = max((_now() - last_order.created_at).days, 0)

    if total_orders == 0:
        segment = "lead"
        churn_risk = "medium" if cart_abandonments or visits_without_purchase else "low"
        repurchase_probability = 0.15
    elif days_since_last_order is not None and days_since_last_order > 60:
        segment = "inativo"
        churn_risk = "high"
        repurchase_probability = 0.25
    elif days_since_last_order is not None and days_since_last_order > 30:
        segment = "em_risco"
        churn_risk = "medium"
        repurchase_probability = 0.4
    elif total_orders >= 5 or total_spent >= 500:
        segment = "vip"
        churn_risk = "low"
        repurchase_probability = 0.85
    elif total_orders >= 3:
        segment = "recorrente"
        churn_risk = "low"
        repurchase_probability = 0.72
    else:
        segment = "novo_comprador"
        churn_risk = "low"
        repurchase_probability = 0.5

    if average_ticket >= 120 and segment not in {"vip", "inativo", "em_risco"}:
        segment = "alto_ticket"

    best_day = weekday_counter.most_common(1)[0][0] if weekday_counter else "sexta"
    best_hour = hour_counter.most_common(1)[0][0] if hour_counter else "18:00"
    favorite_product = product_counter.most_common(1)[0][0] if product_counter else None
    favorite_flavor = flavor_counter.most_common(1)[0][0] if flavor_counter else None

    if segment == "lead":
        next_action = "Enviar incentivo de primeira compra pelo canal autorizado."
        offer = "Cupom de boas-vindas ou frete reduzido para primeira compra."
    elif segment in {"inativo", "em_risco"}:
        next_action = "Executar acao de recuperacao com oferta objetiva e prazo curto."
        offer = "Oferta de retorno baseada no sabor ou produto favorito."
    elif segment in {"vip", "alto_ticket"}:
        next_action = "Oferecer experiencia premium e lancamentos antes da base geral."
        offer = "Combo premium ou item exclusivo com beneficio de fidelidade."
    else:
        next_action = "Estimular recompra no melhor dia e horario identificados."
        offer = "Recomendacao personalizada baseada nos itens mais comprados."

    recommendation_focus = favorite_flavor or favorite_product or "uma pizza favorita da casa"
    recommended_message = (
        f"Ola {customer.name}, separamos uma sugestao especial para voce: "
        f"{recommendation_focus}. Posso te mostrar as opcoes para hoje?"
    )
    summary = (
        f"{customer.name} esta classificado como {segment.replace('_', ' ')}. "
        f"Tem {total_orders} pedido(s) pago(s), ticket medio de R$ {average_ticket:.2f} "
        f"e melhor contato em {best_day} por volta de {best_hour}."
    )

    preferences = {
        "favorite_products": _top(product_counter),
        "favorite_categories": _top(category_counter),
        "favorite_flavors": _top(flavor_counter),
        "favorite_sizes": _top(size_counter),
        "favorite_crusts": _top(crust_counter),
        "favorite_drinks": _top(drink_counter),
        "best_purchase_days": _top(weekday_counter),
        "best_purchase_hours": _top(hour_counter),
    }
    behavior = {
        "total_orders": total_orders,
        "total_spent": round(total_spent, 2),
        "average_ticket": round(average_ticket, 2),
        "last_order_at": last_order.created_at.isoformat() if last_order and last_order.created_at else None,
        "days_since_last_order": days_since_last_order,
        "cart_abandonments": cart_abandonments,
        "checkout_abandonments": checkout_abandonments,
        "visits_without_purchase": visits_without_purchase,
        "coupon_events": coupon_events,
        "campaign_events": campaign_events,
        "chatbot_interactions": chatbot_interactions,
    }

    profile = db.query(CustomerAIProfile).filter(CustomerAIProfile.customer_id == customer_id).first()
    if not profile:
        profile = CustomerAIProfile(id=str(uuid.uuid4()), customer_id=customer_id)
        db.add(profile)
    profile.profile_summary = summary
    profile.segment = segment
    profile.preferences_json = _safe_json(preferences)
    profile.behavior_json = _safe_json(behavior)
    profile.churn_risk = churn_risk
    profile.repurchase_probability = repurchase_probability
    profile.average_ticket = round(average_ticket, 2)
    profile.best_contact_day = best_day
    profile.best_contact_hour = best_hour
    profile.next_best_action = next_action
    profile.recommended_offer = offer
    profile.recommended_message = recommended_message
    profile.analysis_source = "rules"
    profile.model_version = "rules_v1"
    profile.generated_at = _now()
    profile.updated_at = _now()

    suggestions = _build_suggestions(
        segment=segment,
        total_orders=total_orders,
        total_spent=total_spent,
        average_ticket=average_ticket,
        churn_risk=churn_risk,
        cart_abandonments=cart_abandonments,
        coupon_events=coupon_events,
        favorite_category=category_counter.most_common(1)[0][0] if category_counter else None,
    )
    _replace_pending_suggestions(db, customer_id, suggestions)
    _timeline(
        db,
        customer_id,
        "ai_profile_analyzed",
        "Perfil inteligente analisado",
        summary,
        {"segment": segment, "churn_risk": churn_risk, "repurchase_probability": repurchase_probability},
    )
    db.commit()
    db.refresh(profile)
    return {
        "profile": _profile_to_dict(profile),
        "suggestions": list_customer_ai_suggestions(db, customer_id),
    }


def _build_suggestions(
    *,
    segment: str,
    total_orders: int,
    total_spent: float,
    average_ticket: float,
    churn_risk: str,
    cart_abandonments: int,
    coupon_events: int,
    favorite_category: str | None,
) -> list[dict[str, str]]:
    suggestions: list[dict[str, str]] = []

    def add(kind: str, name: str, reason: str, confidence: str = "medium") -> None:
        suggestions.append({
            "suggestion_type": kind,
            "name": name,
            "slug": _slugify(name),
            "reason": reason,
            "confidence": confidence,
        })

    if segment == "vip":
        add("tag", "VIP", "Cliente com alto valor acumulado ou alta recorrencia.", _confidence(high=True))
        add("group", "Clientes VIP", "Base prioritaria para ofertas premium.", _confidence(high=True))
    if segment == "recorrente":
        add("tag", "Recorrente", "Cliente com historico consistente de compras.", _confidence(high=True))
        add("group", "Clientes recorrentes", "Bom publico para campanhas de recompra.", _confidence(high=True))
    if segment in {"inativo", "em_risco"} or churn_risk in {"medium", "high"}:
        add("tag", "Em risco", "Cliente esta ha muitos dias sem comprar.", _confidence(high=churn_risk == "high"))
        add("group", "Recuperacao de clientes", "Deve receber acao de reativacao.", _confidence(high=churn_risk == "high"))
    if average_ticket >= 120 or total_spent >= 500:
        add("tag", "Alto ticket", "Ticket medio ou gasto acumulado acima da media esperada.", _confidence(high=average_ticket >= 120))
    if cart_abandonments > 0 and total_orders <= 1:
        add("tag", "Carrinho abandonado", "Possui carrinho abandonado com baixa conversao.", "medium")
        add("group", "Recuperar carrinho", "Pode responder bem a lembrete com oferta simples.", "medium")
    if coupon_events > 0:
        add("tag", "Sensivel a desconto", "Interagiu com cupons ou campanhas promocionais.", "medium")
    if favorite_category:
        add("tag", f"Prefere {favorite_category}", f"Categoria mais recorrente nos pedidos: {favorite_category}.", "medium")
    return suggestions


def _replace_pending_suggestions(db: Session, customer_id: str, suggestions: list[dict[str, str]]) -> None:
    db.query(CustomerAISuggestion).filter(
        CustomerAISuggestion.customer_id == customer_id,
        CustomerAISuggestion.status == "pending",
    ).delete(synchronize_session=False)

    existing = {
        (suggestion.suggestion_type, suggestion.slug)
        for suggestion in db.query(CustomerAISuggestion)
        .filter(
            CustomerAISuggestion.customer_id == customer_id,
            CustomerAISuggestion.status.in_(["accepted", "rejected"]),
        )
        .all()
    }
    for data in suggestions:
        key = (data["suggestion_type"], data["slug"])
        if key in existing:
            continue
        db.add(
            CustomerAISuggestion(
                id=str(uuid.uuid4()),
                customer_id=customer_id,
                suggestion_type=data["suggestion_type"],
                name=data["name"],
                slug=data["slug"],
                reason=data["reason"],
                confidence=data["confidence"],
                status="pending",
                source="rules",
            )
        )


def accept_customer_ai_suggestion(db: Session, suggestion_id: str, admin_name: str | None = None) -> dict[str, Any]:
    suggestion = db.query(CustomerAISuggestion).filter(CustomerAISuggestion.id == suggestion_id).first()
    if not suggestion:
        raise ValueError("Sugestao nao encontrada.")
    if suggestion.status != "pending":
        return _suggestion_to_dict(suggestion)

    if suggestion.suggestion_type == "tag":
        target_id = _accept_tag_suggestion(db, suggestion, admin_name)
    elif suggestion.suggestion_type == "group":
        target_id = _accept_group_suggestion(db, suggestion, admin_name)
    else:
        raise ValueError("Tipo de sugestao invalido.")

    suggestion.status = "accepted"
    suggestion.target_id = target_id
    suggestion.resolved_at = _now()
    suggestion.updated_at = _now()
    _timeline(
        db,
        suggestion.customer_id,
        "ai_suggestion_accepted",
        "Sugestao da IA aceita",
        f"{suggestion.suggestion_type}: {suggestion.name}",
        {"suggestion_id": suggestion.id, "target_id": target_id},
    )
    db.commit()
    db.refresh(suggestion)
    return _suggestion_to_dict(suggestion)


def reject_customer_ai_suggestion(db: Session, suggestion_id: str) -> dict[str, Any]:
    suggestion = db.query(CustomerAISuggestion).filter(CustomerAISuggestion.id == suggestion_id).first()
    if not suggestion:
        raise ValueError("Sugestao nao encontrada.")
    suggestion.status = "rejected"
    suggestion.resolved_at = _now()
    suggestion.updated_at = _now()
    _timeline(
        db,
        suggestion.customer_id,
        "ai_suggestion_rejected",
        "Sugestao da IA rejeitada",
        f"{suggestion.suggestion_type}: {suggestion.name}",
        {"suggestion_id": suggestion.id},
    )
    db.commit()
    db.refresh(suggestion)
    return _suggestion_to_dict(suggestion)


def _accept_tag_suggestion(db: Session, suggestion: CustomerAISuggestion, admin_name: str | None) -> str:
    tag = db.query(CustomerTag).filter(CustomerTag.tenant_id == "default", CustomerTag.slug == suggestion.slug).first()
    if not tag:
        tag = CustomerTag(
            id=str(uuid.uuid4()),
            tenant_id="default",
            name=suggestion.name,
            slug=suggestion.slug,
            description=suggestion.reason,
            color="#f97316",
            status="active",
            source="ai",
            created_by=admin_name,
        )
        db.add(tag)
        db.flush()

    existing = db.query(CustomerTagAssignment).filter(
        CustomerTagAssignment.customer_id == suggestion.customer_id,
        CustomerTagAssignment.tag_id == tag.id,
    ).first()
    if not existing:
        db.add(
            CustomerTagAssignment(
                id=str(uuid.uuid4()),
                tenant_id="default",
                customer_id=suggestion.customer_id,
                tag_id=tag.id,
                source="ai",
                created_by=admin_name,
            )
        )
        _timeline(
            db,
            suggestion.customer_id,
            "tag_added",
            "Tag adicionada ao cliente",
            tag.name,
            {"tag_id": tag.id, "source": "ai"},
        )
    return tag.id


def _accept_group_suggestion(db: Session, suggestion: CustomerAISuggestion, admin_name: str | None) -> str:
    row = db.execute(
        text(
            """
            SELECT id FROM customer_groups
            WHERE COALESCE(tenant_id, 'default') = 'default'
              AND (slug = :slug OR LOWER(name) = LOWER(:name))
            LIMIT 1
            """
        ),
        {"slug": suggestion.slug, "name": suggestion.name},
    ).fetchone()
    if row:
        group_id = row[0]
    else:
        group_id = str(uuid.uuid4())
        db.execute(
            text(
                """
                INSERT INTO customer_groups (
                    id, tenant_id, name, slug, description, group_type, color, active, source, created_by, created_at, updated_at
                ) VALUES (
                    :id, 'default', :name, :slug, :description, 'manual', '#f97316', TRUE, 'ai', :created_by, :now, :now
                )
                """
            ),
            {
                "id": group_id,
                "name": suggestion.name,
                "slug": suggestion.slug,
                "description": suggestion.reason,
                "created_by": admin_name,
                "now": _now(),
            },
        )

    db.execute(
        text(
            """
            INSERT INTO customer_group_members (id, tenant_id, group_id, customer_id, source, created_by)
            VALUES (:id, 'default', :group_id, :customer_id, 'ai', :created_by)
            ON CONFLICT DO NOTHING
            """
        ),
        {
            "id": str(uuid.uuid4()),
            "group_id": group_id,
            "customer_id": suggestion.customer_id,
            "created_by": admin_name,
        },
    )
    _timeline(
        db,
        suggestion.customer_id,
        "group_added",
        "Cliente adicionado ao grupo",
        suggestion.name,
        {"group_id": group_id, "source": "ai"},
    )
    return group_id

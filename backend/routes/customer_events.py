"""
Customer Events — registro comportamental de clientes e visitantes.
Endpoints públicos para receber eventos da loja.
"""
from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.admin import AdminUser
from backend.models.customer_event import CustomerEvent
from backend.schemas.customer_event import CustomerEventCreate, IdentifySessionRequest
from backend.core.response import ok, created
from backend.routes.admin_auth import get_current_admin
from backend.routes.customer_access import require_customer_id_or_admin

router = APIRouter(prefix="/customer-events", tags=["customer-events"])

EVENT_FRIENDLY_NAMES: dict[str, str] = {
    "site_opened": "Acessou o site",
    "page_viewed": "Visualizou página",
    "product_viewed": "Visualizou produto",
    "category_viewed": "Visualizou categoria",
    "campaign_viewed": "Visualizou campanha",
    "popup_viewed": "Viu popup",
    "popup_closed": "Fechou popup",
    "popup_clicked": "Clicou no popup",
    "banner_clicked": "Clicou no banner",
    "cart_item_added": "Adicionou item ao carrinho",
    "cart_item_removed": "Removeu item do carrinho",
    "cart_viewed": "Visualizou carrinho",
    "cart_abandoned": "Abandonou carrinho",
    "cart_recovered": "Recuperou carrinho",
    "checkout_started": "Iniciou checkout",
    "checkout_completed": "Completou checkout",
    "checkout_abandoned": "Abandonou checkout",
    "payment_method_selected": "Selecionou forma de pagamento",
    "order_created": "Pedido criado",
    "order_paid": "Pedido pago",
    "order_cancelled": "Pedido cancelado",
    "order_delivered": "Pedido entregue",
    "coupon_applied": "Aplicou cupom",
    "coupon_rejected": "Cupom rejeitado",
    "customer_logged_in": "Cliente fez login",
    "customer_created": "Cadastro realizado",
    "customer_returned": "Cliente retornou",
    "chatbot_opened": "Abriu chatbot",
    "chatbot_message_sent": "Enviou mensagem no chat",
    "chatbot_closed": "Fechou chatbot",
}


@router.post("", status_code=201)
def register_event(
    body: CustomerEventCreate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_customer_phone: str | None = Header(default=None),
    x_customer_email: str | None = Header(default=None),
):
    if body.customer_id:
        require_customer_id_or_admin(
            body.customer_id,
            db,
            authorization,
            x_customer_phone,
            x_customer_email,
        )
    event = CustomerEvent(
        id=str(uuid.uuid4()),
        customer_id=body.customer_id,
        session_id=body.session_id,
        event_type=body.event_type,
        event_name=body.event_name or EVENT_FRIENDLY_NAMES.get(body.event_type, body.event_type),
        event_description=body.event_description,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        product_id=body.product_id,
        order_id=body.order_id,
        campaign_id=body.campaign_id,
        coupon_id=body.coupon_id,
        metadata_json=body.metadata_json,
        source=body.source,
        utm_source=body.utm_source,
        utm_medium=body.utm_medium,
        utm_campaign=body.utm_campaign,
        device_type=body.device_type,
        browser=body.browser,
        operating_system=body.operating_system,
        ip_address=body.ip_address,
        page_url=body.page_url,
        referrer_url=body.referrer_url,
    )
    db.add(event)
    db.commit()
    return created({"id": event.id}, "Evento registrado.")


@router.get("/by-session/{session_id}")
def events_by_session(
    session_id: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    events = (
        db.query(CustomerEvent)
        .filter(CustomerEvent.session_id == session_id)
        .order_by(CustomerEvent.created_at.desc())
        .limit(100)
        .all()
    )
    return ok([_serialize(e) for e in events])


@router.post("/identify")
def identify_session(
    body: IdentifySessionRequest,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_customer_phone: str | None = Header(default=None),
    x_customer_email: str | None = Header(default=None),
):
    """Vincula todos os eventos anônimos de uma session_id ao customer_id."""
    require_customer_id_or_admin(
        body.customer_id,
        db,
        authorization,
        x_customer_phone,
        x_customer_email,
    )
    updated = (
        db.query(CustomerEvent)
        .filter(
            CustomerEvent.session_id == body.session_id,
            CustomerEvent.customer_id.is_(None),
        )
        .update({"customer_id": body.customer_id})
    )
    db.commit()
    return ok({"updated_events": updated})


def _serialize(e: CustomerEvent) -> dict:
    return {
        "id": e.id,
        "customer_id": e.customer_id,
        "session_id": e.session_id,
        "event_type": e.event_type,
        "event_name": e.event_name,
        "event_description": e.event_description,
        "entity_type": e.entity_type,
        "entity_id": e.entity_id,
        "product_id": e.product_id,
        "order_id": e.order_id,
        "campaign_id": e.campaign_id,
        "coupon_id": e.coupon_id,
        "metadata_json": e.metadata_json,
        "source": e.source,
        "utm_source": e.utm_source,
        "utm_medium": e.utm_medium,
        "utm_campaign": e.utm_campaign,
        "device_type": e.device_type,
        "browser": e.browser,
        "page_url": e.page_url,
        "referrer_url": e.referrer_url,
        "created_at": e.created_at,
    }

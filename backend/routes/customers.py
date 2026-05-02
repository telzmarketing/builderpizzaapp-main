import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.routes.customer_access import require_customer_or_admin
from backend.models.admin import AdminUser
from backend.models.customer import Customer, Address
from backend.models.order import Order
from backend.models.customer_event import CustomerEvent
from backend.schemas.customer import (
    CustomerCreate, CustomerUpdate, CustomerOut,
    AddressCreate, AddressOut,
)
from backend.core.response import ok

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=list[CustomerOut])
def list_customers(
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    return db.query(Customer).order_by(Customer.name).all()


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Cliente não encontrado.")
    return customer


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(body: CustomerCreate, db: Session = Depends(get_db)):
    existing = db.query(Customer).filter(Customer.email == body.email).first()
    if existing:
        raise HTTPException(400, "E-mail já cadastrado.")
    customer = Customer(id=str(uuid.uuid4()), **body.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: str,
    body: CustomerUpdate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_customer_phone: str | None = Header(default=None),
    x_customer_email: str | None = Header(default=None),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Cliente não encontrado.")
    require_customer_or_admin(customer, db, authorization, x_customer_phone, x_customer_email)
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(customer, key, value)
    db.commit()
    db.refresh(customer)
    return customer


# ── Addresses ─────────────────────────────────────────────────────────────────

@router.get("/{customer_id}/addresses", response_model=list[AddressOut])
def list_addresses(
    customer_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_customer_phone: str | None = Header(default=None),
    x_customer_email: str | None = Header(default=None),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Cliente não encontrado.")
    require_customer_or_admin(customer, db, authorization, x_customer_phone, x_customer_email)
    return db.query(Address).filter(Address.customer_id == customer_id).all()


@router.post("/{customer_id}/addresses", response_model=AddressOut, status_code=201)
def add_address(
    customer_id: str,
    body: AddressCreate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_customer_phone: str | None = Header(default=None),
    x_customer_email: str | None = Header(default=None),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Cliente não encontrado.")
    require_customer_or_admin(customer, db, authorization, x_customer_phone, x_customer_email)
    if body.is_default:
        db.query(Address).filter(Address.customer_id == customer_id).update({"is_default": False})
    address = Address(id=str(uuid.uuid4()), customer_id=customer_id, **body.model_dump())
    db.add(address)
    db.commit()
    db.refresh(address)
    return address


@router.delete("/{customer_id}/addresses/{address_id}", status_code=204)
def delete_address(
    customer_id: str,
    address_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_customer_phone: str | None = Header(default=None),
    x_customer_email: str | None = Header(default=None),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Cliente não encontrado.")
    require_customer_or_admin(customer, db, authorization, x_customer_phone, x_customer_email)
    address = db.query(Address).filter(
        Address.id == address_id, Address.customer_id == customer_id
    ).first()
    if not address:
        raise HTTPException(404, "Endereço não encontrado.")
    db.delete(address)
    db.commit()


# ── Customer orders ────────────────────────────────────────────────────────────

@router.get("/{customer_id}/orders")
def get_customer_orders(
    customer_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_customer_phone: str | None = Header(default=None),
    x_customer_email: str | None = Header(default=None),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Cliente não encontrado.")
    require_customer_or_admin(customer, db, authorization, x_customer_phone, x_customer_email)

    orders = (
        db.query(Order)
        .filter(Order.customer_id == customer_id)
        .order_by(desc(Order.created_at))
        .limit(limit)
        .all()
    )

    result = []
    for o in orders:
        status_val = o.status.value if hasattr(o.status, "value") else str(o.status)
        items = []
        for item in o.items:
            flavors = [{"name": f.flavor_name, "price": f.flavor_price} for f in item.flavors] if item.flavors else []
            items.append({
                "id": item.id,
                "product_id": item.product_id,
                "quantity": item.quantity,
                "selected_size": item.selected_size,
                "selected_crust_type": item.selected_crust_type,
                "selected_drink_variant": item.selected_drink_variant,
                "notes": item.notes,
                "flavors": flavors,
                "unit_price": item.unit_price,
            })
        result.append({
            "id": o.id,
            "status": status_val,
            "total": o.total,
            "subtotal": o.subtotal,
            "shipping_fee": o.shipping_fee,
            "discount": o.discount,
            "created_at": o.created_at,
            "paid_at": o.paid_at,
            "delivered_at": o.delivered_at,
            "delivery_name": o.delivery_name,
            "delivery_street": o.delivery_street,
            "delivery_city": o.delivery_city,
            "delivery_complement": o.delivery_complement,
            "coupon_id": o.coupon_id,
            "total_time_minutes": o.total_time_minutes,
            "estimated_time": o.estimated_time,
            "items": items,
            "payment_status": o.payment.status.value if o.payment else "pending",
        })
    return ok(result)


# ── Customer events timeline ──────────────────────────────────────────────────

@router.get("/{customer_id}/events")
def get_customer_events(
    customer_id: str,
    event_type: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Cliente não encontrado.")

    q = db.query(CustomerEvent).filter(CustomerEvent.customer_id == customer_id)
    if event_type:
        q = q.filter(CustomerEvent.event_type == event_type)

    events = q.order_by(desc(CustomerEvent.created_at)).limit(limit).all()

    return ok([{
        "id": e.id,
        "session_id": e.session_id,
        "event_type": e.event_type,
        "event_name": e.event_name,
        "event_description": e.event_description,
        "product_id": e.product_id,
        "order_id": e.order_id,
        "campaign_id": e.campaign_id,
        "coupon_id": e.coupon_id,
        "metadata_json": e.metadata_json,
        "source": e.source,
        "utm_source": e.utm_source,
        "utm_campaign": e.utm_campaign,
        "device_type": e.device_type,
        "browser": e.browser,
        "page_url": e.page_url,
        "created_at": e.created_at,
    } for e in events])


# ── Customer behavioral summary ────────────────────────────────────────────────

@router.get("/{customer_id}/summary")
def get_customer_summary(
    customer_id: str,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Cliente não encontrado.")

    orders = db.query(Order).filter(Order.customer_id == customer_id).all()
    total_orders = len(orders)
    total_spent = sum(o.total or 0 for o in orders)
    avg_ticket = total_spent / total_orders if total_orders > 0 else 0

    def _status(o: Order) -> str:
        return o.status.value if hasattr(o.status, "value") else str(o.status)

    paid_count = len([o for o in orders if _status(o) in ("paid", "pago", "preparing", "ready_for_pickup", "on_the_way", "delivered")])
    delivered_count = len([o for o in orders if _status(o) == "delivered"])
    cancelled_count = len([o for o in orders if _status(o) == "cancelled"])

    sorted_orders = sorted(orders, key=lambda o: o.created_at)
    last_order = sorted_orders[-1] if sorted_orders else None
    first_order = sorted_orders[0] if sorted_orders else None

    events = db.query(CustomerEvent).filter(CustomerEvent.customer_id == customer_id).all()
    total_visits = sum(1 for e in events if e.event_type == "site_opened")
    products_viewed = sum(1 for e in events if e.event_type == "product_viewed")
    cart_abandonments = sum(1 for e in events if e.event_type == "cart_abandoned")
    checkout_abandonments = sum(1 for e in events if e.event_type == "checkout_abandoned")

    last_event = sorted(events, key=lambda e: e.created_at, reverse=True)[0] if events else None

    if total_orders >= 5:
        behavior_status = "recorrente"
    elif total_orders >= 2:
        behavior_status = "ativo"
    elif total_orders == 1:
        behavior_status = "novo_comprador"
    elif cart_abandonments > 0:
        behavior_status = "interessado"
    elif total_visits > 0:
        behavior_status = "visitante"
    else:
        behavior_status = "lead"

    return ok({
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "crm_status": customer.crm_status,
            "source": customer.source,
            "utm_source": customer.utm_source,
            "utm_campaign": customer.utm_campaign,
            "created_at": customer.created_at,
        },
        "orders": {
            "total": total_orders,
            "total_spent": round(total_spent, 2),
            "avg_ticket": round(avg_ticket, 2),
            "paid": paid_count,
            "delivered": delivered_count,
            "cancelled": cancelled_count,
            "last_order_at": last_order.created_at if last_order else None,
            "first_order_at": first_order.created_at if first_order else None,
        },
        "behavior": {
            "status": behavior_status,
            "total_visits": total_visits,
            "products_viewed": products_viewed,
            "cart_abandonments": cart_abandonments,
            "checkout_abandonments": checkout_abandonments,
            "last_activity_at": last_event.created_at if last_event else None,
        },
    })

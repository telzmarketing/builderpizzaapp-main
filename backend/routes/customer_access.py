import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.models.customer import Customer
from backend.routes.admin_auth import get_current_admin


def _normalize_contact(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^\d+]", "", value).lower()


def _matches_customer_contact(
    customer: Customer,
    phone: str | None,
    email: str | None,
) -> bool:
    phone_match = bool(customer.phone) and _normalize_contact(phone) == _normalize_contact(customer.phone)
    email_match = bool(customer.email) and (email or "").strip().lower() == customer.email.strip().lower()
    return phone_match or email_match


def require_customer_or_admin(
    customer: Customer,
    db: Session,
    authorization: str | None,
    x_customer_phone: str | None,
    x_customer_email: str | None,
) -> None:
    if authorization and authorization.startswith("Bearer "):
        try:
            get_current_admin(authorization=authorization, db=db)
            return
        except HTTPException:
            pass

    if _matches_customer_contact(customer, x_customer_phone, x_customer_email):
        return

    raise HTTPException(403, "Acesso ao cliente nao autorizado.")


def require_customer_id_or_admin(
    customer_id: str,
    db: Session,
    authorization: str | None,
    x_customer_phone: str | None,
    x_customer_email: str | None,
) -> Customer:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(404, "Cliente nao encontrado.")

    require_customer_or_admin(
        customer,
        db,
        authorization,
        x_customer_phone,
        x_customer_email,
    )
    return customer

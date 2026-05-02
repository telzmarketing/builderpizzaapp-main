import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.models.order import Order
from backend.routes.admin_auth import get_current_admin
from backend.routes.customer_access import require_customer_id_or_admin


def _normalize_contact(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^\d+]", "", value).lower()


def require_order_or_admin(
    order: Order,
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

    if order.customer_id:
        try:
            require_customer_id_or_admin(
                order.customer_id,
                db,
                authorization,
                x_customer_phone,
                x_customer_email,
            )
            return
        except HTTPException:
            pass

    if order.delivery_phone and _normalize_contact(x_customer_phone) == _normalize_contact(order.delivery_phone):
        return

    raise HTTPException(403, "Acesso ao pedido nao autorizado.")

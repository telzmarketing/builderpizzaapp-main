from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.models.order import Order
from backend.routes.admin_auth import authenticate_admin_token
from backend.routes.customer_access import require_customer_id_or_admin


def require_order_or_admin(
    order: Order,
    db: Session,
    authorization: str | None,
    x_customer_phone: str | None,
    x_customer_email: str | None,
) -> None:
    if authorization and authorization.startswith("Bearer "):
        try:
            authenticate_admin_token(authorization=authorization, db=db)
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

    raise HTTPException(401, "Sessao autenticada de cliente obrigatoria.")

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.core.tenant_auth import get_current_tenant_context
from backend.models.order import Order
from backend.routes.admin_auth import authenticate_admin_token
from backend.routes.customer_access import require_customer_id_or_admin


def require_order_or_admin(
    order: Order,
    db: Session,
    authorization: str | None,
    x_customer_phone: str | None,
    x_customer_email: str | None,
    *,
    expected_tenant_id: str | None = None,
) -> None:
    if authorization and authorization.startswith("Bearer "):
        try:
            admin = authenticate_admin_token(authorization=authorization, db=db)
        except HTTPException:
            pass
        else:
            if expected_tenant_id:
                context = get_current_tenant_context(
                    authorization=authorization,
                    requested_tenant_id=expected_tenant_id,
                    admin=admin,
                    db=db,
                )
                if context.tenant_id != expected_tenant_id:
                    raise HTTPException(403, "Acesso ao tenant nao autorizado.")
            return

    if order.customer_id:
        try:
            require_customer_id_or_admin(
                order.customer_id,
                db,
                authorization,
                x_customer_phone,
                x_customer_email,
                expected_tenant_id=expected_tenant_id,
            )
            return
        except HTTPException:
            pass

    raise HTTPException(401, "Sessao autenticada de cliente obrigatoria.")

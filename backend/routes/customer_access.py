from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.models.customer import Customer
from backend.routes.admin_auth import authenticate_admin_token
from backend.core.customer_auth import authenticate_customer_token


def require_customer_or_admin(
    customer: Customer,
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
            authenticated = authenticate_customer_token(
                authorization,
                db,
                expected_tenant_id=customer.tenant_id,
            )
            if authenticated.id == customer.id:
                return
            raise HTTPException(403, "Acesso ao cliente nao autorizado.")

    # Phone and e-mail remain accepted as HTTP parameters for wire
    # compatibility, but are deliberately not credentials anymore.
    raise HTTPException(401, "Sessao autenticada de cliente obrigatoria.")


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

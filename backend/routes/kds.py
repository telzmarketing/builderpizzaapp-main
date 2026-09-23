"""Dedicated, permission-gated APIs for the two touch KDS stations."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import err, ok
from backend.database import get_db
from backend.schemas.kds import DispatchAssignIn
from backend.services.kds_service import KdsService


router = APIRouter(prefix="/kds", tags=["kds"])


@router.get("/kitchen/orders")
def kitchen_orders(
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "view")),
):
    return ok(KdsService(db, actor.tenant_context).kitchen_orders())


@router.post("/kitchen/orders/{order_id}/start")
def kitchen_start(
    order_id: str,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit")),
):
    try:
        result = KdsService(db, actor.tenant_context).start_preparation(order_id, actor_id=actor.user_id)
        return ok(result, "Pedido enviado para preparacao.")
    except DomainError as exc:
        return err(exc)


@router.post("/kitchen/orders/{order_id}/ready")
def kitchen_ready(
    order_id: str,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit")),
):
    try:
        result = KdsService(db, actor.tenant_context).mark_ready(order_id, actor_id=actor.user_id)
        return ok(result, "Pedido marcado como pronto.")
    except DomainError as exc:
        return err(exc)


@router.post("/kitchen/orders/{order_id}/pickup-complete")
def kitchen_pickup_complete(
    order_id: str,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit")),
):
    try:
        result = KdsService(db, actor.tenant_context).complete_pickup(order_id, actor_id=actor.user_id)
        return ok(result, "Retirada concluida.")
    except DomainError as exc:
        return err(exc)


@router.get("/dispatch/orders")
def dispatch_orders(
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "view")),
):
    return ok(KdsService(db, actor.tenant_context).dispatch_orders())


@router.get("/dispatch/drivers")
def dispatch_drivers(
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "view")),
):
    return ok(KdsService(db, actor.tenant_context).available_drivers())


@router.post("/dispatch/orders/{order_id}/assign")
def dispatch_assign(
    order_id: str,
    body: DispatchAssignIn,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("expedicao", "edit")),
):
    try:
        result = KdsService(db, actor.tenant_context).assign_driver(
            order_id, body.delivery_person_id,
            estimated_minutes=body.estimated_minutes, actor_id=actor.user_id,
        )
        return ok(result, "Motoboy atribuido; pedido aguarda inicio da rota.")
    except DomainError as exc:
        return err(exc)

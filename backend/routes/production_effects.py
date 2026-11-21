from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import err, ok
from backend.database import get_db
from backend.schemas.production_effects import (
    OrderBonificationIn,
    ProductionEffectOut,
    ProductionLossIn,
    ProductionReproductionIn,
)
from backend.services.production_effects_service import ProductionEffectsService


router = APIRouter(prefix="/production-effects", tags=["production-effects"])


def _service(db: Session, actor: AuthorizedTenantActor) -> ProductionEffectsService:
    return ProductionEffectsService(db, actor.tenant_context, actor.user_id)


@router.post("/loss", response_model=ProductionEffectOut, status_code=201)
@router.post("/losses", response_model=ProductionEffectOut, status_code=201, include_in_schema=False)
def record_loss(
    body: ProductionLossIn,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=200),
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit")),
):
    try:
        return ok(_service(db, actor).record_loss(body, idempotency_key), status_code=201)
    except DomainError as exc:
        return err(exc)


@router.post("/reproduction", response_model=ProductionEffectOut, status_code=201)
@router.post("/reproductions", response_model=ProductionEffectOut, status_code=201, include_in_schema=False)
def create_reproduction(
    body: ProductionReproductionIn,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=200),
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("cozinha", "edit")),
):
    try:
        return ok(_service(db, actor).create_reproduction(body, idempotency_key), status_code=201)
    except DomainError as exc:
        return err(exc)


@router.post("/bonification", response_model=ProductionEffectOut, status_code=201)
@router.post("/bonifications", response_model=ProductionEffectOut, status_code=201, include_in_schema=False)
def bonify_order(
    body: OrderBonificationIn,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=200),
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("pedidos", "edit")),
):
    try:
        return ok(_service(db, actor).bonify_order(body, idempotency_key), status_code=201)
    except DomainError as exc:
        return err(exc)

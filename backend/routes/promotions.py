"""
Promotions endpoints.

GET /promotions          → list (loja: ?active_only=true, ERP: all)
GET /promotions/{id}     → single promotion
POST /promotions         → create (ERP / admin)
PUT  /promotions/{id}    → update (ERP / admin)
DELETE /promotions/{id}  → delete (ERP / admin)
"""
import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from backend.core.response import ok, created, no_content, err_msg
from backend.core.tenant_ownership import assign_tenant_on_create, identity_catalog_enforcement_enabled, scope_query_to_tenant
from backend.core.tenant_runtime import resolve_panel_tenant_context, resolve_public_tenant_context
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.models.promotion import Promotion
from backend.routes.admin_auth import get_current_admin
from backend.schemas.promotion import PromotionCreate, PromotionUpdate, PromotionOut
from backend.core.security import decode_access_token
from jose import JWTError

router = APIRouter(prefix="/promotions", tags=["promotions"])


def _require_admin(request: Request, db: Session) -> AdminUser:
    return get_current_admin(
        request=request,
        authorization=request.headers.get("authorization"),
        db=db,
    )


def _has_admin_bearer(request: Request) -> bool:
    authorization = request.headers.get("authorization") or ""
    if not authorization.startswith("Bearer "):
        return False
    try:
        payload = decode_access_token(authorization.removeprefix("Bearer ").strip())
    except JWTError:
        return False
    return payload.get("token_kind") != "customer"


def _query(db: Session, context):
    return scope_query_to_tenant(
        db.query(Promotion), Promotion, context, enabled=identity_catalog_enforcement_enabled()
    )


@router.get("")
def list_promotions(
    request: Request,
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """
    List promotions. Pass ?active_only=true for the loja home banner.
    ERP/admin uses the full list (active_only=false).
    """
    context = (
        resolve_public_tenant_context(request, db)
        if active_only
        else resolve_panel_tenant_context(request, db, _require_admin(request, db))
    )

    q = _query(db, context)
    if active_only:
        q = q.filter(Promotion.active == True)  # noqa: E712
    promos = q.order_by(Promotion.created_at.desc()).all()
    return ok(promos)


@router.get("/{promo_id}")
def get_promotion(promo_id: str, request: Request, db: Session = Depends(get_db)):
    is_admin_request = _has_admin_bearer(request)
    context = (
        resolve_panel_tenant_context(request, db, _require_admin(request, db))
        if is_admin_request
        else resolve_public_tenant_context(request, db)
    )
    promo = _query(db, context).filter(Promotion.id == promo_id).first()
    if not promo:
        return err_msg(f"Promoção '{promo_id}' não encontrada.", code="PromotionNotFound", status_code=404)
    if not promo.active and not is_admin_request:
        return err_msg("Promocao nao encontrada.", code="PromotionNotFound", status_code=404)
    if not promo.active and is_admin_request:
        context = resolve_panel_tenant_context(request, db, _require_admin(request, db))
        promo = _query(db, context).filter(Promotion.id == promo_id).first()
        if not promo:
            return err_msg(f"PromoÃ§Ã£o '{promo_id}' nÃ£o encontrada.", code="PromotionNotFound", status_code=404)
    return ok(promo)


@router.post("", status_code=201)
def create_promotion(body: PromotionCreate, request: Request, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    context = resolve_panel_tenant_context(request, db, admin)
    promo = Promotion(id=str(uuid.uuid4()), **body.model_dump())
    assign_tenant_on_create(promo, context, enabled=identity_catalog_enforcement_enabled())
    db.add(promo)
    db.commit()
    db.refresh(promo)
    return created(promo, "Promoção criada.")


@router.put("/{promo_id}")
def update_promotion(promo_id: str, body: PromotionUpdate, request: Request, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    context = resolve_panel_tenant_context(request, db, admin)
    promo = _query(db, context).filter(Promotion.id == promo_id).first()
    if not promo:
        return err_msg(f"Promoção '{promo_id}' não encontrada.", code="PromotionNotFound", status_code=404)
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(promo, key, value)
    db.commit()
    db.refresh(promo)
    return ok(promo, "Promoção atualizada.")


@router.delete("/{promo_id}", status_code=204)
def delete_promotion(promo_id: str, request: Request, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    context = resolve_panel_tenant_context(request, db, admin)
    promo = _query(db, context).filter(Promotion.id == promo_id).first()
    if not promo:
        return err_msg(f"Promoção '{promo_id}' não encontrada.", code="PromotionNotFound", status_code=404)
    db.delete(promo)
    db.commit()
    return no_content()

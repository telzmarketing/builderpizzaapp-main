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
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.models.promotion import Promotion
from backend.routes.admin_auth import get_current_admin
from backend.schemas.promotion import PromotionCreate, PromotionUpdate, PromotionOut

router = APIRouter(prefix="/promotions", tags=["promotions"])


def _require_admin(request: Request, db: Session) -> AdminUser:
    return get_current_admin(
        authorization=request.headers.get("authorization"),
        db=db,
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
    if not active_only:
        _require_admin(request, db)

    q = db.query(Promotion)
    if active_only:
        q = q.filter(Promotion.active == True)  # noqa: E712
    promos = q.order_by(Promotion.created_at.desc()).all()
    return ok(promos)


@router.get("/{promo_id}")
def get_promotion(promo_id: str, request: Request, db: Session = Depends(get_db)):
    promo = db.query(Promotion).filter(Promotion.id == promo_id).first()
    if not promo:
        return err_msg(f"Promoção '{promo_id}' não encontrada.", code="PromotionNotFound", status_code=404)
    if not promo.active:
        _require_admin(request, db)
    return ok(promo)


@router.post("", status_code=201)
def create_promotion(body: PromotionCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    promo = Promotion(id=str(uuid.uuid4()), **body.model_dump())
    db.add(promo)
    db.commit()
    db.refresh(promo)
    return created(promo, "Promoção criada.")


@router.put("/{promo_id}")
def update_promotion(promo_id: str, body: PromotionUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    promo = db.query(Promotion).filter(Promotion.id == promo_id).first()
    if not promo:
        return err_msg(f"Promoção '{promo_id}' não encontrada.", code="PromotionNotFound", status_code=404)
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(promo, key, value)
    db.commit()
    db.refresh(promo)
    return ok(promo, "Promoção atualizada.")


@router.delete("/{promo_id}", status_code=204)
def delete_promotion(promo_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    promo = db.query(Promotion).filter(Promotion.id == promo_id).first()
    if not promo:
        return err_msg(f"Promoção '{promo_id}' não encontrada.", code="PromotionNotFound", status_code=404)
    db.delete(promo)
    db.commit()
    return no_content()

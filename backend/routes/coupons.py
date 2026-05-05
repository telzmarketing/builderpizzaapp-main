import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.coupon import Coupon, CouponUsage
from backend.routes.admin_auth import get_current_admin
from backend.routes.customer_access import require_customer_id_or_admin
from backend.schemas.coupon import (
    CouponCreate, CouponUpdate, CouponOut,
    CouponApplyIn, CouponApplyOut, CouponUsageOut,
)
from backend.services.coupon_service import CouponService

router = APIRouter(prefix="/coupons", tags=["coupons"])


def _validate_trigger_automation(trigger_automation_id: str | None, db: Session) -> None:
    if not trigger_automation_id:
        return
    exists = db.execute(
        text("SELECT 1 FROM marketing_automations WHERE id = :id"),
        {"id": trigger_automation_id},
    ).scalar()
    if not exists:
        raise HTTPException(400, "Gatilho selecionado nao encontrado.")


@router.get("", response_model=list[CouponOut])
def list_coupons(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return db.query(Coupon).order_by(Coupon.created_at.desc()).all()


@router.get("/public", response_model=list[CouponOut])
def list_public_coupons(
    request: Request,
    customer_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    customer_phone: str | None = None
    if customer_id:
        customer = require_customer_id_or_admin(
            customer_id=customer_id,
            db=db,
            authorization=request.headers.get("authorization"),
            x_customer_phone=request.headers.get("x-customer-phone"),
            x_customer_email=request.headers.get("x-customer-email"),
        )
        customer_phone = customer.phone

    public_coupons = (
        db.query(Coupon)
        .filter(Coupon.active == True)  # noqa: E712
        .filter(Coupon.public_profile == True)  # noqa: E712
        .filter((Coupon.starts_at.is_(None)) | (Coupon.starts_at <= now))
        .filter((Coupon.ends_at.is_(None)) | (Coupon.ends_at >= now))
        .filter((Coupon.expiry_date.is_(None)) | (Coupon.expiry_date >= now))
        .filter((Coupon.max_uses.is_(None)) | (Coupon.used_count < Coupon.max_uses))
        .filter(Coupon.trigger_automation_id.is_(None))
        .order_by(Coupon.created_at.desc())
        .all()
    )

    used_coupon_ids: set[str] = set()
    used_coupons: list[Coupon] = []
    if customer_id or customer_phone:
        usage_filter = []
        if customer_id:
            usage_filter.append(CouponUsage.customer_id == customer_id)
        if customer_phone:
            usage_filter.append(CouponUsage.phone == customer_phone)

        usages = db.query(CouponUsage.coupon_id).filter(or_(*usage_filter)).all()
        used_coupon_ids = {coupon_id for (coupon_id,) in usages}
        if used_coupon_ids:
            used_coupons = (
                db.query(Coupon)
                .filter(Coupon.id.in_(used_coupon_ids))
                .order_by(Coupon.created_at.desc())
                .all()
            )

    by_id: dict[str, Coupon] = {coupon.id: coupon for coupon in public_coupons}
    for coupon in used_coupons:
        by_id[coupon.id] = coupon

    result = []
    for coupon in sorted(by_id.values(), key=lambda item: item.created_at, reverse=True):
        result.append({
            "id": coupon.id,
            "code": coupon.code,
            "description": coupon.description,
            "icon": coupon.icon,
            "coupon_type": coupon.coupon_type,
            "discount_value": coupon.discount_value,
            "min_order_value": coupon.min_order_value,
            "max_uses": coupon.max_uses,
            "max_uses_per_customer": coupon.max_uses_per_customer,
            "used_count": coupon.used_count,
            "starts_at": coupon.starts_at,
            "ends_at": coupon.ends_at,
            "expiry_date": coupon.expiry_date,
            "free_shipping": bool(coupon.free_shipping),
            "gift_enabled": bool(coupon.gift_enabled),
            "gift_product_id": coupon.gift_product_id,
            "gift_quantity": coupon.gift_quantity or 1,
            "stackable": bool(coupon.stackable),
            "public_profile": bool(coupon.public_profile),
            "used_by_customer": coupon.id in used_coupon_ids,
            "active": bool(coupon.active),
            "campaign_id": coupon.campaign_id,
            "trigger_automation_id": coupon.trigger_automation_id,
            "created_at": coupon.created_at,
        })
    return result


@router.get("/usage", response_model=list[CouponUsageOut])
def list_all_usage(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return CouponService(db).list_usage()


@router.get("/{coupon_id}", response_model=CouponOut)
def get_coupon(coupon_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(404, "Cupom não encontrado.")
    return coupon


@router.get("/{coupon_id}/usage", response_model=list[CouponUsageOut])
def get_coupon_usage(coupon_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return CouponService(db).list_usage(coupon_id=coupon_id)


@router.post("", response_model=CouponOut, status_code=201)
def create_coupon(body: CouponCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    existing = db.query(Coupon).filter(Coupon.code == body.code.upper()).first()
    if existing:
        raise HTTPException(400, f"Código '{body.code}' já existe.")
    data = body.model_dump()
    data["trigger_automation_id"] = data.get("trigger_automation_id") or None
    _validate_trigger_automation(data["trigger_automation_id"], db)
    coupon = Coupon(id=str(uuid.uuid4()), **{**data, "code": body.code.upper()})
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.put("/{coupon_id}", response_model=CouponOut)
def update_coupon(coupon_id: str, body: CouponUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(404, "Cupom não encontrado.")
    data = body.model_dump(exclude_unset=True)
    if "code" in data:
        data["code"] = data["code"].upper()
        existing = db.query(Coupon).filter(Coupon.code == data["code"], Coupon.id != coupon_id).first()
        if existing:
            raise HTTPException(400, f"Código '{data['code']}' já existe.")
    if "trigger_automation_id" in data:
        data["trigger_automation_id"] = data.get("trigger_automation_id") or None
        _validate_trigger_automation(data["trigger_automation_id"], db)
    for key, value in data.items():
        setattr(coupon, key, value)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.delete("/{coupon_id}", status_code=204)
def delete_coupon(coupon_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(404, "Cupom não encontrado.")
    db.delete(coupon)
    db.commit()


@router.post("/apply", response_model=CouponApplyOut)
def apply(body: CouponApplyIn, db: Session = Depends(get_db)):
    return CouponService(db).apply(body)

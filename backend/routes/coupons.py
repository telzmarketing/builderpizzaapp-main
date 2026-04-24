import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.coupon import Coupon
from backend.routes.admin_auth import get_current_admin
from backend.schemas.coupon import (
    CouponCreate, CouponUpdate, CouponOut,
    CouponApplyIn, CouponApplyOut, CouponUsageOut,
)
from backend.services.coupon_service import CouponService

router = APIRouter(prefix="/coupons", tags=["coupons"])


@router.get("", response_model=list[CouponOut])
def list_coupons(db: Session = Depends(get_db)):
    return db.query(Coupon).order_by(Coupon.created_at.desc()).all()


@router.get("/usage", response_model=list[CouponUsageOut])
def list_all_usage(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return CouponService(db).list_usage()


@router.get("/{coupon_id}", response_model=CouponOut)
def get_coupon(coupon_id: str, db: Session = Depends(get_db)):
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
    coupon = Coupon(id=str(uuid.uuid4()), **{**body.model_dump(), "code": body.code.upper()})
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.put("/{coupon_id}", response_model=CouponOut)
def update_coupon(coupon_id: str, body: CouponUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(404, "Cupom não encontrado.")
    data = body.model_dump(exclude_none=True)
    if "code" in data:
        data["code"] = data["code"].upper()
        existing = db.query(Coupon).filter(Coupon.code == data["code"], Coupon.id != coupon_id).first()
        if existing:
            raise HTTPException(400, f"Código '{data['code']}' já existe.")
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

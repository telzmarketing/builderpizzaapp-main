import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.coupon import Coupon
from backend.schemas.coupon import (
    CouponCreate, CouponUpdate, CouponOut,
    CouponApplyIn, CouponApplyOut,
)
from backend.services.coupon_service import apply_coupon

router = APIRouter(prefix="/coupons", tags=["coupons"])


@router.get("", response_model=list[CouponOut])
def list_coupons(db: Session = Depends(get_db)):
    return db.query(Coupon).order_by(Coupon.created_at.desc()).all()


@router.get("/{coupon_id}", response_model=CouponOut)
def get_coupon(coupon_id: str, db: Session = Depends(get_db)):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(404, "Cupom não encontrado.")
    return coupon


@router.post("", response_model=CouponOut, status_code=201)
def create_coupon(body: CouponCreate, db: Session = Depends(get_db)):
    existing = db.query(Coupon).filter(Coupon.code == body.code.upper()).first()
    if existing:
        raise HTTPException(400, f"Código '{body.code}' já existe.")
    coupon = Coupon(id=str(uuid.uuid4()), **{**body.model_dump(), "code": body.code.upper()})
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.put("/{coupon_id}", response_model=CouponOut)
def update_coupon(coupon_id: str, body: CouponUpdate, db: Session = Depends(get_db)):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(404, "Cupom não encontrado.")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(coupon, key, value)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.delete("/{coupon_id}", status_code=204)
def delete_coupon(coupon_id: str, db: Session = Depends(get_db)):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(404, "Cupom não encontrado.")
    db.delete(coupon)
    db.commit()


@router.post("/apply", response_model=CouponApplyOut)
def apply(body: CouponApplyIn, db: Session = Depends(get_db)):
    return apply_coupon(body, db)

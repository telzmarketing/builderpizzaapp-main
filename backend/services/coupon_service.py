from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.models.coupon import Coupon, CouponType
from backend.schemas.coupon import CouponApplyIn, CouponApplyOut


def apply_coupon(payload: CouponApplyIn, db: Session) -> CouponApplyOut:
    coupon: Coupon | None = (
        db.query(Coupon)
        .filter(Coupon.code == payload.code.upper(), Coupon.active == True)  # noqa: E712
        .first()
    )

    if not coupon:
        return CouponApplyOut(valid=False, discount_amount=0, message="Cupom não encontrado ou inativo.")

    now = datetime.now(timezone.utc)
    if coupon.expiry_date and coupon.expiry_date < now:
        return CouponApplyOut(valid=False, discount_amount=0, message="Cupom expirado.")

    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        return CouponApplyOut(valid=False, discount_amount=0, message="Cupom esgotado.")

    if payload.order_subtotal < coupon.min_order_value:
        return CouponApplyOut(
            valid=False, discount_amount=0,
            message=f"Pedido mínimo de R$ {coupon.min_order_value:.2f} não atingido."
        )

    if coupon.coupon_type == CouponType.percentage:
        discount = round(payload.order_subtotal * coupon.discount_value / 100, 2)
    else:
        discount = min(coupon.discount_value, payload.order_subtotal)

    return CouponApplyOut(
        valid=True,
        coupon_id=coupon.id,
        discount_amount=discount,
        message=f"Cupom aplicado! Desconto de R$ {discount:.2f}.",
    )


def mark_coupon_used(coupon_id: str, db: Session) -> None:
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if coupon:
        coupon.used_count += 1
        db.commit()

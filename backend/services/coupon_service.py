import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.models.coupon import Coupon, CouponType, CouponUsage
from backend.schemas.coupon import CouponApplyIn, CouponApplyOut


class CouponService:
    def __init__(self, db: Session):
        self._db = db

    def apply(self, payload: CouponApplyIn) -> CouponApplyOut:
        coupon: Coupon | None = (
            self._db.query(Coupon)
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

        # Per-customer limit check
        if coupon.max_uses_per_customer is not None:
            customer_uses = self._count_customer_uses(coupon.id, payload.customer_id, payload.phone)
            if customer_uses >= coupon.max_uses_per_customer:
                return CouponApplyOut(
                    valid=False, discount_amount=0,
                    message="Você já utilizou este cupom o número máximo de vezes permitido."
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

    def _count_customer_uses(self, coupon_id: str, customer_id: str | None, phone: str | None) -> int:
        if not customer_id and not phone:
            return 0
        q = self._db.query(CouponUsage).filter(CouponUsage.coupon_id == coupon_id)
        if customer_id:
            return q.filter(CouponUsage.customer_id == customer_id).count()
        return q.filter(CouponUsage.phone == phone).count()

    def record_usage(self, coupon_id: str, customer_id: str | None, phone: str | None, order_id: str | None) -> None:
        usage = CouponUsage(
            id=str(uuid.uuid4()),
            coupon_id=coupon_id,
            customer_id=customer_id,
            phone=phone,
            order_id=order_id,
        )
        self._db.add(usage)
        coupon = self._db.query(Coupon).filter(Coupon.id == coupon_id).first()
        if coupon:
            coupon.used_count += 1
        self._db.commit()

    def list_usage(self, coupon_id: str | None = None):
        q = self._db.query(CouponUsage)
        if coupon_id:
            q = q.filter(CouponUsage.coupon_id == coupon_id)
        return q.order_by(CouponUsage.created_at.desc()).all()


# ── Backward-compatible standalone functions ──────────────────────────────────

def apply_coupon(payload: CouponApplyIn, db: Session) -> CouponApplyOut:
    return CouponService(db).apply(payload)


def mark_coupon_used(coupon_id: str, db: Session) -> None:
    svc = CouponService(db)
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if coupon:
        coupon.used_count += 1
        db.commit()

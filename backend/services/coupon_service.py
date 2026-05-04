import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.models.coupon import Coupon, CouponType, CouponUsage
from backend.models.product import Product
from backend.schemas.coupon import CouponApplyIn, CouponApplyOut, CouponGiftOut


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
            return CouponApplyOut(valid=False, discount_amount=0, message="Cupom nao encontrado ou inativo.")

        now = datetime.now(timezone.utc)
        starts_at = self._as_utc(coupon.starts_at)
        if starts_at and starts_at > now:
            return CouponApplyOut(valid=False, discount_amount=0, message="Cupom ainda nao esta ativo.")

        effective_end = self._as_utc(coupon.ends_at or coupon.expiry_date)
        if effective_end and effective_end < now:
            return CouponApplyOut(valid=False, discount_amount=0, message="Cupom expirado.")

        if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
            return CouponApplyOut(valid=False, discount_amount=0, message="Cupom esgotado.")

        if payload.order_subtotal < coupon.min_order_value:
            return CouponApplyOut(
                valid=False,
                discount_amount=0,
                message=f"Pedido minimo de R$ {coupon.min_order_value:.2f} nao atingido.",
            )

        if coupon.max_uses_per_customer is not None:
            customer_uses = self._count_customer_uses(coupon.id, payload.customer_id, payload.phone)
            if customer_uses >= coupon.max_uses_per_customer:
                return CouponApplyOut(
                    valid=False,
                    discount_amount=0,
                    message="Voce ja utilizou este cupom o numero maximo de vezes permitido.",
                )

        gift = self._resolve_gift(coupon)
        if coupon.gift_enabled and gift is None:
            return CouponApplyOut(valid=False, discount_amount=0, message="Produto brinde indisponivel.")

        discount = self._financial_discount(coupon, payload.order_subtotal)
        delivery_fee_original = round(max(0.0, payload.delivery_fee or 0.0), 2)
        delivery_fee_discount = delivery_fee_original if coupon.free_shipping else 0.0
        delivery_fee_final = round(max(0.0, delivery_fee_original - delivery_fee_discount), 2)

        benefits: list[str] = []
        if discount > 0:
            benefits.append(f"desconto de R$ {discount:.2f}")
        if coupon.free_shipping:
            benefits.append("frete gratis")
        if gift:
            benefits.append(f"brinde: {gift.quantity}x {gift.name}")

        message = "Cupom aplicado!"
        if benefits:
            message += " " + " + ".join(benefits) + "."

        return CouponApplyOut(
            valid=True,
            coupon_id=coupon.id,
            coupon_code=coupon.code,
            discount_amount=discount,
            free_shipping=bool(coupon.free_shipping),
            delivery_fee_original=delivery_fee_original,
            delivery_fee_discount=delivery_fee_discount,
            delivery_fee_final=delivery_fee_final,
            free_shipping_applied=bool(coupon.free_shipping),
            gift=gift,
            message=message,
        )

    def _resolve_gift(self, coupon: Coupon) -> CouponGiftOut | None:
        if not coupon.gift_enabled or not coupon.gift_product_id:
            return None

        product = (
            self._db.query(Product)
            .filter(Product.id == coupon.gift_product_id, Product.active == True)  # noqa: E712
            .first()
        )
        if not product:
            return None

        return CouponGiftOut(
            product_id=product.id,
            name=product.name,
            icon=product.icon,
            quantity=max(1, coupon.gift_quantity or 1),
            original_price=round(product.price, 2),
            coupon_id=coupon.id,
            coupon_code=coupon.code,
        )

    @staticmethod
    def _financial_discount(coupon: Coupon, subtotal: float) -> float:
        if coupon.discount_value <= 0:
            return 0.0
        if coupon.coupon_type == CouponType.percentage:
            return round(subtotal * coupon.discount_value / 100, 2)
        return round(min(coupon.discount_value, subtotal), 2)

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        if not value:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

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


def apply_coupon(payload: CouponApplyIn, db: Session) -> CouponApplyOut:
    return CouponService(db).apply(payload)


def mark_coupon_used(coupon_id: str, db: Session) -> None:
    svc = CouponService(db)
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if coupon:
        coupon.used_count += 1
        db.commit()

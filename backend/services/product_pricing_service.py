from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from backend.models.product import Product, ProductCrustType, ProductSize
from backend.models.product_promotion import ProductPromotion, ProductPromotionCombination


def normalize_crust_price_addition(price_addition: float | None, product_base_price: float | None) -> float:
    addition = float(price_addition or 0)
    if addition <= 0:
        return 0.0
    if product_base_price and product_base_price > 0 and abs(addition - product_base_price) <= 0.01:
        return 0.0
    return round(addition, 2)


@dataclass(frozen=True)
class ProductPriceResult:
    standard_price: float
    final_price: float
    promotion_id: str | None = None
    promotion_name: str | None = None
    discount_amount: float = 0.0
    discount_type: str | None = None
    promotion_blocked: bool = False
    promotion_block_reason: str | None = None

    @property
    def promotion_applied(self) -> bool:
        return self.promotion_id is not None


class ProductPricingService:
    """Centralizes product price calculation, including valid product promotions."""

    def __init__(self, db: Session):
        self._db = db

    def calculate(
        self,
        *,
        product: Product,
        size: ProductSize | None = None,
        crust: ProductCrustType | None = None,
        now: datetime | None = None,
        standard_price_override: float | None = None,
        flavor_count: int = 1,
        flavor_product_ids: list[str] | None = None,
    ) -> ProductPriceResult:
        standard_price = self._standard_price(product, size, crust, standard_price_override)
        current_dt = self._localized_now(now)

        promotions = (
            self._db.query(ProductPromotion)
            .filter(
                ProductPromotion.product_id == product.id,
                ProductPromotion.active == True,  # noqa: E712
            )
            .order_by(ProductPromotion.created_at.desc())
            .all()
        )

        if flavor_count > 1:
            blocked_promotion = next(
                (promotion for promotion in promotions if self._matching_combination(promotion.id, size, crust)),
                None,
            )
            if blocked_promotion:
                return ProductPriceResult(
                    standard_price=round(standard_price, 2),
                    final_price=round(standard_price, 2),
                    promotion_blocked=True,
                    promotion_block_reason="Promoção válida apenas para pizza de 1 sabor",
                )

        for promotion in promotions:
            if not self._promotion_is_valid(promotion, current_dt):
                continue

            combination = self._matching_combination(promotion.id, size, crust)
            if not combination:
                continue

            value = combination.promotional_value
            if value is None:
                value = promotion.default_value
            if value is None:
                continue

            final_price = self._apply_discount(standard_price, promotion.discount_type, float(value))
            discount = max(0.0, round(standard_price - final_price, 2))
            return ProductPriceResult(
                standard_price=round(standard_price, 2),
                final_price=round(final_price, 2),
                promotion_id=promotion.id,
                promotion_name=promotion.name,
                discount_amount=discount,
                discount_type=promotion.discount_type,
            )

        return ProductPriceResult(
            standard_price=round(standard_price, 2),
            final_price=round(standard_price, 2),
        )

    def _standard_price(
        self,
        product: Product,
        size: ProductSize | None,
        crust: ProductCrustType | None,
        override: float | None,
    ) -> float:
        if override is not None:
            return round(float(override), 2)
        base_price = float(size.price if size else product.price)
        if crust:
            base_price += normalize_crust_price_addition(crust.price_addition, product.price)
        return round(base_price, 2)

    def _localized_now(self, now: datetime | None) -> datetime:
        zone = ZoneInfo("America/Sao_Paulo")
        if now is None:
            return datetime.now(zone)
        if now.tzinfo is None:
            return now.replace(tzinfo=zone)
        return now.astimezone(zone)

    def _promotion_is_valid(self, promotion: ProductPromotion, current_dt: datetime) -> bool:
        weekdays = self._parse_weekdays(promotion.valid_weekdays)
        if current_dt.weekday() not in weekdays:
            return False

        current_date = current_dt.date()
        if promotion.start_date and current_date < self._as_date(promotion.start_date):
            return False
        if promotion.end_date and current_date > self._as_date(promotion.end_date):
            return False

        return self._time_window_is_valid(promotion, current_dt.time())

    def _matching_combination(
        self,
        promotion_id: str,
        size: ProductSize | None,
        crust: ProductCrustType | None,
    ) -> ProductPromotionCombination | None:
        query = self._db.query(ProductPromotionCombination).filter(
            ProductPromotionCombination.promotion_id == promotion_id,
            ProductPromotionCombination.active == True,  # noqa: E712
        )

        if size:
            query = query.filter(ProductPromotionCombination.product_size_id == size.id)
        else:
            query = query.filter(ProductPromotionCombination.product_size_id.is_(None))

        if crust:
            query = query.filter(ProductPromotionCombination.product_crust_type_id == crust.id)
        else:
            query = query.filter(ProductPromotionCombination.product_crust_type_id.is_(None))

        return query.first()

    def _apply_discount(self, standard_price: float, discount_type: str, value: float) -> float:
        if discount_type == "amount_off":
            return max(0.0, standard_price - value)
        if discount_type == "percent_off":
            return max(0.0, standard_price * (1 - (value / 100)))
        return max(0.0, value)

    def _parse_weekdays(self, raw: str | None) -> set[int]:
        if not raw:
            return set()
        try:
            values = json.loads(raw)
        except Exception:
            return set()
        return {int(day) for day in values if isinstance(day, int) or str(day).isdigit()}

    def _time_window_is_valid(self, promotion: ProductPromotion, current_time: time) -> bool:
        start = self._parse_time(promotion.start_time)
        end = self._parse_time(promotion.end_time)
        if not start and not end:
            return True
        current = current_time.replace(second=0, microsecond=0)
        if start and not end:
            return current >= start
        if end and not start:
            return current <= end
        if not start or not end:
            return True
        if start <= end:
            return start <= current <= end
        return current >= start or current <= end

    def _parse_time(self, value: str | None) -> time | None:
        if not value:
            return None
        try:
            return time.fromisoformat(value)
        except ValueError:
            return None

    def _as_date(self, value: date | datetime) -> date:
        if isinstance(value, datetime):
            return value.date()
        return value

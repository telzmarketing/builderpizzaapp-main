from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.models.product import Product
from backend.models.product_promotion import ProductPromotion
from backend.models.promotion_landing_page import PromotionLandingPage
from backend.services.product_pricing_service import ProductPricingService


class PromotionLandingNotFound(DomainError):
    http_status = 404

    def __init__(self):
        super().__init__("Landing page promocional nao encontrada.", code="PromotionLandingNotFound")


class PromotionLandingRuleError(DomainError):
    def __init__(self, message: str, *, code: str = "PromotionLandingRuleError"):
        super().__init__(message, code=code)


class PromotionLandingService:
    def __init__(self, db: Session):
        self._db = db

    def list(self) -> list[PromotionLandingPage]:
        return (
            self._db.query(PromotionLandingPage)
            .order_by(PromotionLandingPage.updated_at.desc())
            .all()
        )

    def get(self, landing_id: str) -> PromotionLandingPage:
        landing = self._db.query(PromotionLandingPage).filter(PromotionLandingPage.id == landing_id).first()
        if not landing:
            raise PromotionLandingNotFound()
        return landing

    def get_by_product_promotion(self, product_id: str, promotion_id: str) -> PromotionLandingPage | None:
        return (
            self._db.query(PromotionLandingPage)
            .filter(
                PromotionLandingPage.product_id == product_id,
                PromotionLandingPage.promotion_id == promotion_id,
            )
            .order_by(PromotionLandingPage.updated_at.desc())
            .first()
        )

    def get_public_by_slug(self, slug: str) -> PromotionLandingPage:
        landing = (
            self._db.query(PromotionLandingPage)
            .filter(
                PromotionLandingPage.slug == slug,
                PromotionLandingPage.status == "published",
                PromotionLandingPage.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not landing or not self.promotion_is_active_now(landing.promotion):
            raise PromotionLandingNotFound()
        return landing

    def create(self, data: dict) -> PromotionLandingPage:
        product, promotion = self._validate_product_promotion(data["product_id"], data["promotion_id"])
        base_slug = data.get("slug") or product.name
        status = data.get("status") or "draft"
        landing = PromotionLandingPage(
            id=f"plp-{uuid.uuid4().hex[:10]}",
            **{
                **data,
                "slug": self._unique_slug(base_slug),
                "status": status,
                "published_at": datetime.now(timezone.utc) if status == "published" else None,
            },
        )
        self._db.add(landing)
        self._db.commit()
        self._db.refresh(landing)
        return landing

    def update(self, landing_id: str, data: dict) -> PromotionLandingPage:
        landing = self.get(landing_id)
        previous_status = landing.status
        if "slug" in data and data["slug"]:
            data["slug"] = self._unique_slug(data["slug"], current_id=landing.id)
        if "status" in data and data["status"] == "published" and previous_status != "published":
            data["published_at"] = datetime.now(timezone.utc)
        if "status" in data and data["status"] == "draft":
            data["published_at"] = None
        for key, value in data.items():
            setattr(landing, key, value)
        self._db.commit()
        self._db.refresh(landing)
        return landing

    def publish(self, landing_id: str) -> PromotionLandingPage:
        landing = self.get(landing_id)
        landing.status = "published"
        landing.is_active = True
        landing.published_at = datetime.now(timezone.utc)
        self._db.commit()
        self._db.refresh(landing)
        return landing

    def unpublish(self, landing_id: str) -> PromotionLandingPage:
        landing = self.get(landing_id)
        landing.status = "draft"
        landing.published_at = None
        self._db.commit()
        self._db.refresh(landing)
        return landing

    def active_landing_for_product(self, product: Product) -> PromotionLandingPage | None:
        active_promotion_ids = self._active_promotion_ids_for_product(product)
        if not active_promotion_ids:
            return None
        return (
            self._db.query(PromotionLandingPage)
            .filter(
                PromotionLandingPage.product_id == product.id,
                PromotionLandingPage.promotion_id.in_(active_promotion_ids),
                PromotionLandingPage.status == "published",
                PromotionLandingPage.is_active == True,  # noqa: E712
            )
            .order_by(PromotionLandingPage.published_at.desc().nullslast(), PromotionLandingPage.updated_at.desc())
            .first()
        )

    def promotion_is_active_now(self, promotion: ProductPromotion | None) -> bool:
        if not promotion or not promotion.active or not promotion.product:
            return False
        return promotion.id in self._active_promotion_ids_for_product(promotion.product)

    def _validate_product_promotion(self, product_id: str, promotion_id: str) -> tuple[Product, ProductPromotion]:
        product = self._db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise PromotionLandingRuleError("Produto vinculado nao encontrado.", code="ProductNotFound")
        promotion = (
            self._db.query(ProductPromotion)
            .filter(ProductPromotion.id == promotion_id, ProductPromotion.product_id == product_id)
            .first()
        )
        if not promotion:
            raise PromotionLandingRuleError(
                "A landing promocional precisa estar vinculada a uma promocao do proprio produto.",
                code="PromotionNotLinkedToProduct",
            )
        return product, promotion

    def _active_promotion_ids_for_product(self, product: Product) -> set[str]:
        pricing = ProductPricingService(self._db)
        active_sizes = [size for size in product.sizes if size.active] or [None]
        active_crusts = [crust for crust in product.crust_types if crust.active]
        crust_options = active_crusts or [None]
        active_ids: set[str] = set()
        for size in active_sizes:
            for crust in crust_options:
                quote = pricing.calculate(product=product, size=size, crust=crust)
                if quote.promotion_id:
                    active_ids.add(quote.promotion_id)
        return active_ids

    def _unique_slug(self, raw: str, current_id: str | None = None) -> str:
        base = self._slugify(raw) or f"promocao-{uuid.uuid4().hex[:6]}"
        slug = base[:150]
        suffix = 1
        while self._slug_exists(slug, current_id=current_id):
            suffix += 1
            tail = f"-{suffix}"
            slug = f"{base[:150 - len(tail)]}{tail}"
        return slug

    def _slug_exists(self, slug: str, *, current_id: str | None = None) -> bool:
        q = self._db.query(PromotionLandingPage).filter(PromotionLandingPage.slug == slug)
        if current_id:
            q = q.filter(PromotionLandingPage.id != current_id)
        return self._db.query(q.exists()).scalar()

    def _slugify(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
        return re.sub(r"-{2,}", "-", slug)

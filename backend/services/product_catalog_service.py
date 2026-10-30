"""Validation and persistence for the existing commercial catalog."""
from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.core.tenant_context import TenantContext
from backend.core.catalog_context import catalog_query, assign_catalog_tenant
from backend.models.product import Product, ProductCategory, ProductSize, ProductCrustType
from backend.models.product_promotion import ProductPromotion


DEFAULT_PRODUCT_ICONS = {
    "pizza": "\U0001f355",
    "esfiha": "\U0001f95f",
    "drink": "\U0001f964",
    "other": "\U0001f37d\ufe0f",
    "brinde": "\U0001f381",
}


class ProductCatalogService:
    def __init__(self, db: Session, tenant_context: TenantContext | None):
        self.db = db
        self.context = tenant_context

    def _query(self, model):
        return catalog_query(self.db, model, self.context)

    def product_values(self, values: dict, *, current: Product | None = None, creating: bool = False) -> dict:
        """Validate edited references, preserving untouched legacy classifications."""
        result = dict(values)
        if creating and result.get("icon") is None:
            result["icon"] = DEFAULT_PRODUCT_ICONS.get(result.get("product_type"), DEFAULT_PRODUCT_ICONS["other"])
        if not ({"category", "subcategory"} & result.keys()):
            return result
        category_name = result.get("category", getattr(current, "category", None))
        subcategory_name = result.get("subcategory", getattr(current, "subcategory", None))
        category_name = category_name.strip() or None if category_name else None
        subcategory_name = subcategory_name.strip() or None if subcategory_name else None
        category = None
        if category_name:
            category = self._query(ProductCategory).filter(
                func.lower(ProductCategory.name) == category_name.lower(),
                ProductCategory.parent_id.is_(None),
            ).first()
            if category is None:
                raise HTTPException(422, "Categoria principal nao encontrada neste catalogo.")
        if subcategory_name:
            subcategory = self._query(ProductCategory).filter(
                func.lower(ProductCategory.name) == subcategory_name.lower(),
            ).first()
            if subcategory is None or subcategory.parent_id is None:
                raise HTTPException(422, "Subcategoria nao encontrada neste catalogo.")
            if category is None:
                category = self._query(ProductCategory).filter(
                    ProductCategory.id == subcategory.parent_id,
                    ProductCategory.parent_id.is_(None),
                ).first()
            if category is None or subcategory.parent_id != category.id:
                raise HTTPException(422, "Subcategoria nao pertence a categoria informada.")
            result["subcategory"] = subcategory.name
        elif "subcategory" in result:
            result["subcategory"] = None
        if category is not None:
            result["category"] = category.name
        elif "category" in result:
            result["category"] = None
        return result

    def create(self, body) -> Product:
        product = Product(id=f"prod-{uuid.uuid4().hex[:8]}", **self.product_values(body.model_dump(), creating=True))
        assign_catalog_tenant(product, self.context)
        self.db.add(product)
        self.db.commit()
        self.db.refresh(product)
        return product

    def update(self, product_id: str, body) -> Product:
        product = self._query(Product).filter(Product.id == product_id).first()
        if product is None:
            raise HTTPException(404, "Produto nao encontrado.")
        values = self.product_values(body.model_dump(exclude_unset=True), current=product)
        for key, value in values.items():
            setattr(product, key, value)
        self.db.commit()
        self.db.refresh(product)
        return product

    def validate_promotion(self, product_id: str, body, *, current: ProductPromotion | None = None) -> None:
        values = body.model_dump(exclude_unset=True)
        start_date = values.get("start_date", getattr(current, "start_date", None))
        end_date = values.get("end_date", getattr(current, "end_date", None))
        if start_date is not None and end_date is not None and end_date < start_date:
            raise HTTPException(422, "Fim da promocao deve ser igual ou posterior ao inicio.")
        gift_enabled = values.get("gift_enabled", getattr(current, "gift_enabled", False))
        gift_product_id = values.get("gift_product_id", getattr(current, "gift_product_id", None))
        if gift_enabled:
            gift = self._query(Product).filter(
                Product.id == gift_product_id, Product.active.is_(True),
            ).first() if gift_product_id else None
            if gift is None:
                raise HTTPException(422, "Selecione um brinde ativo deste catalogo.")
        for combination in getattr(body, "combinations", None) or []:
            for option_id, model in (
                (combination.product_size_id, ProductSize),
                (combination.product_crust_type_id, ProductCrustType),
            ):
                if option_id is None:
                    continue
                option = self._query(model).filter(
                    model.id == option_id, model.product_id == product_id, model.active.is_(True),
                ).first()
                if option is None:
                    raise HTTPException(422, "Opcao da promocao deve estar ativa e pertencer ao produto deste catalogo.")


def assert_public_product(product: Product | None, channel: str = "delivery") -> Product:
    """The same visibility boundary applies to public detail and option APIs."""
    if (
        product is None or not product.active or product.product_type == "brinde"
        or not getattr(product, f"visible_{channel}", False)
    ):
        raise HTTPException(404, "Produto nao encontrado neste canal.")
    return product

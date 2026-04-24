import uuid

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.product import Product, ProductCategory
from backend.schemas.product import ProductCategoryCreate, ProductCategoryUpdate


def list_categories(db: Session, active_only: bool = False) -> list[ProductCategory]:
    query = db.query(ProductCategory)
    if active_only:
        query = query.filter(ProductCategory.active == True)  # noqa: E712
    return query.order_by(ProductCategory.sort_order, ProductCategory.name).all()


def create_category(db: Session, body: ProductCategoryCreate) -> ProductCategory:
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Nome da categoria e obrigatorio.")
    existing = db.query(ProductCategory).filter(func.lower(ProductCategory.name) == name.lower()).first()
    if existing:
        raise HTTPException(409, "Categoria ja cadastrada.")

    category = ProductCategory(
        id=f"cat-{uuid.uuid4().hex[:8]}",
        name=name,
        active=body.active,
        sort_order=body.sort_order,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(db: Session, category_id: str, body: ProductCategoryUpdate) -> ProductCategory:
    category = db.query(ProductCategory).filter(ProductCategory.id == category_id).first()
    if not category:
        raise HTTPException(404, "Categoria nao encontrada.")

    changes = body.model_dump(exclude_none=True)
    if "name" in changes:
        name = changes["name"].strip()
        if not name:
            raise HTTPException(400, "Nome da categoria e obrigatorio.")
        existing = (
            db.query(ProductCategory)
            .filter(func.lower(ProductCategory.name) == name.lower(), ProductCategory.id != category_id)
            .first()
        )
        if existing:
            raise HTTPException(409, "Categoria ja cadastrada.")
        changes["name"] = name

    for key, value in changes.items():
        setattr(category, key, value)
    db.commit()
    db.refresh(category)
    return category


def delete_category(db: Session, category_id: str) -> None:
    category = db.query(ProductCategory).filter(ProductCategory.id == category_id).first()
    if not category:
        raise HTTPException(404, "Categoria nao encontrada.")
    in_use = db.query(Product.id).filter(Product.category == category.name).first()
    if in_use:
        raise HTTPException(400, "Categoria em uso por produto. Remova dos produtos antes de excluir.")
    db.delete(category)
    db.commit()

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
    if body.parent_id:
        parent = db.query(ProductCategory).filter(ProductCategory.id == body.parent_id).first()
        if not parent:
            raise HTTPException(404, "Categoria principal nao encontrada.")
    existing = db.query(ProductCategory).filter(func.lower(ProductCategory.name) == name.lower()).first()
    if existing:
        raise HTTPException(409, "Categoria ja cadastrada.")

    category = ProductCategory(
        id=f"cat-{uuid.uuid4().hex[:8]}",
        parent_id=body.parent_id,
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
    if "parent_id" in changes and changes["parent_id"]:
        if changes["parent_id"] == category_id:
            raise HTTPException(400, "Categoria nao pode ser filha dela mesma.")
        parent = db.query(ProductCategory).filter(ProductCategory.id == changes["parent_id"]).first()
        if not parent:
            raise HTTPException(404, "Categoria principal nao encontrada.")
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
    child = db.query(ProductCategory.id).filter(ProductCategory.parent_id == category_id).first()
    if child:
        raise HTTPException(400, "Categoria possui subcategorias. Remova as subcategorias antes de excluir.")
    in_use = db.query(Product.id).filter(
        (Product.category == category.name) | (Product.subcategory == category.name)
    ).first()
    if in_use:
        raise HTTPException(400, "Categoria em uso por produto. Remova dos produtos antes de excluir.")
    db.delete(category)
    db.commit()

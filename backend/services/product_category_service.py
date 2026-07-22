import uuid

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.product import Product, ProductCategory
from backend.schemas.product import ProductCategoryCreate, ProductCategoryUpdate
from backend.core.tenant_context import TenantContext
from backend.core.tenant_ownership import assign_tenant_on_create, identity_catalog_enforcement_enabled, scope_query_to_tenant


def _query(db: Session, model, context: TenantContext | None):
    return scope_query_to_tenant(db.query(model), model, context, enabled=identity_catalog_enforcement_enabled())


def list_categories(db: Session, active_only: bool = False, tenant_context: TenantContext | None = None) -> list[ProductCategory]:
    query = _query(db, ProductCategory, tenant_context)
    if active_only:
        query = query.filter(ProductCategory.active == True)  # noqa: E712
    return query.order_by(ProductCategory.sort_order, ProductCategory.name).all()


def create_category(db: Session, body: ProductCategoryCreate, tenant_context: TenantContext | None = None) -> ProductCategory:
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Nome da categoria e obrigatorio.")
    if body.parent_id:
        parent = _query(db, ProductCategory, tenant_context).filter(ProductCategory.id == body.parent_id).first()
        if not parent:
            raise HTTPException(404, "Categoria principal nao encontrada.")
        if parent.parent_id:
            raise HTTPException(400, "Subcategoria deve pertencer a uma categoria principal.")
    existing = _query(db, ProductCategory, tenant_context).filter(func.lower(ProductCategory.name) == name.lower()).first()
    if existing:
        raise HTTPException(409, "Categoria ja cadastrada.")

    category = ProductCategory(
        id=f"cat-{uuid.uuid4().hex[:8]}",
        parent_id=body.parent_id,
        name=name,
        active=body.active,
        sort_order=body.sort_order,
    )
    assign_tenant_on_create(category, tenant_context, enabled=identity_catalog_enforcement_enabled())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(db: Session, category_id: str, body: ProductCategoryUpdate, tenant_context: TenantContext | None = None) -> ProductCategory:
    category = _query(db, ProductCategory, tenant_context).filter(ProductCategory.id == category_id).first()
    if not category:
        raise HTTPException(404, "Categoria nao encontrada.")

    old_name = category.name
    changes = body.model_dump(exclude_none=True)
    if "parent_id" in changes and changes["parent_id"]:
        if changes["parent_id"] == category_id:
            raise HTTPException(400, "Categoria nao pode ser filha dela mesma.")
        child = _query(db, ProductCategory, tenant_context).filter(ProductCategory.parent_id == category_id).first()
        if child:
            raise HTTPException(400, "Categoria com subcategorias nao pode virar subcategoria.")
        parent = _query(db, ProductCategory, tenant_context).filter(ProductCategory.id == changes["parent_id"]).first()
        if not parent:
            raise HTTPException(404, "Categoria principal nao encontrada.")
        if parent.parent_id:
            raise HTTPException(400, "Subcategoria deve pertencer a uma categoria principal.")
    if "name" in changes:
        name = changes["name"].strip()
        if not name:
            raise HTTPException(400, "Nome da categoria e obrigatorio.")
        existing = (
            _query(db, ProductCategory, tenant_context)
            .filter(func.lower(ProductCategory.name) == name.lower(), ProductCategory.id != category_id)
            .first()
        )
        if existing:
            raise HTTPException(409, "Categoria ja cadastrada.")
        changes["name"] = name

    for key, value in changes.items():
        setattr(category, key, value)
    if "name" in changes and changes["name"] != old_name:
        _query(db, Product, tenant_context).filter(Product.category == old_name).update(
            {Product.category: changes["name"]},
            synchronize_session=False,
        )
        _query(db, Product, tenant_context).filter(Product.subcategory == old_name).update(
            {Product.subcategory: changes["name"]},
            synchronize_session=False,
        )
    db.commit()
    db.refresh(category)
    return category


def delete_category(db: Session, category_id: str, tenant_context: TenantContext | None = None) -> None:
    category = _query(db, ProductCategory, tenant_context).filter(ProductCategory.id == category_id).first()
    if not category:
        raise HTTPException(404, "Categoria nao encontrada.")
    child = _query(db, ProductCategory, tenant_context).filter(ProductCategory.parent_id == category_id).first()
    if child:
        raise HTTPException(400, "Categoria possui subcategorias. Remova as subcategorias antes de excluir.")
    in_use = _query(db, Product, tenant_context).filter(
        (Product.category == category.name) | (Product.subcategory == category.name)
    ).first()
    if in_use:
        raise HTTPException(400, "Categoria em uso por produto. Remova dos produtos antes de excluir.")
    db.delete(category)
    db.commit()

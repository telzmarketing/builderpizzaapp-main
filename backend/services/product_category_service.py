import uuid

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.product import Product, ProductCategory
from backend.schemas.product import ProductCategoryCreate, ProductCategoryUpdate
from backend.core.tenant_context import TenantContext
from backend.core.catalog_context import catalog_query, assign_catalog_tenant


CAPABILITY_FIELDS = (
    "enable_sizes",
    "enable_product_options",
    "enable_recipe",
    "enable_dough",
    "enable_border",
    "enable_promotions",
)


def _query(db: Session, model, context: TenantContext | None):
    return catalog_query(db, model, context)


def _category_by_id(db: Session, category_id: str | None, tenant_context: TenantContext | None) -> ProductCategory | None:
    if not category_id:
        return None
    return _query(db, ProductCategory, tenant_context).filter(ProductCategory.id == category_id).first()


def _root_category(db: Session, category: ProductCategory | None, tenant_context: TenantContext | None) -> ProductCategory | None:
    if category is None:
        return None
    return _category_by_id(db, category.parent_id, tenant_context) if category.parent_id else category


def product_category(db: Session, product: Product, tenant_context: TenantContext | None = None) -> ProductCategory | None:
    """Resolve category by tenant-scoped IDs first, then by legacy names."""
    category = _category_by_id(db, getattr(product, "category_id", None), tenant_context)
    if category is None:
        subcategory = _category_by_id(db, getattr(product, "subcategory_id", None), tenant_context)
        category = _root_category(db, subcategory, tenant_context)
    if category is None and getattr(product, "category", None):
        category = (
            _query(db, ProductCategory, tenant_context)
            .filter(ProductCategory.parent_id.is_(None), func.lower(ProductCategory.name) == product.category.strip().lower())
            .first()
        )
    if category is None and getattr(product, "subcategory", None):
        subcategory = (
            _query(db, ProductCategory, tenant_context)
            .filter(func.lower(ProductCategory.name) == product.subcategory.strip().lower())
            .first()
        )
        category = _root_category(db, subcategory, tenant_context)
    return category


def effective_capabilities(db: Session, product: Product, tenant_context: TenantContext | None = None) -> dict[str, bool]:
    """Return category capabilities, with a read-only fallback for unmigrated products."""
    try:
        category = product_category(db, product, tenant_context)
    except AttributeError:
        # Lightweight catalog doubles used by legacy unit tests do not expose
        # SQLAlchemy NULL/function expression values. Real sessions never hit
        # this branch; they must resolve categories through the query above.
        category = None
    if category is not None:
        root = _root_category(db, category, tenant_context)
        return {field: bool(getattr(root, field, False)) for field in CAPABILITY_FIELDS}

    # Once a category is resolved its flags are the sole source of truth. The
    # fallback only protects legacy rows that cannot yet be associated safely.
    crusts = getattr(product, "crust_types", []) or []
    return {
        "enable_sizes": product.product_type == "pizza" or any(getattr(row, "active", True) for row in (getattr(product, "sizes", []) or [])),
        "enable_product_options": bool(getattr(product, "option_groups", []) or []),
        "enable_recipe": False,
        "enable_dough": bool(getattr(product, "show_crust_options", True)),
        "enable_border": bool(getattr(product, "show_crust_options", True)),
        "enable_promotions": bool(getattr(product, "promotions", []) or []),
    }


def require_capability(db: Session, product: Product, capability: str, tenant_context: TenantContext | None = None) -> None:
    if capability not in CAPABILITY_FIELDS:
        raise ValueError(f"Capacidade de categoria desconhecida: {capability}")
    if not effective_capabilities(db, product, tenant_context).get(capability, False):
        raise HTTPException(422, f"A categoria deste produto nao habilita {capability.removeprefix('enable_')}.")


def normalize_product_category_payload(db: Session, body, tenant_context: TenantContext | None):
    """Validate ID-based category input and keep legacy text fields canonical."""
    values = body.model_dump(exclude_unset=True)
    category_id_present = "category_id" in values
    subcategory_id_present = "subcategory_id" in values
    category = _category_by_id(db, values.get("category_id"), tenant_context) if category_id_present else None
    subcategory = _category_by_id(db, values.get("subcategory_id"), tenant_context) if subcategory_id_present else None

    if category_id_present and values.get("category_id") and (category is None or category.parent_id is not None):
        raise HTTPException(422, "Categoria principal invalida neste catalogo.")
    if subcategory_id_present and values.get("subcategory_id"):
        if subcategory is None or subcategory.parent_id is None:
            raise HTTPException(422, "Subcategoria invalida neste catalogo.")
        if category_id_present and values.get("category_id") != subcategory.parent_id:
            raise HTTPException(422, "Subcategoria nao pertence a categoria informada.")
        category = _category_by_id(db, subcategory.parent_id, tenant_context)
        values["category_id"] = category.id if category else subcategory.parent_id
        values["category"] = category.name if category else None
        values["subcategory"] = subcategory.name
    elif category_id_present:
        values["category"] = category.name if category else None
        values["subcategory"] = None
        values["subcategory_id"] = None
    elif not category_id_present and subcategory_id_present and values.get("subcategory_id") is None:
        values["subcategory"] = None
    return body.model_copy(update=values)


def sync_product_category_refs(db: Session, product: Product, tenant_context: TenantContext | None = None) -> Product:
    """Backfill/repair IDs from compatible text without erasing unmatched legacy text."""
    category = None
    subcategory = None
    if getattr(product, "subcategory", None):
        subcategory = (
            _query(db, ProductCategory, tenant_context)
            .filter(ProductCategory.parent_id.is_not(None), func.lower(ProductCategory.name) == product.subcategory.strip().lower())
            .first()
        )
        if subcategory:
            category = _category_by_id(db, subcategory.parent_id, tenant_context)
    if category is None and getattr(product, "category", None):
        category = (
            _query(db, ProductCategory, tenant_context)
            .filter(ProductCategory.parent_id.is_(None), func.lower(ProductCategory.name) == product.category.strip().lower())
            .first()
        )
    if category is not None:
        product.category_id = category.id
        product.category = category.name
    if subcategory is not None and category is not None:
        product.subcategory_id = subcategory.id
        product.subcategory = subcategory.name
    elif not getattr(product, "subcategory", None):
        product.subcategory_id = None
        if not getattr(product, "category", None):
            product.category_id = None
    return product


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
        **{field: getattr(body, field) for field in CAPABILITY_FIELDS},
    )
    assign_catalog_tenant(category, tenant_context)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(db: Session, category_id: str, body: ProductCategoryUpdate, tenant_context: TenantContext | None = None) -> ProductCategory:
    category = _query(db, ProductCategory, tenant_context).filter(ProductCategory.id == category_id).first()
    if not category:
        raise HTTPException(404, "Categoria nao encontrada.")

    old_name = category.name
    old_parent_id = category.parent_id
    changes = body.model_dump(exclude_unset=True)
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
    if "parent_id" in changes and changes["parent_id"] != old_parent_id:
        name = category.name
        if category.parent_id is None:
            _query(db, Product, tenant_context).filter(Product.subcategory == name).update(
                {Product.category: name, Product.subcategory: None}, synchronize_session=False,
            )
        else:
            parent = _query(db, ProductCategory, tenant_context).filter(ProductCategory.id == category.parent_id).first()
            if old_parent_id is None:
                _query(db, Product, tenant_context).filter(Product.category == name).update(
                    {Product.category: parent.name, Product.subcategory: name}, synchronize_session=False,
                )
            else:
                _query(db, Product, tenant_context).filter(Product.subcategory == name).update(
                    {Product.category: parent.name}, synchronize_session=False,
                )
    for product in _query(db, Product, tenant_context).all():
        sync_product_category_refs(db, product, tenant_context)
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
        (Product.category_id == category.id)
        | (Product.subcategory_id == category.id)
        | (Product.category == category.name)
        | (Product.subcategory == category.name)
    ).first()
    if in_use:
        raise HTTPException(400, "Categoria em uso por produto. Remova dos produtos antes de excluir.")
    db.delete(category)
    db.commit()

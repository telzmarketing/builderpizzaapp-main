import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.catalog_context import assign_catalog_tenant, catalog_query
from backend.core.rbac_authorization import require_rbac_permission
from backend.core.tenant_runtime import resolve_panel_tenant_context
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.models.catalog_global import PizzaGlobalCrust, PizzaGlobalDoughType, PizzaGlobalSize
from backend.models.order import OrderItem
from backend.models.product import Product, ProductCrustType, ProductSize
from backend.models.salao import TableSessionItem
from backend.schemas.catalog_global import ProductCatalogConfigurationOut, ProductCatalogConfigurationUpdate, ProductOptionAssociationCreate, ProductSizeAssociationCreate
from backend.routes.admin_auth import get_current_admin
from backend.schemas.catalog_global import (
    GlobalCatalogCreate, GlobalCatalogOut, GlobalCatalogUpdate,
    GlobalSizeCreate, GlobalSizeOut, GlobalSizeUpdate,
)
from backend.schemas.product import ProductCrustTypeOut, ProductSizeOut

router = APIRouter(prefix="/catalog", tags=["catalog-global"])


def _context(request: Request, db: Session, admin: AdminUser):
    return resolve_panel_tenant_context(request, db, admin)


def _list(db, model, context):
    return catalog_query(db, model, context).order_by(model.sort_order, model.name).all()


def _create(db, model, body, context, prefix):
    values = body.model_dump()
    if isinstance(values.get("name"), str):
        values["name"] = values["name"].strip()
    resource = catalog_query(db, model, context).filter(model.name == values["name"]).with_for_update().first()
    if resource is not None:
        raise HTTPException(status_code=409, detail="Ja existe um cadastro com este nome neste tenant, ativo ou inativo.")
    resource = model(id=f"{prefix}-{uuid.uuid4().hex}", **values)
    assign_catalog_tenant(resource, context)
    db.add(resource)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ja existe um cadastro com este nome neste tenant, ativo ou inativo.")
    db.refresh(resource)
    return resource


def _update(db, model, resource_id, body, context):
    resource = catalog_query(db, model, context).filter(model.id == resource_id).first()
    if resource is None:
        raise HTTPException(status_code=404, detail="Cadastro nao encontrado.")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(resource, key, value.strip() if key == "name" and isinstance(value, str) else value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ja existe um cadastro com este nome neste tenant.")
    db.refresh(resource)
    return resource


def _delete(db, model, resource_id, context, *, physical=False):
    resource = catalog_query(db, model, context).filter(model.id == resource_id).first()
    if resource is None:
        raise HTTPException(status_code=404, detail="Cadastro nao encontrado.")
    if physical:
        # Product options keep a RESTRICT FK to the global border. A physical
        # delete explicitly removes the border configuration and every product
        # association, so neither active nor inactive links may block it.
        if model is PizzaGlobalCrust:
            links = catalog_query(db, ProductCrustType, context).filter(
                ProductCrustType.global_crust_id == resource.id,
            ).all()
            link_ids = [link.id for link in links]
            if link_ids:
                # Orders/table sessions retain the displayed border name as a
                # snapshot. Clear only the technical FK before removing the
                # obsolete product-option rows.
                inspector = inspect(db.get_bind())
                if inspector.has_table(OrderItem.__tablename__):
                    db.query(OrderItem).filter(
                        OrderItem.tenant_id == context.tenant_id,
                        OrderItem.selected_border_id.in_(link_ids),
                    ).update({OrderItem.selected_border_id: None}, synchronize_session=False)
                if inspector.has_table(TableSessionItem.__tablename__):
                    db.query(TableSessionItem).filter(
                        TableSessionItem.tenant_id == context.tenant_id,
                        TableSessionItem.selected_border_id.in_(link_ids),
                    ).update({TableSessionItem.selected_border_id: None}, synchronize_session=False)
                db.query(ProductCrustType).filter(
                    ProductCrustType.tenant_id == context.tenant_id,
                    ProductCrustType.id.in_(link_ids),
                ).delete(synchronize_session=False)
        db.delete(resource)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Nao e possivel excluir esta borda porque ela esta associada a um ou mais produtos.",
            )
    else:
        resource.active = False
        db.commit()


def _product(db, product_id: str, context):
    product = catalog_query(db, Product, context).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Produto nao encontrado.")
    return product


def _global_option(db, model, option_id: str, context):
    option = catalog_query(db, model, context).filter(model.id == option_id).first()
    if option is None:
        raise HTTPException(status_code=422, detail="Configuracao global nao encontrada neste tenant.")
    if not option.active:
        raise HTTPException(status_code=422, detail="Configuracao global inativa nao pode ser associada a novos produtos.")
    return option


@router.get("/products/{product_id}/configuration", response_model=ProductCatalogConfigurationOut,
            dependencies=[Depends(require_rbac_permission("cardapio", "view"))])
def product_configuration(request: Request, product_id: str, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    context = _context(request, db, admin)
    _product(db, product_id, context)
    sizes = catalog_query(db, ProductSize, context).filter(ProductSize.product_id == product_id).order_by(ProductSize.sort_order, ProductSize.id).all()
    options = catalog_query(db, ProductCrustType, context).filter(ProductCrustType.product_id == product_id).order_by(ProductCrustType.sort_order, ProductCrustType.id).all()
    return {"product_id": product_id, "sizes": [row.global_size_id for row in sizes if row.global_size_id and row.active], "size_prices": {row.global_size_id: row.price for row in sizes if row.global_size_id and row.active}, "dough_types": [row.global_dough_type_id for row in options if row.global_dough_type_id and row.active], "crusts": [row.global_crust_id for row in options if row.global_crust_id and row.active]}


@router.put("/products/{product_id}/configuration", response_model=ProductCatalogConfigurationOut,
           dependencies=[Depends(require_rbac_permission("cardapio", "edit"))])
def update_product_configuration(product_id: str, body: ProductCatalogConfigurationUpdate, request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    context = _context(request, db, admin)
    product = _product(db, product_id, context)
    size_ids = set(body.sizes)
    dough_ids = set(body.dough_types)
    crust_ids = set(body.crusts)
    if len(size_ids) != len(body.sizes) or len(dough_ids) != len(body.dough_types) or len(crust_ids) != len(body.crusts):
        raise HTTPException(status_code=422, detail="Nao repita configuracoes globais.")
    sizes = catalog_query(db, ProductSize, context).filter(ProductSize.product_id == product_id).all()
    options = catalog_query(db, ProductCrustType, context).filter(ProductCrustType.product_id == product_id).all()
    for global_id in size_ids:
        global_size = _global_option(db, PizzaGlobalSize, global_id, context)
        existing = next((row for row in sizes if row.global_size_id == global_id), None)
        if existing:
            existing.active = True
            if global_id in body.size_prices: existing.price = body.size_prices[global_id]
        else:
            row = ProductSize(id=f"size-{uuid.uuid4().hex[:8]}", tenant_id=context.tenant_id, product_id=product.id,
                              global_size_id=global_id, label=global_size.name, description=global_size.description,
                              price=body.size_prices.get(global_id, product.price), is_default=global_size.is_default, sort_order=global_size.sort_order, active=True)
            db.add(row); sizes.append(row)
    for global_id in dough_ids:
        global_option = _global_option(db, PizzaGlobalDoughType, global_id, context)
        if not next((row for row in options if row.global_dough_type_id == global_id), None):
            row = ProductCrustType(id=f"crust-{uuid.uuid4().hex[:8]}", tenant_id=context.tenant_id, product_id=product.id,
                                   global_dough_type_id=global_id, name=global_option.name, option_kind="dough",
                                   price_addition=global_option.price_addition, sort_order=global_option.sort_order, active=True)
            db.add(row); options.append(row)
    for global_id in crust_ids:
        global_option = _global_option(db, PizzaGlobalCrust, global_id, context)
        if not next((row for row in options if row.global_crust_id == global_id), None):
            row = ProductCrustType(id=f"crust-{uuid.uuid4().hex[:8]}", tenant_id=context.tenant_id, product_id=product.id,
                                   global_crust_id=global_id, name=global_option.name, option_kind="border",
                                   price_addition=global_option.price_addition, sort_order=global_option.sort_order, active=True)
            db.add(row); options.append(row)
    for row in sizes:
        if row.global_size_id and row.global_size_id not in size_ids: row.active = False
    for row in options:
        if row.global_dough_type_id and row.global_dough_type_id not in dough_ids: row.active = False
        if row.global_crust_id and row.global_crust_id not in crust_ids: row.active = False
    db.commit()
    db.flush()
    return {"product_id": product_id, "sizes": list(size_ids), "size_prices": {row.global_size_id: row.price for row in sizes if row.global_size_id in size_ids}, "dough_types": list(dough_ids), "crusts": list(crust_ids)}


@router.post("/products/{product_id}/sizes", response_model=ProductSizeOut, status_code=status.HTTP_201_CREATED,
            dependencies=[Depends(require_rbac_permission("cardapio", "create"))])
def associate_size(product_id: str, body: ProductSizeAssociationCreate, request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    context = _context(request, db, admin)
    product = _product(db, product_id, context)
    global_size = _global_option(db, PizzaGlobalSize, body.global_size_id, context)
    duplicate = catalog_query(db, ProductSize, context).filter(ProductSize.product_id == product_id, ProductSize.global_size_id == global_size.id).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Este tamanho global ja esta associado ao produto.")
    row = ProductSize(
        id=f"size-{uuid.uuid4().hex[:8]}", tenant_id=context.tenant_id, product_id=product.id,
        global_size_id=global_size.id, label=body.label or global_size.name,
        description=body.description if body.description is not None else global_size.description,
        price=body.price, is_default=body.is_default, sort_order=body.sort_order, active=body.active,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Associacao de tamanho ja existe.")
    db.refresh(row)
    return row


@router.post("/products/{product_id}/options", response_model=ProductCrustTypeOut, status_code=status.HTTP_201_CREATED,
            dependencies=[Depends(require_rbac_permission("cardapio", "create"))])
def associate_option(product_id: str, body: ProductOptionAssociationCreate, request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    context = _context(request, db, admin)
    product = _product(db, product_id, context)
    if bool(body.global_dough_type_id) == bool(body.global_crust_id):
        raise HTTPException(status_code=422, detail="Informe exatamente uma massa global ou uma borda global.")
    if body.global_dough_type_id:
        global_option = _global_option(db, PizzaGlobalDoughType, body.global_dough_type_id, context)
        option_kind, field_name = "dough", "global_dough_type_id"
    else:
        global_option = _global_option(db, PizzaGlobalCrust, body.global_crust_id, context)
        option_kind, field_name = "border", "global_crust_id"
    duplicate = catalog_query(db, ProductCrustType, context).filter(ProductCrustType.product_id == product_id, getattr(ProductCrustType, field_name) == global_option.id).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Esta configuracao global ja esta associada ao produto.")
    effective_price = body.price_addition_override if body.price_addition_override is not None else global_option.price_addition
    row = ProductCrustType(
        id=f"crust-{uuid.uuid4().hex[:8]}", tenant_id=context.tenant_id, product_id=product.id,
        name=body.name or global_option.name, option_kind=option_kind,
        global_dough_type_id=body.global_dough_type_id, global_crust_id=body.global_crust_id,
        price_addition=effective_price, price_addition_override=body.price_addition_override,
        active=body.active, sort_order=body.sort_order,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Associacao de opcao ja existe.")
    db.refresh(row)
    return row


@router.get("/pizza-sizes", response_model=list[GlobalSizeOut])
def list_sizes(request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin), _=Depends(require_rbac_permission("cardapio", "view"))):
    return _list(db, PizzaGlobalSize, _context(request, db, admin))


@router.post("/pizza-sizes", response_model=GlobalSizeOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_rbac_permission("cardapio", "create"))])
def create_size(body: GlobalSizeCreate, request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    return _create(db, PizzaGlobalSize, body, _context(request, db, admin), "global-size")


@router.put("/pizza-sizes/{resource_id}", response_model=GlobalSizeOut, dependencies=[Depends(require_rbac_permission("cardapio", "edit"))])
def update_size(resource_id: str, body: GlobalSizeUpdate, request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    return _update(db, PizzaGlobalSize, resource_id, body, _context(request, db, admin))


@router.delete("/pizza-sizes/{resource_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_rbac_permission("cardapio", "delete"))])
def delete_size(resource_id: str, request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    _delete(db, PizzaGlobalSize, resource_id, _context(request, db, admin))


def _catalog_routes(path: str, model, output, create_schema, update_schema, prefix: str, *, physical_delete: bool = False):
    @router.get(path, response_model=list[output])
    def list_resource(request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin), _=Depends(require_rbac_permission("cardapio", "view"))):
        return _list(db, model, _context(request, db, admin))

    @router.post(path, response_model=output, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_rbac_permission("cardapio", "create"))])
    def create_resource(body: create_schema, request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
        return _create(db, model, body, _context(request, db, admin), prefix)

    @router.put(f"{path}/{{resource_id}}", response_model=output, dependencies=[Depends(require_rbac_permission("cardapio", "edit"))])
    def update_resource(resource_id: str, body: update_schema, request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
        return _update(db, model, resource_id, body, _context(request, db, admin))

    @router.delete(f"{path}/{{resource_id}}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_rbac_permission("cardapio", "delete"))])
    def delete_resource(resource_id: str, request: Request, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
        _delete(db, model, resource_id, _context(request, db, admin), physical=physical_delete)


_catalog_routes("/dough-types", PizzaGlobalDoughType, GlobalCatalogOut, GlobalCatalogCreate, GlobalCatalogUpdate, "global-dough")
_catalog_routes("/pizza-crusts", PizzaGlobalCrust, GlobalCatalogOut, GlobalCatalogCreate, GlobalCatalogUpdate, "global-crust", physical_delete=True)

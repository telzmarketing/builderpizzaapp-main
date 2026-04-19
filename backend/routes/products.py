import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.product import Product, MultiFlavorsConfig, ProductSize, ProductCrustType, ProductDrinkVariant
from backend.schemas.product import (
    ProductCreate, ProductUpdate, ProductOut,
    MultiFlavorsConfigUpdate, MultiFlavorsConfigOut,
    ProductSizeCreate, ProductSizeUpdate, ProductSizeOut,
    ProductCrustTypeCreate, ProductCrustTypeUpdate, ProductCrustTypeOut,
    ProductDrinkVariantCreate, ProductDrinkVariantUpdate, ProductDrinkVariantOut,
)
from backend.routes.admin_auth import get_current_admin

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(active_only: bool = True, db: Session = Depends(get_db)):
    q = db.query(Product)
    if active_only:
        q = q.filter(Product.active == True)  # noqa: E712
    return q.order_by(Product.name).all()


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Produto não encontrado.")
    return product


@router.post("", response_model=ProductOut, status_code=201)
def create_product(body: ProductCreate, db: Session = Depends(get_db)):
    product = Product(id=f"prod-{uuid.uuid4().hex[:8]}", **body.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/{product_id}", response_model=ProductOut)
def update_product(product_id: str, body: ProductUpdate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Produto não encontrado.")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Produto não encontrado.")
    db.delete(product)
    db.commit()


# ── Product Sizes ─────────────────────────────────────────────────────────────

@router.get("/{product_id}/sizes", response_model=list[ProductSizeOut])
def list_sizes(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Produto não encontrado.")
    return db.query(ProductSize).filter(ProductSize.product_id == product_id).order_by(ProductSize.sort_order).all()


@router.post("/{product_id}/sizes", response_model=ProductSizeOut, status_code=201)
def create_size(product_id: str, body: ProductSizeCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Produto não encontrado.")
    size = ProductSize(id=f"size-{uuid.uuid4().hex[:8]}", product_id=product_id, **body.model_dump())
    db.add(size)
    db.commit()
    db.refresh(size)
    return size


@router.put("/{product_id}/sizes/{size_id}", response_model=ProductSizeOut)
def update_size(product_id: str, size_id: str, body: ProductSizeUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    size = db.query(ProductSize).filter(ProductSize.id == size_id, ProductSize.product_id == product_id).first()
    if not size:
        raise HTTPException(404, "Tamanho não encontrado.")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(size, key, value)
    db.commit()
    db.refresh(size)
    return size


@router.delete("/{product_id}/sizes/{size_id}", status_code=204)
def delete_size(product_id: str, size_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    size = db.query(ProductSize).filter(ProductSize.id == size_id, ProductSize.product_id == product_id).first()
    if not size:
        raise HTTPException(404, "Tamanho não encontrado.")
    db.delete(size)
    db.commit()


# ── Pizza Crust Types ─────────────────────────────────────────────────────────

@router.get("/{product_id}/crusts", response_model=list[ProductCrustTypeOut])
def list_crusts(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Produto não encontrado.")
    return (
        db.query(ProductCrustType)
        .filter(ProductCrustType.product_id == product_id)
        .order_by(ProductCrustType.sort_order)
        .all()
    )


@router.post("/{product_id}/crusts", response_model=ProductCrustTypeOut, status_code=201)
def create_crust(product_id: str, body: ProductCrustTypeCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Produto não encontrado.")
    crust = ProductCrustType(id=f"crust-{uuid.uuid4().hex[:8]}", product_id=product_id, **body.model_dump())
    db.add(crust)
    db.commit()
    db.refresh(crust)
    return crust


@router.put("/{product_id}/crusts/{crust_id}", response_model=ProductCrustTypeOut)
def update_crust(product_id: str, crust_id: str, body: ProductCrustTypeUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    crust = db.query(ProductCrustType).filter(ProductCrustType.id == crust_id, ProductCrustType.product_id == product_id).first()
    if not crust:
        raise HTTPException(404, "Tipo de massa não encontrado.")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(crust, key, value)
    db.commit()
    db.refresh(crust)
    return crust


@router.delete("/{product_id}/crusts/{crust_id}", status_code=204)
def delete_crust(product_id: str, crust_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    crust = db.query(ProductCrustType).filter(ProductCrustType.id == crust_id, ProductCrustType.product_id == product_id).first()
    if not crust:
        raise HTTPException(404, "Tipo de massa não encontrado.")
    db.delete(crust)
    db.commit()


# ── Drink Variants ────────────────────────────────────────────────────────────

@router.get("/{product_id}/drink-variants", response_model=list[ProductDrinkVariantOut])
def list_drink_variants(product_id: str, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Produto não encontrado.")
    return (
        db.query(ProductDrinkVariant)
        .filter(ProductDrinkVariant.product_id == product_id)
        .order_by(ProductDrinkVariant.sort_order)
        .all()
    )


@router.post("/{product_id}/drink-variants", response_model=ProductDrinkVariantOut, status_code=201)
def create_drink_variant(product_id: str, body: ProductDrinkVariantCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Produto não encontrado.")
    variant = ProductDrinkVariant(id=f"dvar-{uuid.uuid4().hex[:8]}", product_id=product_id, **body.model_dump())
    db.add(variant)
    db.commit()
    db.refresh(variant)
    return variant


@router.put("/{product_id}/drink-variants/{variant_id}", response_model=ProductDrinkVariantOut)
def update_drink_variant(product_id: str, variant_id: str, body: ProductDrinkVariantUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    variant = db.query(ProductDrinkVariant).filter(ProductDrinkVariant.id == variant_id, ProductDrinkVariant.product_id == product_id).first()
    if not variant:
        raise HTTPException(404, "Variante não encontrada.")
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(variant, key, value)
    db.commit()
    db.refresh(variant)
    return variant


@router.delete("/{product_id}/drink-variants/{variant_id}", status_code=204)
def delete_drink_variant(product_id: str, variant_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    variant = db.query(ProductDrinkVariant).filter(ProductDrinkVariant.id == variant_id, ProductDrinkVariant.product_id == product_id).first()
    if not variant:
        raise HTTPException(404, "Variante não encontrada.")
    db.delete(variant)
    db.commit()


# ── Multi-flavor config ───────────────────────────────────────────────────────

@router.get("/config/multi-flavors", response_model=MultiFlavorsConfigOut)
def get_multi_flavors_config(db: Session = Depends(get_db)):
    config = db.query(MultiFlavorsConfig).filter(MultiFlavorsConfig.id == "default").first()
    if not config:
        config = MultiFlavorsConfig(id="default")
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.patch("/config/multi-flavors", response_model=MultiFlavorsConfigOut)
def update_multi_flavors_config(body: MultiFlavorsConfigUpdate, db: Session = Depends(get_db)):
    config = db.query(MultiFlavorsConfig).filter(MultiFlavorsConfig.id == "default").first()
    if not config:
        config = MultiFlavorsConfig(id="default")
        db.add(config)
        db.flush()
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(config, key, value)
    db.commit()
    db.refresh(config)
    return config

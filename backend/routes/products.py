import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.product import Product, MultiFlavorsConfig
from backend.schemas.product import (
    ProductCreate, ProductUpdate, ProductOut,
    MultiFlavorsConfigUpdate, MultiFlavorsConfigOut,
)

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

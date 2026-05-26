import json
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from backend.database import get_db
from backend.models.admin import AdminUser
from backend.models.order import Order, OrderItem, OrderStatus
from backend.models.product import Product, BestSellerConfig, MultiFlavorsConfig, ProductSize, ProductCrustType, ProductDrinkVariant
from backend.models.product_promotion import ProductPromotion, ProductPromotionCombination
from backend.schemas.product import (
    ProductCreate, ProductUpdate, ProductOut,
    MultiFlavorsConfigUpdate, MultiFlavorsConfigOut,
    BestSellerConfigOut, BestSellerConfigUpdate,
    ProductCategoryCreate, ProductCategoryUpdate, ProductCategoryOut,
    ProductSizeCreate, ProductSizeUpdate, ProductSizeOut,
    ProductCrustTypeCreate, ProductCrustTypeUpdate, ProductCrustTypeOut,
    ProductDrinkVariantCreate, ProductDrinkVariantUpdate, ProductDrinkVariantOut,
    ProductPromotionCreate, ProductPromotionUpdate, ProductPromotionOut,
    ProductPriceQuoteOut,
)
from backend.routes.admin_auth import get_current_admin
from backend.services import product_category_service
from backend.services.product_pricing_service import ProductPricingService
from backend.services.promotion_landing_service import PromotionLandingService

_VALID_BADGE_STATUSES = [
    OrderStatus.paid, OrderStatus.pago, OrderStatus.preparing,
    OrderStatus.ready_for_pickup, OrderStatus.on_the_way, OrderStatus.delivered,
]


def _get_best_seller_badge_ids(db: Session) -> set[str]:
    """Returns IDs of products that qualify for the automatic best-seller badge."""
    config = db.query(BestSellerConfig).filter(BestSellerConfig.id == "default").first()
    if not config:
        return set()
    q = (
        db.query(OrderItem.product_id, func.sum(OrderItem.quantity).label("total"))
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.status.in_(_VALID_BADGE_STATUSES))
    )
    if config.period_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=config.period_days)
        q = q.filter(Order.created_at >= cutoff)
    top = (
        q.group_by(OrderItem.product_id)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(config.top_count)
        .all()
    )
    return {row.product_id for row in top}

router = APIRouter(prefix="/products", tags=["products"])


def _require_admin(request: Request, db: Session) -> AdminUser:
    return get_current_admin(
        authorization=request.headers.get("authorization"),
        db=db,
    )


def _ensure_weekdays(days: list[int] | None) -> list[int]:
    if not days:
        return []
    clean = sorted(set(int(day) for day in days))
    if any(day < 0 or day > 6 for day in clean):
        raise HTTPException(400, "Dias da semana devem estar entre 0 (segunda) e 6 (domingo).")
    return clean


def _promotion_payload(promotion: ProductPromotion) -> dict:
    try:
        weekdays = json.loads(promotion.valid_weekdays or "[]")
    except Exception:
        weekdays = []
    return {
        "id": promotion.id,
        "product_id": promotion.product_id,
        "name": promotion.name,
        "active": promotion.active,
        "valid_weekdays": weekdays,
        "start_time": promotion.start_time,
        "end_time": promotion.end_time,
        "start_date": promotion.start_date,
        "end_date": promotion.end_date,
        "discount_type": promotion.discount_type,
        "default_value": promotion.default_value,
        "free_shipping": bool(promotion.free_shipping),
        "gift_enabled": bool(promotion.gift_enabled),
        "gift_product_id": promotion.gift_product_id,
        "gift_quantity": promotion.gift_quantity or 1,
        "blocks_other_coupons": bool(promotion.blocks_other_coupons),
        "timezone": promotion.timezone,
        "created_at": promotion.created_at,
        "updated_at": promotion.updated_at,
        "combinations": promotion.combinations,
    }


def _add_promotion_combinations(
    db: Session,
    promotion: ProductPromotion,
    combinations,
) -> None:
    for combo in combinations:
        db.add(ProductPromotionCombination(
            id=f"ppc-{uuid.uuid4().hex[:10]}",
            promotion_id=promotion.id,
            product_size_id=combo.product_size_id,
            product_crust_type_id=combo.product_crust_type_id,
            active=combo.active,
            promotional_value=combo.promotional_value,
        ))


def _product_payload(product: Product, db: Session, auto_badge_ids: set[str] | None = None) -> dict:
    payload = ProductOut.model_validate(product).model_dump()
    default_size = next((size for size in product.sizes if size.active and size.is_default), None)
    if not default_size:
        default_size = next((size for size in product.sizes if size.active), None)
    pricing = ProductPricingService(db)
    quote = pricing.calculate(product=product, size=default_size)
    active_sizes = [size for size in product.sizes if size.active] or [None]
    active_crusts = [crust for crust in product.crust_types if crust.active]
    crust_options = active_crusts or [None]
    promotion_quotes = [
        candidate
        for size in active_sizes
        for crust in crust_options
        for candidate in [pricing.calculate(product=product, size=size, crust=crust)]
        if candidate.promotion_applied
    ]
    if promotion_quotes:
        quote = min(promotion_quotes, key=lambda candidate: candidate.final_price)
    try:
        landing = PromotionLandingService(db).active_landing_for_product(product) if promotion_quotes else None
    except Exception:
        landing = None

    mode = product.best_seller_badge_mode or "off"
    if mode == "manual":
        show_badge = True
    elif mode == "auto":
        badge_set = auto_badge_ids if auto_badge_ids is not None else _get_best_seller_badge_ids(db)
        show_badge = product.id in badge_set
    else:
        show_badge = False

    payload.update({
        "standard_price": quote.standard_price,
        "current_price": quote.final_price,
        "promotion_applied": quote.promotion_applied,
        "promotion_id": quote.promotion_id,
        "promotion_name": quote.promotion_name,
        "promotion_discount": quote.discount_amount,
        "promotion_free_shipping": quote.free_shipping,
        "promotion_gift_enabled": quote.gift_enabled,
        "promotion_gift_product_id": quote.gift_product_id,
        "promotion_gift_quantity": quote.gift_quantity,
        "promotion_gift_name": quote.gift_name,
        "promotion_gift_icon": quote.gift_icon,
        "promotion_blocks_other_coupons": quote.blocks_other_coupons,
        "promotion_landing_page_id": landing.id if landing else None,
        "promotion_landing_slug": landing.slug if landing else None,
        "promotion_landing_url": f"/promocao/{landing.slug}" if landing else None,
        "show_best_seller_badge": show_badge,
    })
    return payload


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
def update_multi_flavors_config(body: MultiFlavorsConfigUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
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


@router.get("/categories", response_model=list[ProductCategoryOut])
def list_categories(
    request: Request,
    active_only: bool = False,
    db: Session = Depends(get_db),
):
    if not active_only:
        _require_admin(request, db)
    return product_category_service.list_categories(db, active_only=active_only)


@router.post("/categories", response_model=ProductCategoryOut, status_code=201)
def create_category(body: ProductCategoryCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return product_category_service.create_category(db, body)


@router.put("/categories/{category_id}", response_model=ProductCategoryOut)
def update_category(category_id: str, body: ProductCategoryUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return product_category_service.update_category(db, category_id, body)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    product_category_service.delete_category(db, category_id)


@router.get("/config/best-seller", response_model=BestSellerConfigOut)
def get_best_seller_config(db: Session = Depends(get_db)):
    config = db.query(BestSellerConfig).filter(BestSellerConfig.id == "default").first()
    if not config:
        config = BestSellerConfig(id="default")
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.patch("/config/best-seller", response_model=BestSellerConfigOut)
def update_best_seller_config(
    body: BestSellerConfigUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    config = db.query(BestSellerConfig).filter(BestSellerConfig.id == "default").first()
    if not config:
        config = BestSellerConfig(id="default")
        db.add(config)
        db.flush()
    for key, value in body.model_dump(exclude_none=True).items():
        setattr(config, key, value)
    db.commit()
    db.refresh(config)
    return config


@router.get("", response_model=list[ProductOut])
def list_products(
    request: Request,
    active_only: bool = True,
    product_type: str | None = Query(default=None),
    channel: str | None = Query(default=None, pattern="^(delivery|dine_in)$"),
    db: Session = Depends(get_db),
):
    if not active_only or product_type == "brinde":
        _require_admin(request, db)
    q = db.query(Product).options(
        selectinload(Product.sizes),
        selectinload(Product.crust_types),
        selectinload(Product.drink_variants),
        selectinload(Product.promotions).selectinload(ProductPromotion.combinations),
        selectinload(Product.promotions).selectinload(ProductPromotion.gift_product),
    )
    if active_only:
        q = q.filter(Product.active == True)  # noqa: E712
    if product_type:
        q = q.filter(Product.product_type == product_type)
    elif active_only:
        q = q.filter(or_(Product.product_type == None, Product.product_type != "brinde"))  # noqa: E711
    if channel == "delivery":
        q = q.filter(Product.visible_delivery == True)  # noqa: E712
    elif channel == "dine_in":
        q = q.filter(Product.visible_dine_in == True)  # noqa: E712
    products = q.order_by(Product.name).all()
    auto_badge_ids = (
        _get_best_seller_badge_ids(db)
        if any((product.best_seller_badge_mode or "off") == "auto" for product in products)
        else set()
    )
    return [_product_payload(product, db, auto_badge_ids) for product in products]


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: str, request: Request, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Produto não encontrado.")
    if not product.active:
        _require_admin(request, db)
    return _product_payload(product, db)


@router.get("/{product_id}/price", response_model=ProductPriceQuoteOut)
def quote_product_price(
    product_id: str,
    size_id: str | None = Query(default=None),
    crust_id: str | None = Query(default=None),
    flavor_count: int = Query(default=1, ge=1, le=3),
    flavor_ids: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id, Product.active == True).first()  # noqa: E712
    if not product:
        raise HTTPException(404, "Produto nao encontrado.")

    size = None
    if size_id:
        size = (
            db.query(ProductSize)
            .filter(ProductSize.id == size_id, ProductSize.product_id == product_id, ProductSize.active == True)  # noqa: E712
            .first()
        )
        if not size:
            raise HTTPException(404, "Tamanho nao encontrado.")

    crust = None
    if crust_id:
        crust = (
            db.query(ProductCrustType)
            .filter(ProductCrustType.id == crust_id, ProductCrustType.product_id == product_id, ProductCrustType.active == True)  # noqa: E712
            .first()
        )
        if not crust:
            raise HTTPException(404, "Tipo de massa nao encontrado.")

    result = ProductPricingService(db).calculate(
        product=product,
        size=size,
        crust=crust,
        flavor_count=flavor_count,
        flavor_product_ids=flavor_ids,
    )
    return {
        "standard_price": result.standard_price,
        "final_price": result.final_price,
        "promotion_applied": result.promotion_applied,
        "promotion_id": result.promotion_id,
        "promotion_name": result.promotion_name,
        "discount_amount": result.discount_amount,
        "discount_type": result.discount_type,
        "free_shipping": result.free_shipping,
        "gift_enabled": result.gift_enabled,
        "gift_product_id": result.gift_product_id,
        "gift_quantity": result.gift_quantity,
        "gift_name": result.gift_name,
        "gift_icon": result.gift_icon,
        "blocks_other_coupons": result.blocks_other_coupons,
        "promotion_blocked": result.promotion_blocked,
        "promotion_block_reason": result.promotion_block_reason,
    }


@router.get("/{product_id}/promotions", response_model=list[ProductPromotionOut])
def list_product_promotions(product_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Produto nao encontrado.")
    promotions = (
        db.query(ProductPromotion)
        .filter(ProductPromotion.product_id == product_id)
        .order_by(ProductPromotion.created_at.desc())
        .all()
    )
    return [_promotion_payload(promotion) for promotion in promotions]


@router.post("/{product_id}/promotions", response_model=ProductPromotionOut, status_code=201)
def create_product_promotion(product_id: str, body: ProductPromotionCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Produto nao encontrado.")
    promotion = ProductPromotion(
        id=f"pp-{uuid.uuid4().hex[:10]}",
        product_id=product_id,
        name=body.name,
        active=body.active,
        valid_weekdays=json.dumps(_ensure_weekdays(body.valid_weekdays)),
        start_time=body.start_time,
        end_time=body.end_time,
        start_date=body.start_date,
        end_date=body.end_date,
        discount_type=body.discount_type,
        default_value=body.default_value,
        free_shipping=body.free_shipping,
        gift_enabled=body.gift_enabled,
        gift_product_id=body.gift_product_id,
        gift_quantity=body.gift_quantity,
        blocks_other_coupons=body.blocks_other_coupons,
        timezone=body.timezone,
    )
    db.add(promotion)
    db.flush()
    _add_promotion_combinations(db, promotion, body.combinations)
    db.commit()
    db.refresh(promotion)
    return _promotion_payload(promotion)


@router.put("/{product_id}/promotions/{promotion_id}", response_model=ProductPromotionOut)
def update_product_promotion(product_id: str, promotion_id: str, body: ProductPromotionUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    promotion = (
        db.query(ProductPromotion)
        .filter(ProductPromotion.id == promotion_id, ProductPromotion.product_id == product_id)
        .first()
    )
    if not promotion:
        raise HTTPException(404, "Promocao nao encontrada.")

    values = body.model_dump(exclude_unset=True, exclude={"combinations"})
    if "valid_weekdays" in values:
        promotion.valid_weekdays = json.dumps(_ensure_weekdays(values.pop("valid_weekdays")))
    for key, value in values.items():
        setattr(promotion, key, value)

    if body.combinations is not None:
        db.query(ProductPromotionCombination).filter(
            ProductPromotionCombination.promotion_id == promotion.id
        ).delete(synchronize_session=False)
        _add_promotion_combinations(db, promotion, body.combinations)

    db.commit()
    db.refresh(promotion)
    return _promotion_payload(promotion)


@router.delete("/{product_id}/promotions/{promotion_id}", status_code=204)
def delete_product_promotion(product_id: str, promotion_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    promotion = (
        db.query(ProductPromotion)
        .filter(ProductPromotion.id == promotion_id, ProductPromotion.product_id == product_id)
        .first()
    )
    if not promotion:
        raise HTTPException(404, "Promocao nao encontrada.")
    db.delete(promotion)
    db.commit()


@router.post("", response_model=ProductOut, status_code=201)
def create_product(body: ProductCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    product = Product(id=f"prod-{uuid.uuid4().hex[:8]}", **body.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return _product_payload(product, db)


@router.put("/{product_id}", response_model=ProductOut)
def update_product(product_id: str, body: ProductUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Produto não encontrado.")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return _product_payload(product, db)


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Produto não encontrado.")
    product.active = False
    product.updated_at = datetime.now(timezone.utc)
    db.commit()


@router.get("/{product_id}/sizes", response_model=list[ProductSizeOut])
def list_sizes(
    product_id: str,
    request: Request,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Produto não encontrado.")
    if not active_only or not product.active:
        _require_admin(request, db)
    q = db.query(ProductSize).filter(ProductSize.product_id == product_id)
    if active_only:
        q = q.filter(ProductSize.active == True)  # noqa: E712
    return q.order_by(ProductSize.sort_order).all()


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


@router.get("/{product_id}/crusts", response_model=list[ProductCrustTypeOut])
def list_crusts(
    product_id: str,
    request: Request,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Produto não encontrado.")
    if not active_only or not product.active:
        _require_admin(request, db)
    q = db.query(ProductCrustType).filter(ProductCrustType.product_id == product_id)
    if active_only:
        q = q.filter(ProductCrustType.active == True)  # noqa: E712
    return q.order_by(ProductCrustType.sort_order).all()


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


@router.get("/{product_id}/drink-variants", response_model=list[ProductDrinkVariantOut])
def list_drink_variants(
    product_id: str,
    request: Request,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Produto não encontrado.")
    if not active_only or not product.active:
        _require_admin(request, db)
    q = db.query(ProductDrinkVariant).filter(ProductDrinkVariant.product_id == product_id)
    if active_only:
        q = q.filter(ProductDrinkVariant.active == True)  # noqa: E712
    return q.order_by(ProductDrinkVariant.sort_order).all()


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

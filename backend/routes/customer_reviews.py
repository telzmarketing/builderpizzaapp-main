"""Customer review submission, public product reviews, and moderation."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.orm import Session

from backend.core.response import created, err, ok
from backend.core.tenant_context import TenantContext, TenantSource, TenantContextMissing, trusted_process_context
from backend.core.tenant_runtime import resolve_panel_tenant_context, resolve_public_tenant_context
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.models.delivery import Delivery
from backend.models.order import Order, OrderItem
from backend.models.product import Product
from backend.routes.admin_auth import get_current_admin
from backend.routes.order_access import require_order_or_admin
from backend.schemas.customer_review import (
    CustomerReviewAdminCreate as AdminReviewCreate,
    CustomerReviewCreate,
    CustomerReviewOut,
    ProductReviewCreate,
    ProductReviewSummaryOut,
    CustomerReviewModerationIn as ReviewModerationUpdate,
)
from backend.services.customer_review_service import CustomerReviewService


router = APIRouter(prefix="/reviews", tags=["customer-reviews"])


def _panel_context(request: Request, db: Session, admin: AdminUser) -> TenantContext:
    context = resolve_panel_tenant_context(request, db, admin)
    if context is None:
        raise TenantContextMissing("Selecione uma empresa antes de gerenciar avaliações.")
    return context


def _serialize(review, db: Session) -> dict:
    data = CustomerReviewOut.model_validate(review).model_dump(mode="json")
    if review.product_id:
        product = db.query(Product).filter(
            Product.id == review.product_id,
            Product.tenant_id == review.tenant_id,
        ).first()
        data["product_name"] = product.name if product else None
    if review.order_id:
        order = db.query(Order).filter(Order.id == review.order_id, Order.tenant_id == review.tenant_id).first()
        data["order_code"] = order.order_code if order else None
    return data


def _context_from_order(request: Request, db: Session, order: Order) -> TenantContext:
    public = resolve_public_tenant_context(request, db)
    if public is not None:
        public.assert_tenant(order.tenant_id)
        return public
    if not order.tenant_id:
        raise TenantContextMissing("Pedido sem tenant confiável.")
    return trusted_process_context(order.tenant_id, source=TenantSource.JOB, correlation_id=f"review-order:{order.id}")


def _order_for_item(db: Session, order_item_id: str) -> Order:
    item = db.query(OrderItem).filter(OrderItem.id == order_item_id).first()
    if not item:
        from fastapi import HTTPException
        raise HTTPException(404, "Item do pedido não encontrado.")
    order = db.query(Order).filter(Order.id == item.order_id, Order.archived_at.is_(None)).first()
    if not order:
        from fastapi import HTTPException
        raise HTTPException(404, "Pedido não encontrado.")
    return order


def _order_for_delivery(db: Session, delivery_id: str) -> Order:
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not delivery:
        from fastapi import HTTPException
        raise HTTPException(404, "Entrega não encontrada.")
    order = db.query(Order).filter(Order.id == delivery.order_id, Order.archived_at.is_(None)).first()
    if not order:
        from fastapi import HTTPException
        raise HTTPException(404, "Pedido não encontrado.")
    return order


@router.post("/orders/{order_id}")
def submit_order_review(
    order_id: str,
    body: CustomerReviewCreate,
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_customer_phone: str | None = Header(default=None),
    x_customer_email: str | None = Header(default=None),
):
    order = db.query(Order).filter(Order.id == order_id, Order.archived_at.is_(None)).first()
    if not order:
        from fastapi import HTTPException
        raise HTTPException(404, "Pedido não encontrado.")
    require_order_or_admin(order, db, authorization, x_customer_phone, x_customer_email, expected_tenant_id=order.tenant_id)
    review = CustomerReviewService(db, _context_from_order(request, db, order)).create_customer_review(
        body.model_copy(update={"order_id": order_id, "review_type": "order", "order_item_id": None, "product_id": None, "delivery_id": None}), customer_id=order.customer_id,
    )
    return created(_serialize(review, db), "Avaliação do pedido registrada e enviada para moderação.")


@router.post("/order-items/{order_item_id}")
def submit_product_review(
    order_item_id: str,
    body: ProductReviewCreate,
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_customer_phone: str | None = Header(default=None),
    x_customer_email: str | None = Header(default=None),
):
    order = _order_for_item(db, order_item_id)
    require_order_or_admin(order, db, authorization, x_customer_phone, x_customer_email, expected_tenant_id=order.tenant_id)
    review = CustomerReviewService(db, _context_from_order(request, db, order)).create_customer_review(
        body.model_copy(update={"order_id": order.id, "review_type": "item", "order_item_id": order_item_id}), customer_id=order.customer_id,
    )
    return created(_serialize(review, db), "Avaliação da pizza registrada e enviada para moderação.")


@router.post("/deliveries/{delivery_id}")
def submit_delivery_review(
    delivery_id: str,
    body: CustomerReviewCreate,
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_customer_phone: str | None = Header(default=None),
    x_customer_email: str | None = Header(default=None),
):
    order = _order_for_delivery(db, delivery_id)
    require_order_or_admin(order, db, authorization, x_customer_phone, x_customer_email, expected_tenant_id=order.tenant_id)
    review = CustomerReviewService(db, _context_from_order(request, db, order)).create_customer_review(
        body.model_copy(update={"order_id": order.id, "review_type": "delivery", "delivery_id": delivery_id}), customer_id=order.customer_id,
    )
    return created(_serialize(review, db), "Avaliação da entrega registrada e enviada para moderação.")


@router.get("/products/{product_id}", response_model=ProductReviewSummaryOut)
def list_product_reviews(
    product_id: str,
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    context = resolve_public_tenant_context(request, db)
    if context is None:
        from fastapi import HTTPException
        raise HTTPException(404, "Loja não encontrada para este domínio.")
    reviews = CustomerReviewService(db, context).list_reviews(public_only=True, review_type="item", product_id=product_id, limit=limit)
    ratings = [review.rating for review in reviews]
    return {"product_id": product_id, "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None, "count": len(ratings), "reviews": [_serialize(review, db) for review in reviews]}


@router.get("/public")
def list_public_reviews(
    request: Request,
    product_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    context = resolve_public_tenant_context(request, db)
    if context is None:
        from fastapi import HTTPException
        raise HTTPException(404, "Loja não encontrada para este domínio.")
    reviews = CustomerReviewService(db, context).list_reviews(
        public_only=True,
        product_id=product_id,
        limit=limit,
    )
    return [_serialize(review, db) for review in reviews]


@router.get("/admin")
def list_admin_reviews(
    request: Request,
    review_type: str | None = Query(default=None, pattern="^(order|item|product|delivery)$"),
    status: str | None = Query(default=None, pattern="^(pending|approved|rejected)$"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    context = _panel_context(request, db, admin)
    normalized_type = "item" if review_type == "product" else review_type
    reviews = CustomerReviewService(db, context).list_reviews(review_type=normalized_type, status=status, limit=limit)
    return ok([_serialize(review, db) for review in reviews])


@router.post("/admin", status_code=201)
def create_admin_review(
    body: AdminReviewCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    review = CustomerReviewService(db, _panel_context(request, db, admin)).create_admin_review(body, admin_id=admin.id)
    return created(_serialize(review, db), "Avaliação criada.")


@router.patch("/admin/{review_id}/moderation")
def moderate_review(
    review_id: str,
    body: ReviewModerationUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    review = CustomerReviewService(db, _panel_context(request, db, admin)).moderate(review_id, body, admin_id=admin.id)
    return ok(_serialize(review, db), "Moderação da avaliação atualizada.")

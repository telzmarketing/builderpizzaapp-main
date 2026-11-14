from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.tenant_context import TenantContext, TenantContextMissing
from backend.models.customer_review import CustomerReview
from backend.models.delivery import Delivery, DeliveryStatus
from backend.models.order import Order, OrderItem, OrderStatus
from backend.models.product import Product
from backend.schemas.customer_review import (
    CustomerReviewAdminCreate,
    CustomerReviewCreate,
    CustomerReviewModerationIn,
)


class ReviewAlreadyExists(DomainError):
    http_status = 409

    def __init__(self):
        super().__init__("Este item do pedido já possui uma avaliação.", code="CustomerReviewAlreadyExists")


class CustomerReviewService:
    def __init__(self, db: Session, tenant_context: TenantContext):
        if tenant_context is None or not tenant_context.tenant_id:
            raise TenantContextMissing("Contexto de tenant obrigatório para avaliações.")
        self._db = db
        self._tenant_id = tenant_context.tenant_id

    def _query(self, model):
        return self._db.query(model).filter(model.tenant_id == self._tenant_id)

    def _order(self, order_id: str) -> Order:
        order = self._query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(404, "Pedido não encontrado.")
        return order

    def _validate_target(self, body: CustomerReviewCreate):
        order = self._order(body.order_id)
        status = order.status.value if hasattr(order.status, "value") else str(order.status)
        if status not in {OrderStatus.delivered.value, "completed"}:
            raise DomainError("O pedido precisa estar entregue para receber avaliação.", code="CustomerReviewOrderNotEligible")

        item = None
        product = None
        delivery = None
        if body.review_type == "order":
            if body.order_item_id or body.product_id or body.delivery_id:
                raise DomainError("Avaliação de pedido não aceita alvo adicional.", code="CustomerReviewTargetInvalid")
        elif body.review_type == "item":
            if not body.order_item_id:
                raise DomainError("Informe o item do pedido para avaliá-lo.", code="CustomerReviewTargetInvalid")
            item = self._query(OrderItem).filter(OrderItem.id == body.order_item_id, OrderItem.order_id == order.id).first()
            if not item:
                raise HTTPException(404, "Item do pedido não encontrado.")
            product_id = body.product_id or item.product_id
            if product_id != item.product_id:
                raise DomainError("O produto não pertence ao item informado.", code="CustomerReviewTargetInvalid")
            product = self._query(Product).filter(Product.id == product_id).first()
            if not product:
                raise HTTPException(404, "Produto não encontrado.")
        elif body.review_type == "delivery":
            if not body.delivery_id:
                raise DomainError("Informe a entrega para avaliá-la.", code="CustomerReviewTargetInvalid")
            delivery = self._query(Delivery).filter(Delivery.id == body.delivery_id, Delivery.order_id == order.id).first()
            if not delivery:
                raise HTTPException(404, "Entrega não encontrada.")
            if delivery.status not in (DeliveryStatus.delivered, DeliveryStatus.completed):
                raise DomainError("A entrega ainda não está concluída.", code="CustomerReviewDeliveryNotEligible")
        return order, item, product, delivery

    def _existing(self, body: CustomerReviewCreate):
        query = self._query(CustomerReview).filter(
            CustomerReview.order_id == body.order_id,
            CustomerReview.review_type == body.review_type,
        )
        if body.review_type == "item":
            query = query.filter(CustomerReview.order_item_id == body.order_item_id)
        elif body.review_type == "delivery":
            query = query.filter(CustomerReview.delivery_id == body.delivery_id)
        else:
            query = query.filter(CustomerReview.order_item_id.is_(None), CustomerReview.delivery_id.is_(None))
        return query.first()

    def _refresh_product_rating(self, product_id: str) -> None:
        product = self._query(Product).filter(Product.id == product_id).first()
        if not product:
            return
        average = self._query(CustomerReview).filter(
            CustomerReview.product_id == product_id,
            CustomerReview.review_type == "item",
            CustomerReview.status == "approved",
        ).with_entities(func.avg(CustomerReview.rating)).scalar()
        if average is not None:
            product.rating = round(float(average), 2)

    def create_customer_review(self, body: CustomerReviewCreate, customer_id: str | None = None) -> CustomerReview:
        order, item, product, delivery = self._validate_target(body)
        if self._existing(body):
            raise ReviewAlreadyExists()
        review = CustomerReview(
            id=str(uuid.uuid4()),
            tenant_id=self._tenant_id,
            order_id=order.id,
            order_item_id=item.id if item else None,
            product_id=product.id if product else None,
            delivery_id=delivery.id if delivery else None,
            customer_id=customer_id or order.customer_id,
            review_type=body.review_type,
            rating=body.rating,
            comment=body.comment,
            author_name=order.delivery_name,
            status="pending",
            source="customer",
        )
        self._db.add(review)
        self._db.commit()
        self._db.refresh(review)
        return review

    def create_admin_review(self, body: CustomerReviewAdminCreate, admin_id: str) -> CustomerReview:
        order, item, product, delivery = self._validate_target(body)
        if self._existing(body):
            raise ReviewAlreadyExists()
        review = CustomerReview(
            id=str(uuid.uuid4()), tenant_id=self._tenant_id, order_id=order.id,
            order_item_id=item.id if item else None, product_id=product.id if product else None,
            delivery_id=delivery.id if delivery else None, customer_id=order.customer_id,
            review_type=body.review_type, rating=body.rating, comment=body.comment,
            author_name=body.author_name or order.delivery_name, status=body.status,
            source="admin", moderated_by_admin_id=admin_id,
            moderated_at=datetime.now(timezone.utc) if body.status != "pending" else None,
        )
        self._db.add(review)
        if review.status == "approved" and review.product_id:
            self._db.flush()
            self._refresh_product_rating(review.product_id)
        self._db.commit()
        self._db.refresh(review)
        return review

    def list_reviews(self, *, public_only: bool = False, status: str | None = None,
                     review_type: str | None = None, product_id: str | None = None,
                     order_id: str | None = None, limit: int = 100):
        query = self._query(CustomerReview)
        if public_only:
            query = query.filter(CustomerReview.status == "approved")
        elif status:
            query = query.filter(CustomerReview.status == status)
        if review_type:
            query = query.filter(CustomerReview.review_type == review_type)
        if product_id:
            query = query.filter(CustomerReview.product_id == product_id)
        if order_id:
            query = query.filter(CustomerReview.order_id == order_id)
        return query.order_by(CustomerReview.created_at.desc()).limit(limit).all()

    def moderate(self, review_id: str, body: CustomerReviewModerationIn, admin_id: str) -> CustomerReview:
        review = self._query(CustomerReview).filter(CustomerReview.id == review_id).first()
        if not review:
            raise HTTPException(404, "Avaliação não encontrada.")
        review.status = body.status
        review.moderation_note = body.moderation_note
        review.moderated_by_admin_id = admin_id
        review.moderated_at = datetime.now(timezone.utc)
        if review.product_id:
            self._db.flush()
            self._refresh_product_rating(review.product_id)
        self._db.commit()
        self._db.refresh(review)
        return review

    def sync_legacy_delivery_rating(self, delivery: Delivery, rating: int, comment: str | None) -> CustomerReview:
        body = CustomerReviewCreate(order_id=delivery.order_id, review_type="delivery", rating=rating,
                                    delivery_id=delivery.id, comment=comment)
        existing = self._existing(body)
        if existing:
            existing.rating = rating
            existing.comment = comment
            existing.status = "approved"
            existing.source = "customer"
            self._db.commit()
            self._db.refresh(existing)
            return existing
        order = self._order(delivery.order_id)
        review = CustomerReview(
            id=str(uuid.uuid4()), tenant_id=self._tenant_id, order_id=order.id,
            delivery_id=delivery.id, customer_id=order.customer_id,
            review_type="delivery", rating=rating, comment=comment,
            author_name=order.delivery_name, status="approved", source="customer",
        )
        self._db.add(review)
        self._db.commit()
        self._db.refresh(review)
        return review

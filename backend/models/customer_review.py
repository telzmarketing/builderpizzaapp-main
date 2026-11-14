from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)

from backend.database import Base


class CustomerReview(Base):
    """Tenant-scoped customer feedback for a completed order."""

    __tablename__ = "customer_reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            name="fk_customer_reviews_tenant_order",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "order_item_id"],
            ["order_items.tenant_id", "order_items.id"],
            name="fk_customer_reviews_tenant_order_item",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_customer_reviews_tenant_product",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "delivery_id"],
            ["deliveries.tenant_id", "deliveries.id"],
            name="fk_customer_reviews_tenant_delivery",
            ondelete="RESTRICT",
        ),
        Index("ix_customer_reviews_tenant_status_created", "tenant_id", "status", "created_at"),
        Index("ix_customer_reviews_tenant_product_status", "tenant_id", "product_id", "status"),
        Index("ix_customer_reviews_tenant_order", "tenant_id", "order_id"),
        CheckConstraint("review_type IN ('order','item','delivery')", name="ck_customer_reviews_type"),
        CheckConstraint("status IN ('pending','approved','rejected')", name="ck_customer_reviews_status"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_customer_reviews_rating"),
    )

    id = Column(String(36), primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    order_id = Column(String, nullable=False)
    order_item_id = Column(String, nullable=True)
    product_id = Column(String, nullable=True)
    delivery_id = Column(String, nullable=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    review_type = Column(String(20), nullable=False)
    rating = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    author_name = Column(String(200), nullable=True)
    status = Column(String(20), nullable=False, default="pending", server_default="pending")
    source = Column(String(20), nullable=False, default="customer", server_default="customer")
    moderation_note = Column(Text, nullable=True)
    moderated_by_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True)
    moderated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

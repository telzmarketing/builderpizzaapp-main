from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ReviewType = Literal["order", "item", "product", "delivery"]
ReviewStatus = Literal["pending", "approved", "rejected"]


class CustomerReviewCreate(BaseModel):
    order_id: str = Field(..., min_length=1, max_length=100)
    review_type: ReviewType
    rating: int = Field(..., ge=1, le=5)
    order_item_id: str | None = Field(default=None, max_length=100)
    product_id: str | None = Field(default=None, max_length=100)
    delivery_id: str | None = Field(default=None, max_length=100)
    comment: str | None = Field(default=None, max_length=4000)

    @field_validator("comment")
    @classmethod
    def normalize_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("review_type", mode="before")
    @classmethod
    def normalize_product_type(cls, value: str) -> str:
        # The storage contract calls this target an item; accept the clearer
        # public API name as an additive compatibility alias.
        return "item" if value == "product" else value


class CustomerReviewAdminCreate(CustomerReviewCreate):
    status: ReviewStatus = "approved"
    author_name: str | None = Field(default=None, max_length=200)


class CustomerReviewModerationIn(BaseModel):
    status: ReviewStatus
    moderation_note: str | None = Field(default=None, max_length=4000)


class CustomerReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    order_id: str
    order_item_id: str | None = None
    product_id: str | None = None
    delivery_id: str | None = None
    customer_id: str | None = None
    review_type: ReviewType
    rating: int
    comment: str | None = None
    author_name: str | None = None
    status: ReviewStatus
    source: str
    moderation_note: str | None = None
    moderated_by_admin_id: str | None = None
    moderated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CustomerReviewListQuery(BaseModel):
    status: ReviewStatus | None = None
    review_type: ReviewType | None = None
    product_id: str | None = None
    order_id: str | None = None
    limit: int = Field(default=100, ge=1, le=500)


# Compatibility names used by the public review routes.
ProductReviewCreate = CustomerReviewCreate


class ProductReviewSummaryOut(BaseModel):
    product_id: str
    average_rating: float | None = None
    count: int = 0
    reviews: list[CustomerReviewOut] = []

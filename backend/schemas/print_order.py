from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

Platform = Literal["ifood", "99food", "keeta", "unknown"]


class PrintOrderItemReviewIn(BaseModel):
    external_name: str = Field(min_length=1, max_length=300)
    product_id: str | None = Field(default=None, min_length=1, max_length=120)
    quantity: int = Field(default=1, ge=1, le=999)
    selected_size: str | None = Field(default=None, max_length=80)
    flavor_names: list[str] = Field(default_factory=list, max_length=8)
    customizations: dict = Field(default_factory=dict)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    total_price: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)


class PrintOrderReviewIn(BaseModel):
    platform: Platform | None = None
    store_identifier: str | None = Field(default=None, max_length=120)
    external_order_number: str | None = Field(default=None, max_length=120)
    customer_name: str | None = Field(default=None, max_length=200)
    customer_phone: str | None = Field(default=None, max_length=30)
    delivery_street: str | None = Field(default=None, max_length=300)
    delivery_city: str | None = Field(default=None, max_length=100)
    delivery_complement: str | None = Field(default=None, max_length=100)
    fulfillment_type: Literal["delivery", "pickup"] = "delivery"
    payment_method: str | None = Field(default=None, max_length=40)
    subtotal: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    delivery_fee: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    service_fee: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    store_discount: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    platform_discount: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    total_paid: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    printed_total: Decimal | None = Field(default=None, ge=0, max_digits=20, decimal_places=2)
    items: list[PrintOrderItemReviewIn] = Field(default_factory=list, max_length=200)


class PrintOrderMappingIn(BaseModel):
    platform: Platform
    external_product_id: str | None = Field(default=None, max_length=120)
    external_name: str = Field(min_length=1, max_length=300)
    product_id: str = Field(min_length=1, max_length=120)
    variation: dict = Field(default_factory=dict)


class PrintOrderOut(BaseModel):
    id: str
    tenant_id: str
    platform: str
    external_order_number: str | None
    status: str
    source_asset_id: str
    order_id: str | None
    duplicate_of_id: str | None
    review_notes: list
    items: list[dict]
    financials: dict = Field(default_factory=dict)
    reconciliation: dict = Field(default_factory=dict)
    created_at: datetime

"""Public, validated projection of an authoritative checkout quote."""
from typing import Any

from pydantic import BaseModel, Field


class CheckoutQuoteItemOut(BaseModel):
    product_id: str
    quantity: int
    selected_size: str
    selected_size_id: str | None = None
    selected_crust_type_id: str | None = None
    selected_crust_type: str | None = None
    selected_border_id: str | None = None
    selected_border_name: str | None = None
    selected_drink_variant_id: str | None = None
    selected_drink_variant: str | None = None
    unit_price: float
    line_total: float
    standard_unit_price: float
    promotion_applied: bool = False
    promotion_id: str | None = None
    promotion_name: str | None = None
    promotion_discount: float = 0
    promotion_free_shipping: bool = False
    promotion_gift_enabled: bool = False
    promotion_gift_product_id: str | None = None
    promotion_gift_quantity: int = 1
    promotion_gift_name: str | None = None
    promotion_gift_icon: str | None = None
    promotion_blocks_other_coupons: bool = False
    promotion_blocked: bool = False
    promotion_block_reason: str | None = None
    flavors: list[dict[str, Any]] = Field(default_factory=list)


class CheckoutQuoteOut(BaseModel):
    items: list[CheckoutQuoteItemOut]
    subtotal: float
    shipping: dict[str, Any]
    coupon: dict[str, Any] | None = None
    discount: float
    delivery_fee_final: float
    promotion_free_shipping_applied: bool = False
    total: float
    payment_method: str

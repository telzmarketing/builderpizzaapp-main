from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


MarketplaceProvider = Literal["partner_99", "ifood", "keeta"]
MarketplaceSettlementStatus = Literal["expected", "partially_received", "received", "divergent", "cancelled", "quarantined"]


class MarketplaceSettlementIn(BaseModel):
    provider: MarketplaceProvider
    gross_amount: Decimal = Field(ge=0, max_digits=20, decimal_places=2)
    store_discount_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=20, decimal_places=2)
    marketplace_discount_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=20, decimal_places=2)
    delivery_fee: Decimal = Field(default=Decimal("0"), ge=0, max_digits=20, decimal_places=2)
    service_fee: Decimal = Field(default=Decimal("0"), ge=0, max_digits=20, decimal_places=2)
    commission_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=20, decimal_places=2)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=20, decimal_places=2)
    expected_net_amount: Decimal = Field(ge=0, max_digits=20, decimal_places=2)
    received_net_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=20, decimal_places=2)
    status: MarketplaceSettlementStatus = "expected"
    external_settlement_reference: str | None = Field(default=None, max_length=180)
    expected_settlement_at: datetime | None = None
    settled_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)


class MarketplaceSettlementOut(MarketplaceSettlementIn):
    id: str
    tenant_id: str
    order_id: str
    variance_amount: Decimal
    idempotency_key: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

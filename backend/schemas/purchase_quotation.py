from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator


class PurchaseQuotationCreate(BaseModel):
    requisition_id: str
    supplier_ids: list[str] = Field(min_length=1, max_length=100)
    response_due: date | None = None
    notes: str | None = None


class PurchaseQuotationOfferCreate(BaseModel):
    quotation_line_id: str
    supplier_id: str
    unit_price: Decimal = Field(ge=0)
    conversion_factor: Decimal = Field(gt=0)
    freight: Decimal = Field(default=Decimal("0"), ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    payment_terms: str | None = None
    delivery_days: int | None = Field(default=None, ge=0)
    valid_until: date | None = None
    notes: str | None = None


class PurchaseQuotationTransitionIn(BaseModel):
    expected_version: int = Field(gt=0)
    reason: str | None = None


class PurchaseQuotationOfferOut(BaseModel):
    id: str
    supplier_id: str
    supplier_name: str
    quotation_line_id: str
    unit_price: Decimal
    conversion_factor: Decimal
    normalized_unit_price: Decimal
    freight: Decimal
    discount: Decimal
    total: Decimal
    payment_terms: str | None
    delivery_days: int | None
    valid_until: date | None
    notes: str | None


class PurchaseQuotationLineOut(BaseModel):
    id: str
    item_id: str
    item_name: str
    unit_id: str
    unit_symbol: str
    quantity: Decimal
    position: int


class PurchaseQuotationSupplierOut(BaseModel):
    supplier_id: str
    supplier_name: str
    status: str


class PurchaseQuotationOut(BaseModel):
    id: str
    tenant_id: str
    requisition_id: str
    code: str
    status: str
    response_due: date | None
    notes: str | None
    version: int
    awarded_supplier_id: str | None
    created_by_admin_id: str
    created_at: datetime
    updated_at: datetime
    suppliers: list[PurchaseQuotationSupplierOut]
    lines: list[PurchaseQuotationLineOut]
    offers: list[PurchaseQuotationOfferOut]


class PurchaseQuotationTransitionOut(BaseModel):
    quotation: PurchaseQuotationOut

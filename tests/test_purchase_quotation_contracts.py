from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.schemas.purchase_quotation import PurchaseQuotationCreate, PurchaseQuotationOfferCreate


def test_quotation_requires_at_least_one_supplier():
    with pytest.raises(ValidationError):
        PurchaseQuotationCreate(requisition_id="req-1", supplier_ids=[])


def test_offer_rejects_invalid_price_and_conversion():
    with pytest.raises(ValidationError):
        PurchaseQuotationOfferCreate(quotation_line_id="line-1", supplier_id="sup-1", unit_price=Decimal("-1"), conversion_factor=Decimal("1"))
    with pytest.raises(ValidationError):
        PurchaseQuotationOfferCreate(quotation_line_id="line-1", supplier_id="sup-1", unit_price=Decimal("10"), conversion_factor=Decimal("0"))


def test_offer_accepts_decimal_normalization_inputs():
    offer = PurchaseQuotationOfferCreate(quotation_line_id="line-1", supplier_id="sup-1", unit_price=Decimal("40"), conversion_factor=Decimal("4"), freight=Decimal("2"))
    assert offer.unit_price / offer.conversion_factor == Decimal("10")

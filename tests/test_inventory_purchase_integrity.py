from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from backend.services.inventory_service import InventoryInvalidReference, InventoryService


def _service():
    service = object.__new__(InventoryService)
    service._db = MagicMock()
    service._tenant_id = "tenant-a"
    service._actor_id = "admin-a"
    return service


def test_min_stock_confirmation_requires_supplier_and_positive_cost():
    service = _service()
    purchase = SimpleNamespace(
        status="confirmed", source="min_stock", supplier_id=None,
        items=[SimpleNamespace(unit_cost=0, total_cost=0)],
    )

    with pytest.raises(InventoryInvalidReference):
        service._validate_purchase_confirmation(purchase)


def test_non_min_stock_confirmation_keeps_existing_contract():
    service = _service()
    purchase = SimpleNamespace(
        status="confirmed", source="manual", supplier_id=None, items=[],
    )

    service._validate_purchase_confirmation(purchase)


def test_invalid_replenishment_cancellation_requires_zero_value_without_supplier():
    service = _service()
    service._get_purchase = lambda _: SimpleNamespace(
        status="confirmed", source="min_stock", supplier_id="supplier-1", total_amount=0
    )

    with pytest.raises(InventoryInvalidReference):
        service.cancel_invalid_replenishment("purchase-1", reason="teste")

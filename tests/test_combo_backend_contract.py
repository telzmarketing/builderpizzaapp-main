from types import SimpleNamespace

import pytest

from backend.core.exceptions import DomainError
from backend.core.tenant_context import TenantContext, TenantSource
from backend.models.campaign import PromotionalKit, PromotionalKitItem
from backend.models.product import Product
from backend.schemas.order import CartItemIn
from backend.services import combo_service
from backend.services.combo_service import ComboService


class _Query:
    def __init__(self, model, rows):
        self.model = model
        self.rows = rows

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return list(self.rows)


class _Db:
    def __init__(self, kit, kit_items, products):
        self.rows = {PromotionalKit: [kit], PromotionalKitItem: kit_items, Product: products}

    def query(self, model):
        return _Query(model, self.rows.get(model, []))


@pytest.fixture
def combo_db():
    tenant = "tenant-combo-test"
    kit = SimpleNamespace(
        id="kit-1", tenant_id=tenant, name="Família", active=True,
        valid_until=None, price_promotional=12.00,
    )
    items = [
        SimpleNamespace(kit_id=kit.id, tenant_id=tenant, product_id="pizza", quantity=1),
        SimpleNamespace(kit_id=kit.id, tenant_id=tenant, product_id="refrigerante", quantity=2),
    ]
    products = [
        SimpleNamespace(id="pizza", tenant_id=tenant, name="Pizza", price=10.0, icon="🍕", active=True),
        SimpleNamespace(id="refrigerante", tenant_id=tenant, name="Refrigerante", price=5.0, icon="🥤", active=True),
    ]
    return _Db(kit, items, products), TenantContext(tenant_id=tenant, source=TenantSource.JOB)


def test_closed_combo_expands_integer_component_quantities_and_exact_price(combo_db, monkeypatch):
    db, context = combo_db
    monkeypatch.setattr(combo_service, "scope_query_to_tenant", lambda query, *args, **kwargs: query)
    request = CartItemIn(kit_id="kit-1", quantity=2)

    expanded, metadata = ComboService(db, context).expand([request])

    assert [item.product_id for item in expanded] == ["pizza", "refrigerante"]
    assert [item.quantity for item in expanded] == [2, 4]
    assert sum(round(metadata[id(item)].unit_price * item.quantity, 2) for item in expanded) == 24.00
    assert all(item.selected_size == "Combo" for item in expanded)


def test_closed_combo_rejects_client_component_customization(combo_db, monkeypatch):
    db, context = combo_db
    monkeypatch.setattr(combo_service, "scope_query_to_tenant", lambda query, *args, **kwargs: query)
    request = CartItemIn(kit_id="kit-1", quantity=1, selected_size_id="size-from-client")

    with pytest.raises(DomainError) as error:
        ComboService(db, context).expand([request])

    assert error.value.code == "ComboCustomizationNotAllowed"


def test_cart_contract_requires_exactly_one_product_or_closed_combo():
    with pytest.raises(ValueError):
        CartItemIn(quantity=1)
    with pytest.raises(ValueError):
        CartItemIn(product_id="pizza", kit_id="kit-1", quantity=1)

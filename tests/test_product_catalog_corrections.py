"""Catalog regression contracts, including real PostgreSQL API transactions."""
from __future__ import annotations

import os
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.core.catalog_context import catalog_tenant_context
from backend.core.tenant_context import TenantContext, TenantContextMissing, TenantSource
from backend.core import rbac_authorization
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.models.membership import TenantMembership
from backend.models.product import Product, ProductCategory, ProductSize, ProductCrustType
from backend.models.rbac import Role
from backend.models.tenant import Tenant
from backend.routes import products
from backend.routes.admin_auth import get_current_admin
from backend.schemas.product import (
    ProductCreate, ProductUpdate, ProductPromotionCreate, ProductPromotionUpdate,
    ProductCategoryUpdate, ProductSizeUpdate,
)
from backend.services.product_catalog_service import ProductCatalogService
from backend.services.product_category_service import update_category


@pytest.mark.parametrize("values", [
    {"name": None}, {"name": "  "}, {"description": None}, {"price": None},
    {"price": float("inf")}, {"active": None}, {"visible_delivery": None},
    {"product_type": "unknown"}, {"best_seller_badge_mode": "unknown"},
])
def test_product_update_rejects_invalid_explicit_values(values):
    with pytest.raises(ValidationError):
        ProductUpdate(**values)


def test_update_distinguishes_omission_and_allowed_clear():
    assert ProductUpdate().model_dump(exclude_unset=True) == {}
    assert ProductUpdate(category=None, delivery_price=None).model_dump(exclude_unset=True) == {
        "category": None, "delivery_price": None,
    }
    assert ProductCategoryUpdate(parent_id=None).model_dump(exclude_unset=True) == {"parent_id": None}
    with pytest.raises(ValidationError):
        ProductSizeUpdate(label=None)


@pytest.mark.parametrize("values", [
    {"start_time": "99:99"}, {"end_time": "24:00"}, {"timezone": "invalid/zone"},
    {"valid_weekdays": [-1]}, {"start_date": date(2026, 10, 21), "end_date": date(2026, 10, 20)},
    {"active": None}, {"valid_weekdays": None},
])
def test_promotion_rejects_impossible_windows_and_null_required_fields(values):
    with pytest.raises(ValidationError):
        ProductPromotionCreate(name="Promo", **values)


def test_promotion_preserves_overnight_window_and_explicit_clear():
    assert ProductPromotionCreate(name="Evening", start_time="22:00", end_time="02:00").end_time == "02:00"
    assert ProductPromotionUpdate(start_time=None).model_dump(exclude_unset=True) == {"start_time": None}


def test_legacy_catalog_is_explicitly_scoped_without_enabling_rollout(monkeypatch):
    monkeypatch.setattr("backend.core.catalog_context.identity_catalog_enforcement_enabled", lambda: False)
    assert catalog_tenant_context(None).tenant_id == "tenant-legacy-default"
    trusted = TenantContext(tenant_id="tenant-a", source=TenantSource.JOB)
    assert catalog_tenant_context(trusted) is trusted
    monkeypatch.setattr("backend.core.catalog_context.identity_catalog_enforcement_enabled", lambda: True)
    with pytest.raises(TenantContextMissing):
        catalog_tenant_context(None)


@pytest.fixture
def catalog_pg(monkeypatch):
    url = os.environ.get("PRODUCT_AUDIT_DATABASE_URL")
    if not url:
        pytest.skip("Set PRODUCT_AUDIT_DATABASE_URL to the migrated disposable PostgreSQL database")
    # Load the application's complete model registry; no startup hooks or seeds.
    from backend.main import app as _registered_app  # noqa: F401
    engine = create_engine(url, connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        outer = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
        marker = uuid4().hex
        tenant_a, tenant_b = f"catalog-a-{marker}", f"catalog-b-{marker}"
        session.add_all([Tenant(id=tenant_a, slug=tenant_a, name="Catalog A"), Tenant(id=tenant_b, slug=tenant_b, name="Catalog B")])
        session.flush()
        role = Role(id=f"role-{marker}", tenant_id=tenant_a, name="Catalog viewer")
        admin = AdminUser(id=f"admin-{marker}", email=f"{marker}@example.test", name="Catalog auditor", password_hash="not-used", role_id=role.id)
        session.add_all([role, admin])
        session.flush()
        membership = TenantMembership(id=f"membership-{marker}", tenant_id=tenant_a, user_id=admin.id, role="operator", status="active")
        session.add(membership)
        session.flush()
        context = TenantContext(tenant_id=tenant_a, source=TenantSource.JOB)
        monkeypatch.setattr(products, "resolve_panel_tenant_context", lambda *_args: context)
        monkeypatch.setattr(products, "resolve_public_tenant_context", lambda *_args: context)
        monkeypatch.setattr(products, "_require_admin", lambda *_args: admin)
        monkeypatch.setattr(rbac_authorization, "resolve_panel_tenant_context", lambda *_args: context)
        app = FastAPI()
        app.include_router(products.router, prefix="/api")
        app.dependency_overrides[get_db] = lambda: session
        app.dependency_overrides[get_current_admin] = lambda: admin
        state = SimpleNamespace(db=session, client=TestClient(app), context=context, tenant_a=tenant_a,
                                tenant_b=tenant_b, membership=membership, marker=marker)
        try:
            yield state
        finally:
            state.client.close()
            session.close()
            outer.rollback()
    engine.dispose()


def _product(state, *, tenant=None, **values):
    row = Product(id=f"product-{uuid4().hex}", tenant_id=tenant or state.tenant_a, name="Product",
                  description="Synthetic", price=30, product_type="pizza", **values)
    state.db.add(row)
    state.db.flush()
    return row


def test_postgres_rbac_blocks_direct_catalog_mutations(catalog_pg):
    state = catalog_pg
    product = _product(state)
    for method, path, body in [
        ("post", "/api/products", {"name": "Unauthorized", "description": "", "price": 5}),
        ("put", f"/api/products/{product.id}", {"price": 1}),
        ("delete", f"/api/products/{product.id}", None),
        ("post", "/api/products/categories", {"name": "Unauthorized"}),
        ("post", f"/api/products/{product.id}/sizes", {"label": "Large", "price": 80}),
        ("post", f"/api/products/{product.id}/promotions", {"name": "Unauthorized"}),
    ]:
        response = state.client.request(method, path, json=body)
        assert response.status_code == 403, response.text
    assert state.client.get("/api/products?active_only=false").status_code == 403
    state.db.refresh(product)
    assert product.price == 30 and product.active


def test_postgres_admin_recovers_inactive_without_exposing_to_public(catalog_pg):
    state = catalog_pg
    state.membership.role = "owner"
    state.db.flush()
    response = state.client.post("/api/products", json={"name": "Recoverable", "description": "", "price": 30})
    assert response.status_code == 201, response.text
    product_id = response.json()["id"]
    assert state.client.delete(f"/api/products/{product_id}").status_code == 204
    assert product_id not in {row["id"] for row in state.client.get("/api/products").json()}
    assert product_id in {row["id"] for row in state.client.get("/api/products?active_only=false").json()}
    response = state.client.put(f"/api/products/{product_id}", json={"active": True})
    assert response.status_code == 200 and response.json()["id"] == product_id
    assert product_id in {row["id"] for row in state.client.get("/api/products").json()}


def test_postgres_public_channel_scope_and_authoritative_quote(catalog_pg):
    state = catalog_pg
    visible = _product(state, delivery_price=40, dine_in_price=35)
    hidden = _product(state, visible_delivery=False, visible_dine_in=True)
    foreign = _product(state, tenant=state.tenant_b)
    crust = ProductCrustType(id=f"crust-{state.marker}", tenant_id=state.tenant_a, product_id=visible.id, name="Normal", price_addition=2)
    border = ProductCrustType(id=f"border-{state.marker}", tenant_id=state.tenant_a, product_id=visible.id, name="Borda recheada", price_addition=7, option_kind="border")
    size = ProductSize(id=f"size-{state.marker}", tenant_id=state.tenant_a, product_id=visible.id, label="Grande", price=80)
    state.db.add_all([crust, border, size])
    state.db.flush()
    ids = {row["id"] for row in state.client.get("/api/products").json()}
    assert visible.id in ids and hidden.id not in ids and foreign.id not in ids
    assert state.client.get(f"/api/products/{hidden.id}").status_code == 404
    assert state.client.get(f"/api/products/{hidden.id}/sizes").status_code == 404
    assert state.client.get(f"/api/products/{hidden.id}?channel=dine_in").status_code == 200
    assert state.client.get(f"/api/products/{foreign.id}").status_code == 404
    response = state.client.get(f"/api/products/{visible.id}/price", params={"size_id": size.id, "crust_id": crust.id, "border_id": border.id})
    assert response.status_code == 200, response.text
    assert response.json()["final_price"] == 89
    assert state.client.get(f"/api/products/{visible.id}/price", params={"crust_id": border.id, "border_id": border.id}).status_code == 422


def test_postgres_category_relationship_and_explicit_parent_clear(catalog_pg):
    state = catalog_pg
    parent = ProductCategory(id=f"parent-{state.marker}", tenant_id=state.tenant_a, name="Pizzas")
    other = ProductCategory(id=f"other-{state.marker}", tenant_id=state.tenant_a, name="Bebidas")
    state.db.add_all([parent, other])
    state.db.flush()
    child = ProductCategory(id=f"child-{state.marker}", tenant_id=state.tenant_a, parent_id=parent.id, name="Doces")
    state.db.add(child)
    state.db.flush()
    service = ProductCatalogService(state.db, state.context)
    with pytest.raises(Exception) as error:
        service.create(ProductCreate(name="Invalid", description="", price=1, category="Bebidas", subcategory="Doces"))
    assert error.value.status_code == 422
    product = service.create(ProductCreate(name="Valid", description="", price=1, category="Pizzas", subcategory="Doces"))
    update_category(state.db, child.id, ProductCategoryUpdate(parent_id=None), state.context)
    state.db.refresh(product)
    assert child.parent_id is None
    assert product.category == "Doces" and product.subcategory is None


def test_postgres_promotion_rejects_foreign_options_before_persistence(catalog_pg):
    state = catalog_pg
    state.membership.role = "owner"
    product, foreign = _product(state), _product(state, tenant=state.tenant_b)
    size = ProductSize(id=f"foreign-size-{state.marker}", tenant_id=state.tenant_b, product_id=foreign.id, label="Grande", price=80)
    state.db.add(size)
    state.db.flush()
    response = state.client.post(f"/api/products/{product.id}/promotions", json={
        "name": "Invalid", "combinations": [{"product_size_id": size.id}],
    })
    assert response.status_code == 422, response.text
    count = state.db.execute(text("SELECT count(*) FROM product_promotions WHERE product_id=:id"), {"id": product.id}).scalar()
    assert count == 0

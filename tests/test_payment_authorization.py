import inspect
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.core.tenant_context import TenantContext, TenantSource
from backend.routes import admin as admin_routes
from backend.routes import order_access


def _permission_from_endpoint(endpoint):
    dependency = inspect.signature(endpoint).parameters["_payment_permission"].default
    return dependency.dependency.__closure__[0].cell_contents, dependency.dependency.__closure__[1].cell_contents


def test_admin_order_access_rejects_expected_tenant_mismatch(monkeypatch):
    admin = SimpleNamespace(id="admin-a")
    order = SimpleNamespace(customer_id=None)
    customer_fallback_called = False

    monkeypatch.setattr(order_access, "authenticate_admin_token", lambda **_: admin)
    monkeypatch.setattr(
        order_access,
        "get_current_tenant_context",
        lambda **_: TenantContext(
            tenant_id="tenant-b",
            source=TenantSource.PANEL,
            actor_id="admin-a",
            membership_id="membership-b",
        ),
    )

    def fail_customer_fallback(*args, **kwargs):
        nonlocal customer_fallback_called
        customer_fallback_called = True
        raise AssertionError("tenant mismatch must not fall through to customer auth")

    monkeypatch.setattr(order_access, "require_customer_id_or_admin", fail_customer_fallback)

    with pytest.raises(HTTPException) as exc_info:
        order_access.require_order_or_admin(
            order,
            db=object(),
            authorization="Bearer admin-token",
            x_customer_phone=None,
            x_customer_email=None,
            expected_tenant_id="tenant-a",
        )

    assert exc_info.value.status_code == 403
    assert customer_fallback_called is False


def test_admin_order_access_accepts_expected_tenant_match(monkeypatch):
    admin = SimpleNamespace(id="admin-a")
    order = SimpleNamespace(customer_id=None)
    monkeypatch.setattr(order_access, "authenticate_admin_token", lambda **_: admin)
    monkeypatch.setattr(
        order_access,
        "get_current_tenant_context",
        lambda **_: TenantContext(
            tenant_id="tenant-a",
            source=TenantSource.PANEL,
            actor_id="admin-a",
            membership_id="membership-a",
        ),
    )

    order_access.require_order_or_admin(
        order,
        db=object(),
        authorization="Bearer admin-token",
        x_customer_phone=None,
        x_customer_email=None,
        expected_tenant_id="tenant-a",
    )


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        (admin_routes.get_payment_gateway_config, ("payments", "view")),
        (admin_routes.get_payment_gateways, ("payments", "view")),
        (admin_routes.get_payment_gateways_health, ("payments", "view")),
        (admin_routes.update_payment_gateway_config, ("payments", "edit")),
        (admin_routes.update_payment_gateway_routing, ("payments", "edit")),
        (admin_routes.update_payment_gateway_provider, ("payments", "edit")),
        (admin_routes.test_payment_gateway_provider, ("payments", "edit")),
    ],
)
def test_payment_gateway_routes_have_payment_rbac(endpoint, expected):
    assert _permission_from_endpoint(endpoint) == expected

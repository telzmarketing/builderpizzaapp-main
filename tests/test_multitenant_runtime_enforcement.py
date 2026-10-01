from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.core.tenant_context import TenantContextMissing
from backend.models.coupon import Coupon
from backend.models.customer import Customer
from backend.models.order import Order
from backend.models.product import ProductCategory
from backend.routes import products, promotions
from backend.services import agente_whatsapp_tools, customer_identity_service
from backend.services.agente_whatsapp_tools import AgenteWhatsAppToolService
from backend.services.customer_identity_service import CustomerIdentityService


ROOT = Path(__file__).resolve().parents[1]


class NoQueryDB:
    def query(self, *_args, **_kwargs):
        raise AssertionError("a consulta global nao deve ocorrer sem tenant")


def test_customer_identity_fails_closed_without_tenant(monkeypatch):
    monkeypatch.setattr(
        customer_identity_service, "customers_orders_enforcement_enabled", lambda: True
    )
    with pytest.raises(TenantContextMissing):
        CustomerIdentityService(NoQueryDB()).find_by_phone("11999999999")


def test_whatsapp_tool_fails_closed_without_session_or_panel_tenant(monkeypatch):
    monkeypatch.setattr(
        agente_whatsapp_tools, "identity_catalog_enforcement_enabled", lambda: True
    )
    monkeypatch.setattr(
        agente_whatsapp_tools, "customers_orders_enforcement_enabled", lambda: True
    )
    with pytest.raises(TenantContextMissing):
        AgenteWhatsAppToolService(NoQueryDB())._resolve_context(
            session_id=None, customer_id=None
        )


@pytest.mark.parametrize("module", [products, promotions])
def test_customer_bearer_is_not_misclassified_as_admin(monkeypatch, module):
    monkeypatch.setattr(module, "decode_access_token", lambda _token: {"token_kind": "customer"})
    request = SimpleNamespace(headers={"authorization": "Bearer customer-token"})
    assert module._has_admin_bearer(request) is False


def test_business_uniqueness_is_tenant_scoped_in_models():
    assert Customer.__table__.c.email.unique is not True
    assert Order.__table__.c.order_code.unique is not True
    assert ProductCategory.__table__.c.name.unique is not True
    assert Coupon.__table__.c.code.unique is not True
    assert "uq_coupons_tenant_code" in {index.name for index in Coupon.__table__.indexes}


def test_runtime_uniqueness_migration_preserves_webhook_safety():
    source = (
        ROOT
        / "backend/migrations/versions/20260930_tenant_runtime_uniqueness.py"
    ).read_text(encoding="utf-8")
    assert '"ix_orders_order_code"' in source
    assert '"payments_order_id_key"' not in source
    assert '"payments_mercado_pago_payment_id_key"' not in source

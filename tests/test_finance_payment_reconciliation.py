from importlib import import_module
from pkgutil import iter_modules

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import backend.models
from backend.database import Base
from backend.core.tenant_context import TenantContext, TenantSource
from backend.models.finance import FinanceTransaction
from backend.models.order import Order
from backend.models.payment import Payment
from backend.services.finance_service import FinanceService


for module in iter_modules(backend.models.__path__):
    import_module(f"backend.models.{module.name}")


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Order.__table__, Payment.__table__, FinanceTransaction.__table__])
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_payment_reconciliation_reports_projection_readiness_without_provider_inference(db):
    db.add_all([
        Order(id="order-a", tenant_id="tenant-a", subtotal=100, total=100, sales_channel="delivery", fulfillment_type="delivery"),
        Order(id="order-b", tenant_id="tenant-a", subtotal=50, total=50, sales_channel="delivery", fulfillment_type="delivery"),
        Order(id="order-c", tenant_id="tenant-b", subtotal=70, total=70, sales_channel="delivery", fulfillment_type="delivery"),
    ])
    db.add_all([
        Payment(id="payment-ready", tenant_id="tenant-a", order_id="order-a", method="pix", status="approved", amount=100, gateway="mock", provider="pix-provider", provider_payment_id="provider-1"),
        Payment(id="payment-missing", tenant_id="tenant-a", order_id="order-b", method="credit_card", status="paid", amount=50, gateway="mock", provider="card-provider", provider_payment_id="provider-2"),
        Payment(id="payment-other-tenant", tenant_id="tenant-b", order_id="order-c", method="pix", status="approved", amount=70, gateway="mock", provider="pix-provider", provider_payment_id="provider-3"),
    ])
    db.add(FinanceTransaction(
        id="finance-payment-ready", tenant_id="tenant-a", entry_type="income", status="paid",
        description="Venda confirmada", amount=100, paid_amount=100, fee_amount=2, net_amount=98,
        payment_id="payment-ready", origin_type="payment_receivable", origin_id="payment-ready",
    ))
    db.commit()

    context = TenantContext(tenant_id="tenant-a", source=TenantSource.JOB)
    result = FinanceService(db, "tenant-a", context).payment_reconciliation_readiness()

    assert result["total_count"] == 2
    assert result["confirmed_count"] == 2
    assert result["projected_count"] == 1
    assert result["missing_projection_count"] == 1
    assert result["total_gross_amount"] == 150
    assert result["total_linked_fee_amount"] == 2
    assert result["total_linked_net_amount"] == 98
    by_id = {item["payment_id"]: item for item in result["items"]}
    assert by_id["payment-ready"]["readiness"] == "projected"
    assert by_id["payment-ready"]["provider_payment_id"] == "provider-1"
    assert by_id["payment-missing"]["readiness"] == "missing_projection"
    assert "payment-other-tenant" not in by_id

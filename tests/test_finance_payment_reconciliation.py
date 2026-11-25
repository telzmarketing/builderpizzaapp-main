from datetime import date, datetime, timezone
from importlib import import_module
from pkgutil import iter_modules

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import backend.models
from backend.database import Base
from backend.core.tenant_context import TenantContext, TenantSource
from backend.core.exceptions import IdempotencyConflict
from backend.models.finance import (
    FinanceAccount, FinanceCategory, FinanceCounterparty, FinanceSettlement, FinanceTransaction,
)
from backend.models.gestao import GestaoModuleSettings
from backend.models.order import Order
from backend.models.payment import Payment
from backend.schemas.finance import FinancePaymentReconciliationIn
from backend.services.finance_service import FinanceInvalidReference, FinanceService


for module in iter_modules(backend.models.__path__):
    import_module(f"backend.models.{module.name}")


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            Order.__table__, Payment.__table__, FinanceAccount.__table__,
            FinanceCategory.__table__, FinanceCounterparty.__table__,
            FinanceTransaction.__table__, FinanceSettlement.__table__,
            GestaoModuleSettings.__table__,
        ],
    )
    with Session(engine) as session:
        session.add(FinanceAccount(id="account-a", tenant_id="tenant-a", name="Caixa A"))
        session.commit()
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


def test_cash_flow_includes_confirmed_unprojected_payment_once_and_respects_period(db):
    db.add_all([
        Order(id="order-cash-missing", tenant_id="tenant-a", subtotal=80, total=80, sales_channel="delivery", fulfillment_type="delivery", status="paid"),
        Order(id="order-cash-ready", tenant_id="tenant-a", subtotal=45, total=45, sales_channel="delivery", fulfillment_type="delivery", status="paid"),
        Order(id="order-cash-old", tenant_id="tenant-a", subtotal=30, total=30, sales_channel="delivery", fulfillment_type="delivery", status="paid"),
        Order(id="order-cash-pending", tenant_id="tenant-a", subtotal=25, total=25, sales_channel="delivery", fulfillment_type="delivery", status="paid"),
    ])
    db.add_all([
        Payment(id="payment-cash-missing", tenant_id="tenant-a", order_id="order-cash-missing", method="pix", status="approved", amount=80, created_at=datetime(2026, 11, 15, 12, tzinfo=timezone.utc)),
        Payment(id="payment-cash-ready", tenant_id="tenant-a", order_id="order-cash-ready", method="pix", status="paid", amount=45, created_at=datetime(2026, 11, 16, 12, tzinfo=timezone.utc)),
        Payment(id="payment-cash-old", tenant_id="tenant-a", order_id="order-cash-old", method="pix", status="approved", amount=30, created_at=datetime(2026, 10, 31, 12, tzinfo=timezone.utc)),
        Payment(id="payment-cash-pending", tenant_id="tenant-a", order_id="order-cash-pending", method="pix", status="pending", amount=25, created_at=datetime(2026, 11, 17, 12, tzinfo=timezone.utc)),
    ])
    db.add(FinanceTransaction(
        id="finance-cash-ready", tenant_id="tenant-a", entry_type="income", status="paid",
        description="Venda projetada", amount=45, paid_amount=45, net_amount=45,
        competence_date=date(2026, 11, 16), payment_id="payment-cash-ready",
        origin_type="payment_receivable", origin_id="payment-cash-ready",
    ))
    db.commit()

    result = FinanceService(db, "tenant-a", TenantContext(tenant_id="tenant-a", source=TenantSource.JOB)).cash_flow(
        date(2026, 11, 1), date(2026, 11, 30),
    )

    sale_lines = [line for line in result["lines"] if line["entry_type"] == "income"]
    assert [line["id"] for line in sale_lines] == ["finance-cash-ready", "payment:payment-cash-missing"]
    assert result["realized_income"] == 125.0
    assert result["projected_income"] == 125.0
    assert "payment:payment-cash-old" not in {line["id"] for line in result["lines"]}
    assert "payment:payment-cash-pending" not in {line["id"] for line in result["lines"]}


def test_external_payment_reconciliation_is_idempotent_non_posting_and_tenant_scoped(db):
    db.add_all([
        Order(id="order-card-a", tenant_id="tenant-a", subtotal=100, total=100, sales_channel="delivery", fulfillment_type="delivery"),
        Order(id="order-card-b", tenant_id="tenant-b", subtotal=100, total=100, sales_channel="delivery", fulfillment_type="delivery"),
        Payment(id="payment-card-a", tenant_id="tenant-a", order_id="order-card-a", method="credit_card", status="approved", amount=100, gateway="mp", provider="mercadopago", provider_payment_id="mp-1"),
        Payment(id="payment-card-b", tenant_id="tenant-b", order_id="order-card-b", method="pix", status="approved", amount=100, gateway="mp", provider="mercadopago", provider_payment_id="mp-2"),
        FinanceTransaction(id="finance-card-a", tenant_id="tenant-a", entry_type="income", status="paid", description="Receita", amount=100, paid_amount=100, net_amount=100, payment_id="payment-card-a", origin_type="payment_receivable", origin_id="payment-card-a"),
        FinanceTransaction(id="finance-card-b", tenant_id="tenant-b", entry_type="income", status="paid", description="Receita", amount=100, paid_amount=100, net_amount=100, payment_id="payment-card-b", origin_type="payment_receivable", origin_id="payment-card-b"),
    ])
    db.commit()
    svc = FinanceService(db, "tenant-a", TenantContext(tenant_id="tenant-a", source=TenantSource.JOB))
    payload = FinancePaymentReconciliationIn(
        payment_id="payment-card-a",
        external_reference="settlement-001",
        fee_amount="2.50",
        net_amount="97.50",
    )

    first = svc.create_payment_reconciliation(payload, "key-001", "admin-a")
    second = svc.create_payment_reconciliation(payload, "key-001", "admin-a")
    listed = svc.list_payment_reconciliations()

    assert first["id"] == second["id"]
    assert first["gross_amount"] == 100
    assert first["fee_amount"] == 2.50
    assert first["net_amount"] == 97.50
    assert first["acquirer_confirmed"] is False
    assert first["evidence_status"] == "recorded_not_acquirer_confirmed"
    assert db.query(FinanceSettlement).filter(FinanceSettlement.origin_type == "payment_reconciliation").count() == 1
    assert db.get(FinanceSettlement, first["id"]).account_id is None
    assert listed["total_count"] == 1
    assert listed["items"][0]["payment_id"] == "payment-card-a"

    with pytest.raises(IdempotencyConflict):
        svc.create_payment_reconciliation(
            payload.model_copy(update={"net_amount": "96.50"}), "key-001", "admin-a"
        )
    assert FinanceService(db, "tenant-b", TenantContext(tenant_id="tenant-b", source=TenantSource.JOB)).list_payment_reconciliations()["total_count"] == 0


def test_external_payment_reconciliation_requires_projection_and_exact_net(db):
    db.add(Order(id="order-unprojected", tenant_id="tenant-a", subtotal=100, total=100, sales_channel="delivery", fulfillment_type="delivery"))
    db.add(Payment(id="payment-unprojected", tenant_id="tenant-a", order_id="order-unprojected", method="pix", status="approved", amount=100, gateway="mp"))
    db.commit()
    svc = FinanceService(db, "tenant-a", TenantContext(tenant_id="tenant-a", source=TenantSource.JOB))
    with pytest.raises(FinanceInvalidReference, match="projecao"):
        svc.create_payment_reconciliation(FinancePaymentReconciliationIn(payment_id="payment-unprojected", external_reference="x", fee_amount=1, net_amount=99), "key-unprojected")

    db.add(FinanceTransaction(id="finance-unprojected", tenant_id="tenant-a", entry_type="income", status="paid", description="Receita", amount=100, paid_amount=100, net_amount=100, payment_id="payment-unprojected", origin_type="payment_receivable", origin_id="payment-unprojected"))
    db.commit()
    with pytest.raises(FinanceInvalidReference, match="liquido"):
        svc.create_payment_reconciliation(FinancePaymentReconciliationIn(payment_id="payment-unprojected", external_reference="x", fee_amount=1, net_amount=98), "key-net")


def test_sales_backfill_merges_legacy_settings_is_idempotent_and_is_tenant_scoped(db):
    db.add_all([
        GestaoModuleSettings(
            id="finance-settings-a",
            tenant_id="tenant-a",
            module_key="finance",
            title="Financeiro",
            description="",
            enabled=True,
            status="active",
            # Legacy payload intentionally omits auto_create_receivables.
            settings_json='{"cash_basis_enabled": false}',
        ),
        GestaoModuleSettings(
            id="finance-settings-b",
            tenant_id="tenant-b",
            module_key="finance",
            title="Financeiro",
            description="",
            enabled=True,
            status="active",
            settings_json='{"auto_create_receivables": false}',
        ),
        Order(
            id="order-legacy-settings-a",
            tenant_id="tenant-a",
            subtotal=80,
            total=80,
            sales_channel="delivery",
            fulfillment_type="delivery",
            status="paid",
        ),
        Order(
            id="order-legacy-settings-b",
            tenant_id="tenant-b",
            subtotal=90,
            total=90,
            sales_channel="delivery",
            fulfillment_type="delivery",
            status="paid",
        ),
        Payment(
            id="payment-legacy-settings-a",
            tenant_id="tenant-a",
            order_id="order-legacy-settings-a",
            method="pix",
            status="approved",
            amount=80,
            gateway="test",
        ),
        Payment(
            id="payment-legacy-settings-b",
            tenant_id="tenant-b",
            order_id="order-legacy-settings-b",
            method="pix",
            status="approved",
            amount=90,
            gateway="test",
        ),
    ])
    db.commit()

    service_a = FinanceService(
        db, "tenant-a", TenantContext(tenant_id="tenant-a", source=TenantSource.JOB)
    )
    first = service_a.backfill_sales()
    second = service_a.backfill_sales()

    assert first["created"] == 1
    assert first["failed"] == 0
    assert second["created"] == 0
    assert second["already_synced"] == 1
    assert db.query(FinanceTransaction).filter(
        FinanceTransaction.tenant_id == "tenant-a",
        FinanceTransaction.payment_id == "payment-legacy-settings-a",
    ).count() == 1
    assert db.query(FinanceTransaction).filter(
        FinanceTransaction.payment_id == "payment-legacy-settings-b",
    ).count() == 0

    merged = service_a._module_settings()
    assert merged["auto_create_receivables"] is True
    assert merged["cash_basis_enabled"] is False

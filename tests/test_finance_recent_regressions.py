"""Focused regressions for the recent finance projection changes."""

from datetime import date
from decimal import Decimal
from importlib import import_module
from pkgutil import iter_modules

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import backend.models
from backend.core.tenant_context import TenantContext, TenantSource
from backend.database import Base
from backend.models.finance import (
    FinanceAccount, FinanceCategory,
    FinanceObligation,
    FinanceObligationInstallment,
    FinanceSettlement,
    FinanceTransaction,
)
from backend.models.inventory import InventoryPurchase
from backend.models.inventory_receipts import InventoryReceiptDocument
from backend.models.order import Order
from backend.models.payment import Payment, PaymentMethod, PaymentStatus
from backend.models.delivery import DeliveryDailyAllowance, DeliveryEarning
from backend.models.cmv import OrderCmvSnapshot
from backend.models.gestao import GestaoModuleSettings
from backend.models.idempotency import IdempotencyKey
from backend.services.finance_service import FinanceService
from backend.services.inventory_receipt_service import InventoryReceiptService


for module in iter_modules(backend.models.__path__):
    import_module(f"backend.models.{module.name}")


TENANT = "tenant-finance-regressions"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    # Keep the fixture limited to the finance projection graph. Creating the
    # whole application metadata would also pull in unrelated optional models
    # whose legacy foreign keys are not part of these regressions.
    tables = [
        FinanceCategory.__table__,
        FinanceAccount.__table__,
        FinanceObligation.__table__,
        FinanceObligationInstallment.__table__,
        FinanceSettlement.__table__,
        FinanceTransaction.__table__,
        InventoryPurchase.__table__,
        InventoryReceiptDocument.__table__,
        IdempotencyKey.__table__,
        Payment.__table__,
        Order.__table__,
        DeliveryDailyAllowance.__table__,
        DeliveryEarning.__table__,
        OrderCmvSnapshot.__table__,
        GestaoModuleSettings.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    with Session(engine) as session:
        yield session
    engine.dispose()


def finance_service(db):
    context = TenantContext(tenant_id=TENANT, source=TenantSource.JOB)
    return FinanceService(db, TENANT, context)


def test_incomplete_finance_settings_enable_idempotent_sales_projection_for_tenant(db):
    db.add(GestaoModuleSettings(
        id="finance-settings-incomplete", tenant_id=TENANT, module_key="finance",
        title="Financeiro", description="", enabled=True, status="active",
        settings_json='{"dre_enabled": true}', notes="",
    ))
    db.add(Order(
        id="sales-order-1", tenant_id=TENANT, status="paid", order_origin="own",
        fulfillment_type="delivery", sales_channel="delivery", subtotal=100.0,
        total=100.0, discount=0.0,
    ))
    db.add(Payment(
        id="sales-payment-1", tenant_id=TENANT, order_id="sales-order-1",
        method=PaymentMethod.pix, status=PaymentStatus.paid, amount=100.0,
        paid_at=date(2026, 11, 25),
    ))
    db.commit()

    service = finance_service(db)
    settings = service._module_settings()
    assert settings["auto_create_receivables"] is True
    assert settings["dre_enabled"] is True

    first = service.sync_payment_confirmed(
        payment_id="sales-payment-1", order_id="sales-order-1", amount=100.0,
        gateway="mock",
    )
    second = service.sync_payment_confirmed(
        payment_id="sales-payment-1", order_id="sales-order-1", amount=100.0,
        gateway="mock",
    )
    backfill = service.backfill_sales()

    rows = db.query(FinanceTransaction).filter(
        FinanceTransaction.tenant_id == TENANT,
        FinanceTransaction.origin_type == "payment_receivable",
        FinanceTransaction.origin_id == "sales-payment-1",
    ).all()
    assert first["created"] is True, first
    assert second["reason"] == "already_synced"
    assert backfill["already_synced"] == 1
    assert len(rows) == 1
    assert rows[0].tenant_id == TENANT
    assert rows[0].amount == 100.0


def test_incompatible_partial_reversal_keeps_receivable_and_settlement_active(db):
    transaction = FinanceTransaction(
        id="finance-sale-1",
        tenant_id=TENANT,
        entry_type="income",
        status="paid",
        description="Venda confirmada",
        amount=100.0,
        paid_amount=100.0,
        net_amount=100.0,
        payment_id="payment-1",
        origin_type="payment_receivable",
        origin_id="payment-1",
    )
    settlement = FinanceSettlement(
        id="finance-sale-settlement-1",
        tenant_id=TENANT,
        transaction_id=transaction.id,
        principal_amount=100.0,
        net_amount=100.0,
        origin_type="payment_confirmed",
        origin_id="payment-1",
        idempotency_key="payment-confirmed:payment-1",
    )
    db.add_all([transaction, settlement])
    db.commit()

    result = finance_service(db).sync_payment_reversed(
        payment_id="payment-1",
        order_id="order-1",
        amount=40.0,
        gateway="test",
    )

    db.expire_all()
    refreshed = db.get(FinanceTransaction, transaction.id)
    active_settlement = db.get(FinanceSettlement, settlement.id)
    assert result["reversed"] is False
    assert result["reason"] == "partial_reversal_requires_reconciliation"
    assert refreshed.status == "paid"
    assert refreshed.paid_amount == 100.0
    assert active_settlement.cancelled_at is None
    assert db.query(FinanceSettlement).filter(
        FinanceSettlement.origin_type == "payment_reversed"
    ).count() == 0


def test_receipt_reconciliation_supersedes_pending_purchase_payable_without_duplicate(db):
    purchase = InventoryPurchase(
        id="purchase-1",
        tenant_id=TENANT,
        status="confirmed",
        title="Compra 24-11-2026-001",
        purchase_date=date(2026, 11, 24),
        daily_sequence=1,
        total_amount=Decimal("100.00"),
    )
    receipt = InventoryReceiptDocument(
        id="receipt-1",
        tenant_id=TENANT,
        purchase_id=purchase.id,
        status="validated",
        document_model="NFe",
        content_sha256="a" * 64,
        extracted_json={"total_document": "100.00"},
    )
    preliminary = FinanceTransaction(
        id="purchase-payable-1",
        tenant_id=TENANT,
        inventory_purchase_id=purchase.id,
        origin_type="inventory_purchase_payable",
        origin_id=purchase.id,
        entry_type="expense",
        status="pending",
        description="Conta preliminar da compra",
        amount=100.0,
    )
    db.add_all([purchase, receipt, preliminary])
    db.commit()

    result = InventoryReceiptService(db, TENANT, "admin-1").reconcile(
        receipt.id,
        {"installments": [{"amount": "100.00"}]},
        "receipt-reconcile-1",
    )

    db.expire_all()
    obligations = db.query(FinanceObligation).filter(
        FinanceObligation.tenant_id == TENANT,
        FinanceObligation.receipt_document_id == receipt.id,
    ).all()
    receipt_transactions = db.query(FinanceTransaction).filter(
        FinanceTransaction.tenant_id == TENANT,
        FinanceTransaction.origin_type == "inventory_receipt_payable",
        FinanceTransaction.origin_id == receipt.id,
    ).all()
    refreshed_preliminary = db.get(FinanceTransaction, preliminary.id)

    assert result["status"] == "linked"
    assert len(obligations) == 1
    assert len(receipt_transactions) == 1
    assert refreshed_preliminary.status == "cancelled"
    assert "Substituida pela obrigacao" in refreshed_preliminary.notes
    assert db.query(FinanceTransaction).filter(
        FinanceTransaction.inventory_purchase_id == purchase.id,
        FinanceTransaction.origin_type == "inventory_purchase_payable",
        FinanceTransaction.status != "cancelled",
    ).count() == 0


def test_projection_health_accepts_purchase_reconciled_by_active_receipt_obligation(db):
    purchase = InventoryPurchase(
        id="purchase-health-1",
        tenant_id=TENANT,
        status="confirmed",
        title="Compra 24-11-2026-002",
        purchase_date=date(2026, 11, 24),
        daily_sequence=2,
        total_amount=Decimal("75.00"),
    )
    receipt = InventoryReceiptDocument(
        id="receipt-health-1",
        tenant_id=TENANT,
        purchase_id=purchase.id,
        status="validated",
        document_model="NFe",
        content_sha256="b" * 64,
        extracted_json={"total_document": "75.00"},
    )
    obligation = FinanceObligation(
        id="obligation-health-1",
        tenant_id=TENANT,
        receipt_document_id=receipt.id,
        idempotency_key="receipt-health-key",
        status="pending",
        total_amount=Decimal("75.00"),
        product_amount=Decimal("75.00"),
    )
    receipt_transaction = FinanceTransaction(
        id="receipt-health-transaction-1",
        tenant_id=TENANT,
        inventory_purchase_id=purchase.id,
        origin_type="inventory_receipt_payable",
        origin_id=receipt.id,
        entry_type="expense",
        status="pending",
        description="Conta da NF-e",
        amount=75.0,
    )
    db.add_all([purchase, receipt, obligation, receipt_transaction])
    db.commit()

    health = finance_service(db).projection_health()

    assert health["status"] == "healthy"
    assert health["checked_purchases"] == 1
    assert health["missing_purchase_payables_count"] == 0
    assert purchase.id not in health["missing_purchase_ids"]

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.core.tenant_context import TenantContext
from backend.models.finance import FinanceObligation
from backend.models.inventory import InventoryPurchase, InventoryStockMovement
from backend.models.purchase_quotation import PurchaseQuotation
from backend.models.purchase_receipt import PurchaseReceipt, PurchaseReceiptItem
from backend.models.purchase_requisition import PurchaseRequisition

class PurchaseDashboardService:
    def __init__(self, db: Session, context: TenantContext):
        self.db, self.tenant_id = db, context.tenant_id

    @staticmethod
    def _bounds(date_from: date | None, date_to: date | None) -> tuple[date, date]:
        end = date_to or datetime.now(timezone.utc).date()
        start = date_from or (end - timedelta(days=29))
        if start > end:
            raise ValueError("date_from nao pode ser posterior a date_to")
        if end - start > timedelta(days=366):
            raise ValueError("o periodo maximo do dashboard e de 366 dias")
        return start, end

    def _status_counts(self, model, column, start: date, end: date) -> dict[str, int]:
        rows = self.db.query(model.status, func.count(model.id)).filter(
            model.tenant_id == self.tenant_id,
            column >= start,
            column < end + timedelta(days=1),
        ).group_by(model.status).all()
        return {str(status): int(total) for status, total in rows}

    def dashboard(self, date_from: date | None = None, date_to: date | None = None) -> dict:
        start, end = self._bounds(date_from, date_to)
        requisitions_status = self._status_counts(PurchaseRequisition, PurchaseRequisition.created_at, start, end)
        quotations_status = self._status_counts(PurchaseQuotation, PurchaseQuotation.created_at, start, end)
        orders_status = self._status_counts(InventoryPurchase, InventoryPurchase.purchase_date, start, end)
        receipts_status = self._status_counts(PurchaseReceipt, PurchaseReceipt.received_at, start, end)
        order_amount = self.db.query(func.coalesce(func.sum(InventoryPurchase.total_amount), 0)).filter(
            InventoryPurchase.tenant_id == self.tenant_id,
            InventoryPurchase.purchase_date >= start,
            InventoryPurchase.purchase_date < end + timedelta(days=1),
        ).scalar()
        receipt_totals = self.db.query(
            func.coalesce(func.sum(PurchaseReceiptItem.quantity_received), 0),
            func.coalesce(func.sum(PurchaseReceiptItem.quantity_rejected), 0),
        ).join(PurchaseReceipt, PurchaseReceipt.id == PurchaseReceiptItem.receipt_id).filter(
            PurchaseReceipt.tenant_id == self.tenant_id,
            PurchaseReceipt.status == "posted",
            PurchaseReceipt.received_at >= datetime.combine(start, time.min, tzinfo=timezone.utc),
            PurchaseReceipt.received_at < datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc),
        ).one()
        movements = self.db.query(
            func.count(InventoryStockMovement.id),
            func.coalesce(func.sum(InventoryStockMovement.quantity_delta), 0),
            func.coalesce(func.sum(InventoryStockMovement.quantity_delta * InventoryStockMovement.unit_cost), 0),
        ).filter(
            InventoryStockMovement.tenant_id == self.tenant_id,
            InventoryStockMovement.source_type == "receipt",
            InventoryStockMovement.quantity_delta > 0,
            InventoryStockMovement.created_at >= datetime.combine(start, time.min, tzinfo=timezone.utc),
            InventoryStockMovement.created_at < datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc),
        ).one()
        finance_rows = self.db.query(
            func.count(FinanceObligation.id),
            func.coalesce(func.sum(FinanceObligation.total_amount), 0),
        ).filter(
            FinanceObligation.tenant_id == self.tenant_id,
            FinanceObligation.receipt_document_id.isnot(None),
            FinanceObligation.created_at >= datetime.combine(start, time.min, tzinfo=timezone.utc),
            FinanceObligation.created_at < datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc),
        ).one()
        finance_split = self.db.query(FinanceObligation.status, func.coalesce(func.sum(FinanceObligation.total_amount), 0)).filter(
            FinanceObligation.tenant_id == self.tenant_id,
            FinanceObligation.receipt_document_id.isnot(None),
            FinanceObligation.created_at >= datetime.combine(start, time.min, tzinfo=timezone.utc),
            FinanceObligation.created_at < datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc),
        ).group_by(FinanceObligation.status).all()
        split = {str(status): Decimal(str(amount or 0)) for status, amount in finance_split}
        today = datetime.now(timezone.utc).date()
        overdue_quotations = self.db.query(func.count(PurchaseQuotation.id)).filter(PurchaseQuotation.tenant_id == self.tenant_id, PurchaseQuotation.status.in_(["open", "closed"]), PurchaseQuotation.response_due < today).scalar() or 0
        overdue_orders = self.db.query(func.count(InventoryPurchase.id)).filter(InventoryPurchase.tenant_id == self.tenant_id, InventoryPurchase.status.in_(["requested", "confirmed"]), InventoryPurchase.expected_date < today).scalar() or 0
        pending_requisitions = self.db.query(func.count(PurchaseRequisition.id)).filter(PurchaseRequisition.tenant_id == self.tenant_id, PurchaseRequisition.status.in_(["submitted", "approved", "sourcing"])).scalar() or 0
        return {
            "period": {"date_from": start, "date_to": end, "generated_at": datetime.now(timezone.utc)},
            "requisitions": {"total": sum(requisitions_status.values()), "by_status": requisitions_status},
            "quotations": {"total": sum(quotations_status.values()), "by_status": quotations_status},
            "orders": {"total": sum(orders_status.values()), "by_status": orders_status, "total_amount": Decimal(str(order_amount or 0))},
            "receipts": {"total": sum(receipts_status.values()), "by_status": receipts_status, "posted": receipts_status.get("posted", 0), "quantity_received": Decimal(str(receipt_totals[0] or 0)), "quantity_rejected": Decimal(str(receipt_totals[1] or 0))},
            "inventory": {"movement_count": int(movements[0] or 0), "quantity_in": Decimal(str(movements[1] or 0)), "received_value": Decimal(str(movements[2] or 0))},
            "finance": {"obligation_count": int(finance_rows[0] or 0), "total_amount": Decimal(str(finance_rows[1] or 0)), "pending_amount": split.get("pending", Decimal("0")) + split.get("partial", Decimal("0")), "paid_amount": split.get("paid", Decimal("0"))},
            "alerts": {"overdue_quotations": int(overdue_quotations), "overdue_orders": int(overdue_orders), "pending_requisitions": int(pending_requisitions)},
        }

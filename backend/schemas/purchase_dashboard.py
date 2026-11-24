from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel

class PurchaseDashboardPeriod(BaseModel):
    date_from: date
    date_to: date
    generated_at: datetime

class PurchaseDashboardSection(BaseModel):
    total: int
    by_status: dict[str, int]

class PurchaseDashboardOrders(PurchaseDashboardSection):
    total_amount: Decimal

class PurchaseDashboardReceipts(PurchaseDashboardSection):
    posted: int
    quantity_received: Decimal
    quantity_rejected: Decimal

class PurchaseDashboardInventory(BaseModel):
    movement_count: int
    quantity_in: Decimal
    received_value: Decimal

class PurchaseDashboardFinance(BaseModel):
    obligation_count: int
    total_amount: Decimal
    pending_amount: Decimal
    paid_amount: Decimal

class PurchaseDashboardAlerts(BaseModel):
    overdue_quotations: int
    overdue_orders: int
    pending_requisitions: int

class PurchaseDashboardOut(BaseModel):
    period: PurchaseDashboardPeriod
    requisitions: PurchaseDashboardSection
    quotations: PurchaseDashboardSection
    orders: PurchaseDashboardOrders
    receipts: PurchaseDashboardReceipts
    inventory: PurchaseDashboardInventory
    finance: PurchaseDashboardFinance
    alerts: PurchaseDashboardAlerts

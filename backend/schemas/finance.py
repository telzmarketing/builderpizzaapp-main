from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

FinanceAccountType = Literal["cash", "bank", "credit_card", "wallet", "other"]
FinanceEntryType = Literal["income", "expense"]
FinanceTransactionStatus = Literal["pending", "partial", "paid", "cancelled"]
FinanceCounterpartyType = Literal["supplier", "customer", "employee", "partner", "other"]


class FinanceAccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=140)
    account_type: FinanceAccountType = "bank"
    opening_balance: float = 0.0
    notes: str | None = None
    active: bool = True


class FinanceAccountOut(FinanceAccountIn):
    id: str
    tenant_id: str
    current_balance: float = 0.0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FinanceCategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=140)
    entry_type: FinanceEntryType = "expense"
    dre_group: str = Field(default="operational", min_length=1, max_length=80)
    parent_id: str | None = None
    notes: str | None = None
    active: bool = True


class FinanceCategoryOut(FinanceCategoryIn):
    id: str
    tenant_id: str
    parent_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FinanceCounterpartyIn(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    counterparty_type: FinanceCounterpartyType = "supplier"
    document: str | None = Field(default=None, max_length=40)
    phone: str | None = Field(default=None, max_length=40)
    email: str | None = Field(default=None, max_length=180)
    notes: str | None = None
    active: bool = True


class FinanceCounterpartyOut(FinanceCounterpartyIn):
    id: str
    tenant_id: str
    open_amount: float = 0.0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FinanceTransactionIn(BaseModel):
    account_id: str | None = None
    category_id: str | None = None
    cost_center: str | None = Field(default=None, max_length=120)
    counterparty_id: str | None = None
    counterparty_type: FinanceCounterpartyType | None = None
    counterparty_name: str | None = Field(default=None, max_length=180)
    counterparty_document: str | None = Field(default=None, max_length=40)
    entry_type: FinanceEntryType = "expense"
    status: FinanceTransactionStatus = "pending"
    description: str = Field(min_length=1, max_length=220)
    amount: float = Field(gt=0)
    paid_amount: float = Field(default=0.0, ge=0)
    interest_amount: float = Field(default=0.0, ge=0)
    fine_amount: float = Field(default=0.0, ge=0)
    discount_amount: float = Field(default=0.0, ge=0)
    fee_amount: float = Field(default=0.0, ge=0)
    net_amount: float = Field(default=0.0, ge=0)
    competence_date: date
    due_date: date | None = None
    paid_at: datetime | None = None
    document_number: str | None = Field(default=None, max_length=80)
    document_date: date | None = None
    payment_method: str | None = Field(default=None, max_length=40)
    payment_reference: str | None = Field(default=None, max_length=120)
    installment_group_id: str | None = None
    installment_number: int = Field(default=1, ge=1)
    installment_total: int = Field(default=1, ge=1)
    order_id: str | None = None
    payment_id: str | None = None
    inventory_purchase_id: str | None = None
    origin_type: str = Field(default="manual", max_length=60)
    origin_id: str | None = None
    notes: str | None = None


class FinanceSettlementIn(BaseModel):
    account_id: str | None = None
    paid_amount: float | None = Field(default=None, gt=0)
    paid_at: datetime | None = None
    interest_amount: float = Field(default=0.0, ge=0)
    fine_amount: float = Field(default=0.0, ge=0)
    discount_amount: float = Field(default=0.0, ge=0)
    fee_amount: float = Field(default=0.0, ge=0)
    payment_method: str | None = Field(default=None, max_length=40)
    payment_reference: str | None = Field(default=None, max_length=120)
    notes: str | None = None


class FinanceTransactionOut(FinanceTransactionIn):
    id: str
    tenant_id: str
    account_name: str | None = None
    category_name: str | None = None
    cost_center: str | None = None
    counterparty_name: str | None = None
    created_by_admin_id: str | None = None
    updated_by_admin_id: str | None = None
    overdue: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class FinanceSummaryOut(BaseModel):
    income_paid: float
    expense_paid: float
    income_pending: float
    expense_pending: float
    balance: float
    overdue_count: int
    pending_count: int


class FinanceDreLineOut(BaseModel):
    group: str
    entry_type: FinanceEntryType
    amount: float


class FinanceOriginSummaryOut(BaseModel):
    origin_type: str
    entry_type: FinanceEntryType
    amount: float
    count: int


class FinanceDimensionSummaryOut(BaseModel):
    label: str
    entry_type: FinanceEntryType
    amount: float
    count: int


class FinanceManagementOut(BaseModel):
    cash_realized_income: float
    cash_realized_expense: float
    cash_realized_result: float
    accrual_income: float
    accrual_expense: float
    accrual_result: float
    dre_status: str
    dre_label: str
    dre_lines: list[FinanceDreLineOut]
    by_origin: list[FinanceOriginSummaryOut]
    by_category: list[FinanceDimensionSummaryOut]
    by_cost_center: list[FinanceDimensionSummaryOut]
    by_channel: list[FinanceDimensionSummaryOut]


class FinanceOverviewOut(BaseModel):
    summary: FinanceSummaryOut
    management: FinanceManagementOut
    accounts: list[FinanceAccountOut]
    categories: list[FinanceCategoryOut]
    counterparties: list[FinanceCounterpartyOut]
    transactions: list[FinanceTransactionOut]

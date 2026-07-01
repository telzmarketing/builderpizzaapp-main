from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class FinanceAccount(Base):
    __tablename__ = "finance_accounts"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    name = Column(String(140), nullable=False)
    account_type = Column(String(40), nullable=False, default="bank")
    opening_balance = Column(Float, nullable=False, default=0.0)
    notes = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    transactions = relationship("FinanceTransaction", back_populates="account")


class FinanceCategory(Base):
    __tablename__ = "finance_categories"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    name = Column(String(140), nullable=False)
    entry_type = Column(String(20), nullable=False, default="expense", index=True)
    dre_group = Column(String(80), nullable=False, default="operational")
    parent_id = Column(String, ForeignKey("finance_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    parent = relationship("FinanceCategory", remote_side=[id])
    transactions = relationship("FinanceTransaction", back_populates="category")


class FinanceCounterparty(Base):
    __tablename__ = "finance_counterparties"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    name = Column(String(180), nullable=False)
    counterparty_type = Column(String(40), nullable=False, default="supplier", index=True)
    document = Column(String(40), nullable=True, index=True)
    phone = Column(String(40), nullable=True)
    email = Column(String(180), nullable=True)
    notes = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    transactions = relationship("FinanceTransaction", back_populates="counterparty")


class FinanceTransaction(Base):
    __tablename__ = "finance_transactions"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    account_id = Column(String, ForeignKey("finance_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    category_id = Column(String, ForeignKey("finance_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    cost_center = Column(String(120), nullable=True, index=True)
    counterparty_id = Column(String, ForeignKey("finance_counterparties.id", ondelete="SET NULL"), nullable=True, index=True)
    counterparty_type = Column(String(40), nullable=True, index=True)
    counterparty_name = Column(String(180), nullable=True)
    counterparty_document = Column(String(40), nullable=True, index=True)
    entry_type = Column(String(20), nullable=False, default="expense", index=True)
    status = Column(String(20), nullable=False, default="pending", index=True)
    description = Column(String(220), nullable=False)
    amount = Column(Float, nullable=False, default=0.0)
    paid_amount = Column(Float, nullable=False, default=0.0)
    interest_amount = Column(Float, nullable=False, default=0.0)
    fine_amount = Column(Float, nullable=False, default=0.0)
    discount_amount = Column(Float, nullable=False, default=0.0)
    fee_amount = Column(Float, nullable=False, default=0.0)
    net_amount = Column(Float, nullable=False, default=0.0)
    competence_date = Column(Date, nullable=False, default=date.today, index=True)
    due_date = Column(Date, nullable=True, index=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    document_number = Column(String(80), nullable=True, index=True)
    document_date = Column(Date, nullable=True, index=True)
    payment_method = Column(String(40), nullable=True, index=True)
    payment_reference = Column(String(120), nullable=True, index=True)
    installment_group_id = Column(String, nullable=True, index=True)
    installment_number = Column(Integer, nullable=False, default=1)
    installment_total = Column(Integer, nullable=False, default=1)
    order_id = Column(String, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    payment_id = Column(String, ForeignKey("payments.id", ondelete="SET NULL"), nullable=True, index=True)
    inventory_purchase_id = Column(String, ForeignKey("inventory_purchases.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True, index=True)
    updated_by_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True, index=True)
    origin_type = Column(String(60), nullable=False, default="manual", index=True)
    origin_id = Column(String, nullable=True, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    account = relationship("FinanceAccount", back_populates="transactions")
    category = relationship("FinanceCategory", back_populates="transactions")
    counterparty = relationship("FinanceCounterparty", back_populates="transactions")
    settlements = relationship("FinanceSettlement", cascade="all, delete-orphan", back_populates="transaction")
    order = relationship("Order")
    payment = relationship("Payment")
    inventory_purchase = relationship("InventoryPurchase")


class FinanceSettlement(Base):
    __tablename__ = "finance_settlements"

    id = Column(String, primary_key=True)
    tenant_id = Column(String(80), nullable=False, default="default", index=True)
    transaction_id = Column(String, ForeignKey("finance_transactions.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(String, ForeignKey("finance_accounts.id", ondelete="SET NULL"), nullable=True, index=True)
    settled_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    principal_amount = Column(Float, nullable=False, default=0.0)
    interest_amount = Column(Float, nullable=False, default=0.0)
    fine_amount = Column(Float, nullable=False, default=0.0)
    discount_amount = Column(Float, nullable=False, default=0.0)
    fee_amount = Column(Float, nullable=False, default=0.0)
    net_amount = Column(Float, nullable=False, default=0.0)
    payment_method = Column(String(40), nullable=True, index=True)
    payment_reference = Column(String(120), nullable=True, index=True)
    created_by_admin_id = Column(String, ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True, index=True)
    origin_type = Column(String(60), nullable=False, default="manual", index=True)
    origin_id = Column(String, nullable=True, index=True)
    idempotency_key = Column(String(160), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    transaction = relationship("FinanceTransaction", back_populates="settlements")
    account = relationship("FinanceAccount")

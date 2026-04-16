from sqlalchemy import Column, String, Float, Boolean, Integer, Enum, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from backend.database import Base


class TransactionType(str, enum.Enum):
    earned = "earned"
    redeemed = "redeemed"


class LoyaltyLevel(Base):
    __tablename__ = "loyalty_levels"

    id = Column(String, primary_key=True)
    name = Column(String(100), nullable=False)
    min_points = Column(Integer, nullable=False)
    max_points = Column(Integer, nullable=True)    # None = sem limite superior (topo)
    icon = Column(String(50), default="🏆")
    color = Column(String(30), default="orange")   # chave do colorPalette
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    customer_accounts = relationship("CustomerLoyalty", back_populates="level")


class LoyaltyReward(Base):
    __tablename__ = "loyalty_rewards"

    id = Column(String, primary_key=True)
    label = Column(String(200), nullable=False)
    points_required = Column(Integer, nullable=False)
    icon = Column(String(50), default="🎁")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LoyaltyRule(Base):
    """Defines how customers earn points (e.g. first order, every R$1 spent)."""
    __tablename__ = "loyalty_rules"

    id = Column(String, primary_key=True)
    label = Column(String(200), nullable=False)
    icon = Column(String(50), default="⭐")
    points = Column(Integer, nullable=False)
    rule_type = Column(String(50), default="per_order")   # per_order | per_real | first_order
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CustomerLoyalty(Base):
    __tablename__ = "customer_loyalty"

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id"), unique=True, nullable=False)
    total_points = Column(Integer, default=0)
    level_id = Column(String, ForeignKey("loyalty_levels.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    customer = relationship("Customer", back_populates="loyalty_account")
    level = relationship("LoyaltyLevel", back_populates="customer_accounts")
    transactions = relationship("LoyaltyTransaction", back_populates="loyalty_account")


class LoyaltyTransaction(Base):
    __tablename__ = "loyalty_transactions"

    id = Column(String, primary_key=True)
    customer_loyalty_id = Column(String, ForeignKey("customer_loyalty.id"), nullable=False)
    order_id = Column(String, ForeignKey("orders.id"), nullable=True)
    points = Column(Integer, nullable=False)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    description = Column(String(300))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    loyalty_account = relationship("CustomerLoyalty", back_populates="transactions")

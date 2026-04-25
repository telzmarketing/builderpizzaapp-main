from sqlalchemy import Column, String, Float, Boolean, Integer, Enum, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from backend.database import Base


class TransactionType(str, enum.Enum):
    earned = "earned"
    redeemed = "redeemed"
    rollover = "rollover"
    expired = "expired"
    referral = "referral"
    bonus = "bonus"
    manual = "manual"


class BenefitType(str, enum.Enum):
    product = "product"
    discount = "discount"
    frete_gratis = "frete_gratis"
    experience = "experience"


class ReferralStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    cancelled = "cancelled"


class CycleStatus(str, enum.Enum):
    active = "active"
    closed = "closed"


class LoyaltyLevel(Base):
    __tablename__ = "loyalty_levels"

    id = Column(String, primary_key=True)
    name = Column(String(100), nullable=False)
    min_points = Column(Integer, nullable=False)
    max_points = Column(Integer, nullable=True)
    icon = Column(String(50), default="🏆")
    color = Column(String(30), default="orange")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    customer_accounts = relationship("CustomerLoyalty", back_populates="level")
    benefits = relationship("LoyaltyBenefit", back_populates="level")


class LoyaltyReward(Base):
    __tablename__ = "loyalty_rewards"

    id = Column(String, primary_key=True)
    label = Column(String(200), nullable=False)
    points_required = Column(Integer, nullable=False)
    icon = Column(String(50), default="🎁")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LoyaltyRule(Base):
    __tablename__ = "loyalty_rules"

    id = Column(String, primary_key=True)
    label = Column(String(200), nullable=False)
    icon = Column(String(50), default="⭐")
    points = Column(Integer, nullable=False)
    rule_type = Column(String(50), default="per_order")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LoyaltySettings(Base):
    __tablename__ = "loyalty_settings"

    id = Column(String, primary_key=True, default="default")
    enabled = Column(Boolean, default=True, nullable=False)
    points_per_real = Column(Float, default=1.0, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class LoyaltyBenefit(Base):
    """Benefit attached to a loyalty level (unlocked when customer reaches that level)."""
    __tablename__ = "loyalty_benefits"

    id = Column(String, primary_key=True)
    level_id = Column(String, ForeignKey("loyalty_levels.id"), nullable=False)
    benefit_type = Column(Enum(BenefitType), nullable=False)
    label = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    value = Column(Float, default=0.0)          # discount % or product value
    min_order_value = Column(Float, default=0.0)
    expires_in_days = Column(Integer, nullable=True)  # None = never expires
    usage_limit = Column(Integer, default=1)          # per cycle
    stackable = Column(Boolean, default=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    level = relationship("LoyaltyLevel", back_populates="benefits")
    usages = relationship("LoyaltyBenefitUsage", back_populates="benefit")


class LoyaltyBenefitUsage(Base):
    __tablename__ = "loyalty_benefit_usage"

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    benefit_id = Column(String, ForeignKey("loyalty_benefits.id"), nullable=False)
    order_id = Column(String, ForeignKey("orders.id"), nullable=True)
    used_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    benefit = relationship("LoyaltyBenefit", back_populates="usages")


class LoyaltyCycle(Base):
    """Monthly loyalty cycle record per customer."""
    __tablename__ = "loyalty_cycles"

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    points_earned = Column(Integer, default=0)
    points_used = Column(Integer, default=0)
    points_expired = Column(Integer, default=0)
    points_rolled_over = Column(Integer, default=0)
    level_reached = Column(String, ForeignKey("loyalty_levels.id"), nullable=True)
    status = Column(Enum(CycleStatus), default=CycleStatus.active)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    closed_at = Column(DateTime(timezone=True), nullable=True)


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(String, primary_key=True)
    referrer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    referred_id = Column(String, ForeignKey("customers.id"), nullable=True)
    referral_code = Column(String(20), unique=True, nullable=False)
    status = Column(Enum(ReferralStatus), default=ReferralStatus.pending)
    reward_points = Column(Integer, default=10)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)


class CustomerLoyalty(Base):
    __tablename__ = "customer_loyalty"

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id"), unique=True, nullable=False)
    total_points = Column(Integer, default=0)
    level_id = Column(String, ForeignKey("loyalty_levels.id"), nullable=True)
    # Cycle tracking
    cycle_start_date = Column(DateTime(timezone=True), nullable=True)
    cycle_end_date = Column(DateTime(timezone=True), nullable=True)
    # Points breakdown
    rollover_points = Column(Integer, default=0)     # points carried from previous cycle
    lifetime_points = Column(Integer, default=0)     # total ever earned (never decreases)
    # Activity & expiry
    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    benefit_expiration_date = Column(DateTime(timezone=True), nullable=True)
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

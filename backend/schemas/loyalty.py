from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from backend.models.loyalty import TransactionType, BenefitType, ReferralStatus, CycleStatus


class LoyaltyLevelCreate(BaseModel):
    name: str
    min_points: int = Field(ge=0)
    max_points: Optional[int] = None
    icon: str = "🏆"
    color: str = "orange"


class LoyaltyLevelOut(LoyaltyLevelCreate):
    id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LoyaltyRewardCreate(BaseModel):
    label: str
    points_required: int = Field(gt=0)
    icon: str = "🎁"
    active: bool = True


class LoyaltyRewardOut(LoyaltyRewardCreate):
    id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LoyaltyRuleCreate(BaseModel):
    label: str
    icon: str = "⭐"
    points: int = Field(gt=0)
    rule_type: str = "per_order"
    active: bool = True


class LoyaltyRuleOut(LoyaltyRuleCreate):
    id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LoyaltySettingsUpdate(BaseModel):
    enabled: bool = True
    points_per_real: float = Field(default=1.0, ge=0)


class LoyaltySettingsOut(LoyaltySettingsUpdate):
    id: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class LoyaltyBenefitCreate(BaseModel):
    level_id: str
    benefit_type: BenefitType
    label: str
    description: Optional[str] = None
    value: float = 0.0
    min_order_value: float = 0.0
    expires_in_days: Optional[int] = None
    usage_limit: int = 1
    stackable: bool = False
    active: bool = True


class LoyaltyBenefitOut(LoyaltyBenefitCreate):
    id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LoyaltyCycleOut(BaseModel):
    id: str
    customer_id: str
    start_date: datetime
    end_date: datetime
    points_earned: int
    points_used: int
    points_expired: int
    points_rolled_over: int
    level_reached: Optional[str]
    status: CycleStatus
    created_at: datetime
    closed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class ReferralOut(BaseModel):
    id: str
    referrer_id: str
    referred_id: Optional[str]
    referral_code: str
    status: ReferralStatus
    reward_points: int
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class LoyaltyTransactionOut(BaseModel):
    id: str
    order_id: Optional[str]
    points: int
    transaction_type: TransactionType
    description: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class CustomerLoyaltyOut(BaseModel):
    id: str
    customer_id: str
    total_points: int
    rollover_points: int = 0
    lifetime_points: int = 0
    cycle_start_date: Optional[datetime] = None
    cycle_end_date: Optional[datetime] = None
    benefit_expiration_date: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    level: Optional[LoyaltyLevelOut] = None
    transactions: List[LoyaltyTransactionOut] = []
    benefits: List[LoyaltyBenefitOut] = []
    cycles: List[LoyaltyCycleOut] = []

    model_config = {"from_attributes": True}


class RedeemRewardIn(BaseModel):
    customer_id: str
    reward_id: str


class RedeemBenefitIn(BaseModel):
    customer_id: str
    benefit_id: str
    order_id: Optional[str] = None


class ManualPointsIn(BaseModel):
    customer_id: str
    points: int
    description: str = "Ajuste manual"


class CloseCycleIn(BaseModel):
    customer_id: str

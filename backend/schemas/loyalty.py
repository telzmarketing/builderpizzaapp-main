from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from backend.models.loyalty import TransactionType


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
    level: Optional[LoyaltyLevelOut] = None
    transactions: list[LoyaltyTransactionOut] = []

    model_config = {"from_attributes": True}


class RedeemRewardIn(BaseModel):
    customer_id: str
    reward_id: str

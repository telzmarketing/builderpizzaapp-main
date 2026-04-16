from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PromotionCreate(BaseModel):
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    icon: str = "🍕"
    active: bool = False
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class PromotionUpdate(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    active: Optional[bool] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None


class PromotionOut(BaseModel):
    id: str
    title: str
    subtitle: Optional[str]
    description: Optional[str]
    icon: str
    active: bool
    valid_from: Optional[datetime]
    valid_until: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

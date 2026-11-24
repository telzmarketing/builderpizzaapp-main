from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


RequisitionStatus = Literal["draft", "submitted", "approved", "sourcing", "ordered", "partially_fulfilled", "fulfilled", "rejected", "cancelled"]
RequisitionPriority = Literal["normal", "urgent", "emergency"]


class PurchaseRequisitionItemIn(BaseModel):
    item_id: str = Field(min_length=1, max_length=120)
    unit_id: str = Field(min_length=1, max_length=120)
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    notes: str | None = Field(default=None, max_length=1000)


class PurchaseRequisitionCreate(BaseModel):
    priority: RequisitionPriority = "normal"
    needed_by: date | None = None
    reason: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)
    items: list[PurchaseRequisitionItemIn] = Field(min_length=1, max_length=200)


class PurchaseRequisitionUpdate(BaseModel):
    priority: RequisitionPriority = "normal"
    needed_by: date | None = None
    reason: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=2000)
    items: list[PurchaseRequisitionItemIn] = Field(min_length=1, max_length=200)
    expected_version: int = Field(gt=0)


class PurchaseRequisitionTransitionIn(BaseModel):
    expected_version: int = Field(gt=0)
    reason: str | None = Field(default=None, max_length=500)


class PurchaseRequisitionItemOut(BaseModel):
    id: str
    item_id: str
    unit_id: str
    quantity: Decimal
    notes: str | None = None
    position: int

    model_config = {"from_attributes": True}


class PurchaseRequisitionEventOut(BaseModel):
    id: str
    sequence: int
    from_status: str | None
    to_status: str
    action: str
    actor_admin_id: str | None
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PurchaseRequisitionOut(BaseModel):
    id: str
    tenant_id: str
    code: str
    status: RequisitionStatus
    priority: RequisitionPriority
    requested_by_admin_id: str
    needed_by: date | None
    reason: str | None
    notes: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    items: list[PurchaseRequisitionItemOut]
    events: list[PurchaseRequisitionEventOut] = []

    model_config = {"from_attributes": True}

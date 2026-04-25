from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, Field


class StoreOperationIntervalIn(BaseModel):
    id: Optional[str] = None
    open_time: time
    close_time: time


class StoreOperationIntervalOut(StoreOperationIntervalIn):
    id: str
    schedule_id: str
    tenant_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StoreWeeklyScheduleIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    active: bool = True
    intervals: list[StoreOperationIntervalIn] = Field(default_factory=list)


class StoreWeeklyScheduleOut(BaseModel):
    id: str
    tenant_id: str
    weekday: int
    active: bool
    intervals: list[StoreOperationIntervalOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StoreOperationSettingsIn(BaseModel):
    manual_mode: str = Field(pattern=r"^(auto|manual_closed|manual_open)$")
    closed_message: str = Field(min_length=1)
    allow_scheduled_orders: bool
    timezone: str = "America/Sao_Paulo"


class StoreOperationSettingsOut(StoreOperationSettingsIn):
    id: str
    tenant_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StoreOperationExceptionIn(BaseModel):
    date: date
    exception_type: str = Field(pattern=r"^(closed|special_hours)$")
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    reason: Optional[str] = None


class StoreOperationExceptionOut(StoreOperationExceptionIn):
    id: str
    tenant_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StoreOperationLogOut(BaseModel):
    id: str
    tenant_id: str
    admin_id: Optional[str]
    admin_email: Optional[str]
    action: str
    entity: str
    entity_id: Optional[str]
    old_value: Optional[str]
    new_value: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class StoreOperationConfigOut(BaseModel):
    settings: StoreOperationSettingsOut
    weekly_schedules: list[StoreWeeklyScheduleOut]
    exceptions: list[StoreOperationExceptionOut]


class StoreOperationStatusOut(BaseModel):
    is_open: bool
    mode: str
    status_label: str
    message: str
    current_weekday: int
    today_hours: str
    next_opening_at: Optional[datetime] = None
    next_opening_label: Optional[str] = None
    allow_scheduled_orders: bool

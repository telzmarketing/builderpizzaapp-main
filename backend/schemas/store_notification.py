from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator


AllowedStorePage = Literal["home", "cardapio", "product", "cart"]
NotificationStatus = Literal["active", "paused"]
NotificationType = Literal["manual", "fomento"]
NotificationPriority = Literal["low", "medium", "high"]
CapturedStatus = Literal["pending", "activated", "discarded"]


class StoreNotificationSettingsIn(BaseModel):
    enabled: bool = True
    real_orders_enabled: bool = True
    real_percentage: int = Field(default=70, ge=0, le=100)
    manual_percentage: int = Field(default=30, ge=0, le=100)
    initial_delay_seconds: int = Field(default=5, ge=1, le=60)
    min_delay_seconds: int = Field(default=45, ge=1, le=3600)
    max_delay_seconds: int = Field(default=120, ge=1, le=7200)
    default_display_seconds: int = Field(default=7, ge=3, le=60)
    prevent_same_product_sequence: bool = True
    prevent_same_neighborhood_sequence: bool = False
    only_during_store_hours: bool = False
    allowed_pages: list[AllowedStorePage] = ["home", "cardapio", "product", "cart"]

    @field_validator("max_delay_seconds")
    @classmethod
    def max_delay_must_be_valid(cls, value: int, info):
        min_delay = info.data.get("min_delay_seconds")
        if min_delay is not None and value < min_delay:
            raise ValueError("Tempo maximo deve ser maior ou igual ao tempo minimo.")
        return value


class StoreNotificationSettingsOut(StoreNotificationSettingsIn):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StoreNotificationBase(BaseModel):
    type: NotificationType = "manual"
    status: NotificationStatus = "active"
    internal_name: str = Field(min_length=2, max_length=200)
    display_name: str = Field(min_length=1, max_length=120)
    product_id: str
    neighborhood: str | None = Field(default=None, max_length=120)
    template_text: str = Field(min_length=5)
    priority: NotificationPriority = "medium"
    weight: int = Field(default=1, ge=1, le=100)
    display_seconds: int = Field(default=7, ge=3, le=60)
    purchase_minutes_ago: int = Field(default=12, gt=0, le=1440)
    clear_after_view: bool = False
    start_time: time
    end_time: time
    start_date: date | None = None
    end_date: date | None = None
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value):
        if value == "manual/fomento":
            return "manual"
        return value

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, value: list[int]) -> list[int]:
        clean = sorted(set(int(day) for day in value))
        if not clean:
            raise ValueError("Selecione ao menos um dia da semana.")
        if any(day < 0 or day > 6 for day in clean):
            raise ValueError("Dias da semana devem estar entre 0 e 6.")
        return clean


class StoreNotificationCreate(StoreNotificationBase):
    pass


class StoreNotificationUpdate(BaseModel):
    type: NotificationType | None = None
    status: NotificationStatus | None = None
    internal_name: str | None = Field(default=None, min_length=2, max_length=200)
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    product_id: str | None = None
    neighborhood: str | None = Field(default=None, max_length=120)
    template_text: str | None = Field(default=None, min_length=5)
    priority: NotificationPriority | None = None
    weight: int | None = Field(default=None, ge=1, le=100)
    display_seconds: int | None = Field(default=None, ge=3, le=60)
    purchase_minutes_ago: int | None = Field(default=None, gt=0, le=1440)
    clear_after_view: bool | None = None
    start_time: time | None = None
    end_time: time | None = None
    start_date: date | None = None
    end_date: date | None = None
    weekdays: list[int] | None = None

    @field_validator("weekdays")
    @classmethod
    def validate_weekdays(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        clean = sorted(set(int(day) for day in value))
        if not clean:
            raise ValueError("Selecione ao menos um dia da semana.")
        if any(day < 0 or day > 6 for day in clean):
            raise ValueError("Dias da semana devem estar entre 0 e 6.")
        return clean


class StoreNotificationOut(StoreNotificationBase):
    id: str
    product_name: str | None = None
    product_icon: str | None = None
    impressions_count: int = 0
    last_displayed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class StoreNotificationSummary(BaseModel):
    active_notifications: int
    manual_notifications: int
    real_impressions: int
    total_impressions: int


class StoreNotificationPreviewIn(BaseModel):
    display_name: str
    product_name: str | None = None
    neighborhood: str | None = None
    template_text: str
    relative_time: str = "2min"
    purchase_minutes_ago: int | None = Field(default=None, gt=0, le=1440)


class StoreNotificationPreviewOut(BaseModel):
    message: str


class StoreNotificationNextOut(BaseModel):
    source_type: Literal["real", "manual"]
    notification_id: str | None = None
    order_id: str | None = None
    product_id: str | None = None
    product_name: str
    product_image: str | None = None
    neighborhood: str | None = None
    message: str
    display_seconds: int
    purchase_minutes_ago: int


class StoreNotificationNextEnvelope(BaseModel):
    notification: StoreNotificationNextOut | None = None
    next_delay_seconds: int
    initial_delay_seconds: int


class StoreNotificationImpressionIn(BaseModel):
    page: AllowedStorePage = "home"
    customer_id: str | None = None
    anonymous_session_id: str | None = None


class StoreNotificationCapturedOut(BaseModel):
    id: str
    order_id: str | None = None
    customer_id: str | None = None
    product_id: str | None = None
    product_name: str | None = None
    product_image: str | None = None
    neighborhood: str | None = None
    buyer_name: str | None = None
    order_time: datetime | None = None
    status: CapturedStatus
    created_at: datetime

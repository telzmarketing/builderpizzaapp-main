from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrategicCapacitySlotCreate(BaseModel):
    offer_id: str | None = Field(default=None, min_length=1, max_length=120)
    label: str | None = Field(default=None, max_length=160)
    starts_at: datetime
    ends_at: datetime
    capacity_total: int = Field(ge=1, le=1_000_000)
    blocked: bool = False

    @model_validator(mode="after")
    def validate_period(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("O fim do slot deve ser posterior ao inicio.")
        return self


class StrategicCapacitySlotUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=160)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    capacity_total: int | None = Field(default=None, ge=1, le=1_000_000)
    blocked: bool | None = None


class StrategicCapacitySlotOut(BaseModel):
    id: str
    campaign_id: str
    offer_id: str | None
    label: str | None
    starts_at: datetime
    ends_at: datetime
    capacity_total: int
    capacity_used: int
    blocked: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StrategicCampaignAvailabilitySlotOut(BaseModel):
    """Public, read-only representation of one selectable campaign interval."""

    id: str
    offer_id: str | None
    label: str | None
    starts_at: datetime
    ends_at: datetime
    local_date: date
    capacity_total: int
    capacity_used: int
    remaining_capacity: int
    blocked: bool
    schedule_available: bool
    available: bool
    unavailable_reason: Literal[
        "capacity_exhausted",
        "blocked",
        "outside_store_schedule",
        "ended",
    ] | None = None


class StrategicCampaignAvailabilityDateOut(BaseModel):
    date: date
    slots: list[StrategicCampaignAvailabilitySlotOut]


class StrategicCampaignAvailabilityOut(BaseModel):
    campaign_id: str
    offer_id: str | None
    timezone: str
    generated_at: datetime
    dates: list[StrategicCampaignAvailabilityDateOut]


class StrategicReservationCreate(BaseModel):
    slot_id: str = Field(min_length=1, max_length=120)
    offer_id: str | None = Field(default=None, min_length=1, max_length=120)
    customer_reference: str = Field(min_length=1, max_length=200)
    quantity: int = Field(ge=1, le=100_000)
    payment_mode: Literal["no_payment", "partial", "full"] = "no_payment"
    amount_total: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    amount_paid: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    hold_minutes: int = Field(default=15, ge=1, le=1440)
    idempotency_key: str = Field(min_length=8, max_length=200)

    @model_validator(mode="after")
    def validate_payment_policy(self):
        if self.amount_paid > self.amount_total:
            raise ValueError("O valor pago nao pode superar o valor total.")
        if self.payment_mode == "no_payment" and self.amount_paid != 0:
            raise ValueError("Reserva sem pagamento deve ter valor pago igual a zero.")
        if self.payment_mode == "partial" and not (Decimal("0") < self.amount_paid < self.amount_total):
            raise ValueError("Reserva parcial exige pagamento maior que zero e menor que o total.")
        if self.payment_mode == "full" and self.amount_paid != self.amount_total:
            raise ValueError("Reserva integral exige pagamento igual ao valor total.")
        return self


class StrategicReservationRelease(BaseModel):
    reason: str = Field(min_length=1, max_length=300)
    cancelled: bool = False


class StrategicReservationOut(BaseModel):
    id: str
    campaign_id: str
    offer_id: str | None
    slot_id: str
    order_id: str | None
    customer_reference: str
    quantity: int
    status: Literal["held", "confirmed", "released", "expired", "cancelled"]
    payment_mode: Literal["no_payment", "partial", "full"]
    amount_total: Decimal
    amount_paid: Decimal
    idempotency_key: str
    expires_at: datetime | None
    confirmed_at: datetime | None
    released_at: datetime | None
    release_reason: str | None
    operational_released_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StrategicReservationExpirationResult(BaseModel):
    expired_count: int
    reservation_ids: list[str]


class StrategicReservationOrderBinding(BaseModel):
    order_id: str = Field(min_length=1, max_length=120)


class StrategicOperationalReleaseResult(BaseModel):
    released_count: int
    reservation_ids: list[str]
    order_ids: list[str]

"""Strict Decimal contracts for the versioned inventory foundation API."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, BeforeValidator, field_validator, model_validator


def decimal_input(value):
    if not isinstance(value, str) or not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        raise ValueError("Informe decimal como string, sem expoente.")
    return value


Quantity = Annotated[Decimal, BeforeValidator(decimal_input), Field(ge=0, max_digits=20, decimal_places=6)]
PositiveQuantity = Annotated[Decimal, BeforeValidator(decimal_input), Field(gt=0, max_digits=20, decimal_places=6)]
Factor = Annotated[Decimal, BeforeValidator(decimal_input), Field(gt=0, max_digits=24, decimal_places=12)]
Cost = Annotated[Decimal, BeforeValidator(decimal_input), Field(ge=0, max_digits=20, decimal_places=8)]
Id = Annotated[str, Field(min_length=1, max_length=180)]


class StrictIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_default=True)


class Command(StrictIn):
    expected_version: int = Field(ge=0)


class UnitIn(Command):
    name: str = Field(min_length=1, max_length=120)
    symbol: str = Field(min_length=1, max_length=20)
    code: str = Field(min_length=1, max_length=30)
    dimension: Literal["mass", "volume", "count"]
    conversion_factor: Factor


class ConversionPreviewIn(StrictIn):
    item_id: Id
    quantity: PositiveQuantity
    unit_id: Id
    packaging_id: Id | None = None
    measured_quantity: PositiveQuantity | None = None
    measured_unit_id: Id | None = None

    @model_validator(mode="after")
    def measured_pair(self):
        if (self.measured_quantity is None) != (self.measured_unit_id is None):
            raise ValueError("Peso medido e unidade devem ser informados juntos.")
        return self


class PackagingIn(Command):
    name: str = Field(min_length=1, max_length=180)
    item_id: Id
    supplier_id: Id | None = None
    commercial_unit_id: Id
    base_unit_id: Id
    factor: Factor | None = None
    variable_weight: bool = False

    @model_validator(mode="after")
    def factor_required(self):
        if not self.variable_weight and self.factor is None:
            raise ValueError("Embalagem fixa exige fator confirmado.")
        if self.variable_weight and self.factor is not None:
            raise ValueError("Embalagem de peso variavel usa peso medido, sem fator fixo.")
        return self


class LotIn(Command):
    item_id: Id
    location_id: Id
    supplier_id: Id | None = None
    lot_code: str = Field(min_length=1, max_length=120)
    received_at: datetime
    manufactured_on: date | None = None
    expires_on: date | None = None
    effective_expires_at: datetime | None = None

    @field_validator("received_at", "effective_expires_at")
    @classmethod
    def require_timezone(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Instante exige offset de fuso horario.")
        return value

    @model_validator(mode="after")
    def dates(self):
        if self.manufactured_on and self.expires_on and self.manufactured_on > self.expires_on:
            raise ValueError("Fabricacao posterior a validade.")
        return self


class LotStateIn(Command):
    status: Literal["available", "blocked", "quarantine"]
    reason: str = Field(min_length=1, max_length=120)


class MovementLine(ConversionPreviewIn):
    location_id: Id
    lot_id: Id | None = None
    target_location_id: Id | None = None
    unit_cost: Cost = "0.00000000"


class OperationIn(Command):
    kind: Literal["manual_in", "manual_out", "transfer", "loss", "adjustment_in", "adjustment_out"]
    business_key: str = Field(min_length=1, max_length=180)
    reason: str = Field(min_length=1, max_length=120)
    lines: list[MovementLine] = Field(min_length=1, max_length=100)


class ReservationIn(Command):
    business_key: str = Field(min_length=1, max_length=180)
    item_id: Id
    lot_id: Id | None = None
    location_id: Id
    quantity: PositiveQuantity
    unit_id: Id
    source_type: Literal["manual", "order"]
    source_id: Id
    expires_at: datetime | None = None
    reason: str = Field(min_length=1, max_length=120)

    @field_validator("expires_at")
    @classmethod
    def require_timezone(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Instante exige offset de fuso horario.")
        return value


class ReleaseIn(Command):
    reason: str = Field(min_length=1, max_length=120)


class UnitOut(BaseModel):
    id: str
    name: str
    symbol: str
    code: str | None
    dimension: str | None
    conversion_factor: str | None
    active: bool
    version: int


class PackagingOut(BaseModel):
    id: str
    name: str
    item_id: str
    supplier_id: str | None
    commercial_unit_id: str
    base_unit_id: str
    factor: str | None
    variable_weight: bool
    version: int
    active: bool


class LotOut(BaseModel):
    id: str
    item_id: str
    location_id: str
    supplier_id: str | None
    lot_code: str
    received_at: str
    manufactured_on: str | None
    expires_on: str | None
    effective_expires_at: str | None
    status: str
    version: int


class BalanceOut(BaseModel):
    item_id: str
    location_id: str | None
    lot_id: str | None
    physical: str
    usable: str
    reserved: str
    available: str
    legacy_without_lot: bool
    unit_id: str | None


class ReconciliationOut(BalanceOut):
    issues: list[str]


class ReservationOut(BaseModel):
    id: str
    item_id: str
    lot_id: str | None
    location_id: str
    business_key: str
    source_type: str
    source_id: str
    quantity: str
    expires_at: str | None
    status: str
    version: int


class ConversionPreviewOut(BaseModel):
    item_id: str
    original_quantity: str
    original_unit_id: str
    quantity: str
    unit_id: str
    packaging_id: str | None
    packaging_version: int | None
    rounding: str
    scale: int


class OperationLineOut(BaseModel):
    line: int
    quantity: str
    item_id: str
    lot_id: str | None


class OperationOut(BaseModel):
    id: str
    kind: str
    business_key: str
    version: int
    status: str
    movement_ids: list[str]
    lines: list[OperationLineOut]


class UnitsPage(BaseModel):
    items: list[UnitOut]
    next_cursor: str | None


class PackagingsPage(BaseModel):
    items: list[PackagingOut]
    next_cursor: str | None


class LotsPage(BaseModel):
    items: list[LotOut]
    next_cursor: str | None


class ReservationsPage(BaseModel):
    items: list[ReservationOut]
    next_cursor: str | None


class BalancesPage(BaseModel):
    items: list[BalanceOut]
    next_cursor: str | None


class ReconciliationPage(BaseModel):
    items: list[ReconciliationOut]
    next_cursor: str | None
    read_only: bool

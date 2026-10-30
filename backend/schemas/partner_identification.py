from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


PartnerCode = Literal["own", "partner_99", "ifood", "keeta"]


class PartnerIdentificationIn(BaseModel):
    partner_code: PartnerCode
    display_name: str = Field(min_length=1, max_length=120)
    logo_url: Optional[str] = Field(default=None, max_length=500)
    active: bool = True

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Nome do parceiro obrigatorio.")
        return value

    @field_validator("logo_url")
    @classmethod
    def validate_logo_url(cls, value: str | None) -> str | None:
        normalized = (value or "").strip()
        if not normalized:
            return None
        if not normalized.startswith(("/", "http://", "https://")):
            raise ValueError("Logo deve usar a URL retornada pelo upload ou uma URL HTTP(S).")
        return normalized


class PartnerIdentificationOut(PartnerIdentificationIn):
    id: str
    tenant_id: str
    created_at: object
    updated_at: object


class ResolvedOrderIdentificationOut(BaseModel):
    code: PartnerCode
    display_name: str
    logo_url: Optional[str] = None
    partner_order_number: Optional[str] = None


class PartnerIdentificationBatchItem(BaseModel):
    order_origin: PartnerCode
    display_name: str = Field(min_length=1, max_length=120)
    logo_url: Optional[str] = Field(default=None, max_length=500)
    enabled: bool = True


class PartnerIdentificationBatchIn(BaseModel):
    partners: list[PartnerIdentificationBatchItem]

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class OrderBoardSettingsIn(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    logo_url: str | None = Field(default=None, max_length=500)
    enabled: bool = False
    production_sla_minutes: int = Field(default=20, ge=1, le=240)
    dispatch_sla_minutes: int = Field(default=5, ge=1, le=120)
    completed_window_seconds: int = Field(default=120, ge=30, le=900)
    polling_interval_seconds: int = Field(default=5, ge=3, le=60)
    sound_enabled: bool = False
    max_orders: int = Field(default=50, ge=10, le=200)

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Nome da empresa obrigatorio.")
        return normalized

    @field_validator("logo_url")
    @classmethod
    def validate_logo_url(cls, value: str | None) -> str | None:
        normalized = (value or "").strip()
        if not normalized:
            return None
        if not normalized.startswith(("/", "http://", "https://")):
            raise ValueError("Logo deve usar URL HTTP(S) ou caminho local iniciado por /.")
        return normalized


class OrderBoardDeviceRenameIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class OrderBoardActivationApproveIn(BaseModel):
    code: str = Field(min_length=8, max_length=12)
    name: str = Field(min_length=1, max_length=120)


class OrderBoardActivationOut(BaseModel):
    id: str
    code: str
    expires_at: datetime
    poll_after_seconds: int = 3

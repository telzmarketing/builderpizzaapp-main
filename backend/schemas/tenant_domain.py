"""Validated contracts for tenant-domain administration."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from backend.core.tenant_context import normalize_hostname


class TenantDomainCreate(BaseModel):
    hostname: str = Field(min_length=1, max_length=253)
    kind: Literal["subdomain", "custom"]

    @field_validator("hostname")
    @classmethod
    def validate_hostname(cls, value: str) -> str:
        return normalize_hostname(value)


class TenantDomainOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    hostname: str
    kind: Literal["subdomain", "custom"]
    status: Literal[
        "pending", "awaiting_dns", "verifying", "verified", "active",
        "dns_error", "ssl_error", "suspended", "removed",
    ]
    is_primary: bool = False
    expected_txt_record: str | None = None
    expected_cname: str | None = None
    verified_at: datetime | None = None
    activated_at: datetime | None = None
    suspended_at: datetime | None = None
    removed_at: datetime | None = None
    last_checked_at: datetime | None = None
    ssl_status: str = "pending"
    ssl_issued_at: datetime | None = None
    ssl_expires_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class TenantDomainVerificationChallenge(BaseModel):
    hostname: str
    record_type: Literal["TXT"] = "TXT"
    record_name: str
    record_value: str

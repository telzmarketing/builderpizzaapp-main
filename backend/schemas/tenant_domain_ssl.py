"""Public SSL queue contracts deliberately omit worker credentials."""
from datetime import datetime
import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class CertificateRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    accept_terms: Literal[True]

    @field_validator("email")
    @classmethod
    def validate_worker_email(cls, value):
        local, hostname = str(value).split("@")
        labels = hostname.split(".")
        if (len(str(value)) > 254 or len(local) > 64 or ".." in local
                or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9._+%-]*[A-Za-z0-9])?", local)
                or len(labels) < 2
                or any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels)
                or not re.fullmatch(r"[a-z]{2,63}|xn--[a-z0-9-]{2,59}", labels[-1])):
            raise ValueError("Use um e-mail com letras ASCII, numeros e separadores . _ + % - aceitos pelo executor HTTPS.")
        return value


class CertificateJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    attempts: int
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


class CertificateSummaryOut(BaseModel):
    available: bool
    unavailable_reason: str | None = None
    dns_targets: list[str] = Field(default_factory=list)
    domain_id: str
    hostname: str
    ssl_status: str
    ssl_issued_at: datetime | None = None
    ssl_expires_at: datetime | None = None
    job: CertificateJobOut | None = None


class WorkerLeaseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: UUID
    lease_token: str = Field(min_length=32, max_length=128)


class WorkerFailIn(WorkerLeaseIn):
    error_code: Literal["DNS_INVALID", "DOMAIN_INELIGIBLE", "CERTBOT_FAILED", "NGINX_FAILED", "TLS_INVALID", "WORKER_ERROR", "LEASE_EXPIRED"]

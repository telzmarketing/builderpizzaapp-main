from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StationIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    hostname: str | None = Field(default=None, max_length=255)


class PrinterIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    station_id: str = Field(min_length=1, max_length=36)
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    connection_type: Literal["windows", "network", "usb"] = "windows"
    driver_name: str | None = Field(default=None, max_length=160)
    printer_type: Literal["standard", "thermal", "label"] = "standard"
    capabilities: dict[str, Any] = Field(default_factory=dict)


class RoutingRuleIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    sector: str = Field(min_length=1, max_length=40)
    document_type: str = Field(min_length=1, max_length=60)
    printer_id: str = Field(min_length=1, max_length=36)
    copies: int = Field(default=1, ge=1, le=20)
    priority: int = Field(default=0, ge=0, le=100)


class PrintJobIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    external_job_id: str = Field(min_length=1, max_length=120)
    station_id: str | None = Field(default=None, max_length=36)
    printer_id: str = Field(min_length=1, max_length=36)
    sector: str = Field(min_length=1, max_length=40)
    document_type: str = Field(min_length=1, max_length=60)
    document_format: Literal["pdf", "png", "jpeg", "text", "escpos", "zpl", "epl"]
    payload_ref: str = Field(min_length=1, max_length=1000)
    payload_metadata: dict[str, Any] = Field(default_factory=dict)
    copies: int = Field(default=1, ge=1, le=20)
    priority: int = Field(default=0, ge=0, le=100)


class PrintStatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["received", "queued", "processing", "spooler_submitted", "printed", "error", "cancelled", "uncertain"]
    message: str | None = Field(default=None, max_length=500)


class PrintAgentPairingCodeIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    ttl_minutes: int = Field(default=15, ge=1, le=1440)


class PrintAgentPairIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str = Field(min_length=16, max_length=128)
    hostname: str = Field(min_length=1, max_length=255)
    agent_version: str = Field(min_length=1, max_length=80)


class PrintAgentHeartbeatIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    hostname: str | None = Field(default=None, max_length=255)
    agent_version: str | None = Field(default=None, max_length=80)
    printers: list[dict[str, Any]] = Field(default_factory=list, max_length=100)


class PrintAgentJobStatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: Literal["processing", "spooler_submitted", "printed", "error", "uncertain", "cancelled"]
    message: str | None = Field(default=None, max_length=500)
    attempt_id: str | None = Field(default=None, min_length=1, max_length=100)


class PrintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    station_id: str | None
    printer_id: str
    external_job_id: str
    idempotency_key: str
    sector: str
    document_type: str
    document_format: str
    payload_ref: str
    payload_metadata: dict[str, Any]
    copies: int
    priority: int
    status: str
    attempts: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime

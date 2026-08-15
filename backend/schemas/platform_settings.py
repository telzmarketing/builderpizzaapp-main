"""Read-only API contracts for the platform runtime configuration."""
from typing import Literal

from pydantic import BaseModel


class PlatformSettingsApplicationOut(BaseModel):
    app_name: str
    app_version: str
    platform_brand_name: str
    debug: bool


class PlatformSettingsSecurityOut(BaseModel):
    jwt_secret_state: Literal["configured", "default", "missing"]
    platform_rbac_enabled: bool
    multi_tenant_auth_enabled: bool


class PlatformSettingsDomainsOut(BaseModel):
    enabled: bool
    trust_proxy_headers: bool
    platform_hostnames: list[str]
    platform_hostname_count: int
    invalid_platform_hostname_count: int
    trusted_proxy_count: int
    invalid_trusted_proxy_count: int


class PlatformRolloutFlagOut(BaseModel):
    key: str
    label: str
    enabled: bool
    category: Literal["isolation", "runtime", "security", "access"]


class PlatformSettingsAlertOut(BaseModel):
    key: str
    severity: Literal["info", "warning", "critical"]
    title: str
    description: str


class PlatformSettingsOut(BaseModel):
    source: Literal["environment"]
    read_only: Literal[True]
    restart_required: Literal[True]
    status: Literal["ok", "attention", "critical"]
    application: PlatformSettingsApplicationOut
    security: PlatformSettingsSecurityOut
    domains: PlatformSettingsDomainsOut
    rollout_flags: list[PlatformRolloutFlagOut]
    alerts: list[PlatformSettingsAlertOut]

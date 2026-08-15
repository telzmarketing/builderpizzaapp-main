"""Append-only, secret-safe audit writer for platform administration."""
from __future__ import annotations

import json
import re
import uuid
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from backend.models.platform_audit import PlatformAuditLog


SENSITIVE_KEYS = frozenset({
    "password", "password_hash", "token", "access_token", "refresh_token",
    "secret", "api_key", "private_key", "verification_token", "authorization",
    "cookie", "client_secret", "token_hash",
})

# These JSON blobs can contain provider credentials under arbitrary keys.
# Audit keeps only the fact that the field changed, never its contents.
OPAQUE_SECRET_FIELDS = frozenset({"config_json", "default_config_json"})
REQUEST_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$")


def _sensitive(key: str) -> bool:
    normalized = key.lower()
    return normalized in SENSITIVE_KEYS or normalized.endswith(
        ("_password", "_secret", "_token", "_token_hash", "_api_key", "_private_key")
    )


def _safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): (
                "[REDACTED]"
                if _sensitive(str(key)) or str(key).lower() in OPAQUE_SECRET_FIELDS
                else _safe(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_safe(item) for item in value]
    if isinstance(value, (datetime, date, Decimal)):
        return str(value)
    if hasattr(value, "__table__"):
        return _safe({column.name: getattr(value, column.name, None) for column in value.__table__.columns})
    return value


def _json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(_safe(value), ensure_ascii=False, sort_keys=True, default=str)


def _request_identifier(request, state_name: str, header_name: str) -> str | None:
    if request is None:
        return None
    state = getattr(request, "state", None)
    state_value = getattr(state, state_name, None)
    if isinstance(state_value, str) and REQUEST_IDENTIFIER_RE.fullmatch(state_value):
        return state_value
    headers = getattr(request, "headers", None)
    header_value = headers.get(header_name) if headers is not None else None
    if not isinstance(header_value, str):
        return None
    normalized = header_value.strip()
    return normalized if REQUEST_IDENTIFIER_RE.fullmatch(normalized) else None


class PlatformAuditService:
    def __init__(self, db):
        self.db = db

    def record(
        self,
        *,
        action: str,
        actor,
        tenant_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        before: Any = None,
        after: Any = None,
        reason: str | None = None,
        request=None,
        metadata: Any = None,
    ) -> PlatformAuditLog:
        row = PlatformAuditLog(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            actor_user_id=getattr(actor, "id", None),
            actor_label=getattr(actor, "name", None) or getattr(actor, "email", None) or "system",
            actor_role=getattr(actor, "role_id", None),
            actor_type="platform_user" if actor is not None else "system",
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=_request_identifier(request, "request_id", "x-request-id"),
            correlation_id=_request_identifier(request, "correlation_id", "x-correlation-id"),
            ip_address=request.client.host if request is not None and request.client else None,
            user_agent=request.headers.get("user-agent") if request is not None else None,
            before_data=_json(before),
            after_data=_json(after),
            reason=reason,
            metadata_json=_json(metadata),
        )
        self.db.add(row)
        return row

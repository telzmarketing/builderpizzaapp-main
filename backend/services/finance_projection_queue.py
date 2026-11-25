"""Durable retry queue for financial projection failures.

This service deliberately does not publish events or call payment services.
It only persists and claims retry work, so producers can integrate it from
their own transaction boundary without coupling the queue to a payment flow.
"""
from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from backend.models.finance_projection import FinanceProjectionEvent


_SENSITIVE_KEY_PARTS = (
    "password", "passwd", "secret", "token", "authorization", "api_key",
    "apikey", "private_key", "access_key", "refresh_key", "card_number",
    "security_code", "cvv", "cvc",
)
_MAX_PAYLOAD_BYTES = 64 * 1024
_MAX_ERROR_LENGTH = 4000


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def redact_payload(value: Any, *, _depth: int = 0) -> Any:
    """Return a bounded, JSON-safe copy with credential-like values removed."""
    if _depth > 8:
        return "[truncated]"
    if isinstance(value, Mapping):
        return {
            str(key)[:120]: "[redacted]" if _is_sensitive_key(key)
            else redact_payload(item, _depth=_depth + 1)
            for key, item in list(value.items())[:200]
        }
    if isinstance(value, (list, tuple, set)):
        return [redact_payload(item, _depth=_depth + 1) for item in list(value)[:200]]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return str(value)[:500]


def _payload_json(payload: Mapping[str, Any] | None) -> str:
    redacted = redact_payload(payload or {})
    encoded = json.dumps(redacted, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(encoded.encode("utf-8")) <= _MAX_PAYLOAD_BYTES:
        return encoded
    return json.dumps({"_redacted": "payload_too_large", "preview": encoded[:2000]}, ensure_ascii=False)


class FinanceProjectionQueue:
    """Tenant-scoped enqueue/claim/acknowledge operations for projection jobs."""

    def __init__(self, db: Session, tenant_id: str):
        if not tenant_id or not str(tenant_id).strip():
            raise ValueError("tenant_id obrigatorio")
        self.db = db
        self.tenant_id = str(tenant_id)

    def enqueue(
        self,
        *,
        event_type: str,
        dedupe_key: str,
        aggregate_type: str | None = None,
        aggregate_id: str | None = None,
        source_type: str | None = None,
        source_id: str | None = None,
        payload: Mapping[str, Any] | None = None,
        event_version: int = 1,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        max_attempts: int = 5,
        available_at: datetime | None = None,
    ) -> FinanceProjectionEvent:
        if not event_type or not event_type.strip():
            raise ValueError("event_type obrigatorio")
        if not dedupe_key or not dedupe_key.strip():
            raise ValueError("dedupe_key obrigatorio")
        if event_version < 1 or max_attempts < 1:
            raise ValueError("event_version e max_attempts devem ser positivos")

        now = utcnow()
        values = {
            "id": str(uuid.uuid4()), "tenant_id": self.tenant_id,
            "event_type": event_type[:120], "event_version": event_version,
            "aggregate_type": aggregate_type[:80] if aggregate_type else None,
            "aggregate_id": str(aggregate_id)[:160] if aggregate_id is not None else None,
            "source_type": source_type[:80] if source_type else None,
            "source_id": str(source_id)[:160] if source_id is not None else None,
            "payload_json": _payload_json(payload), "dedupe_key": dedupe_key[:240],
            "correlation_id": correlation_id[:160] if correlation_id else None,
            "causation_id": causation_id[:160] if causation_id else None,
            "status": "pending", "attempts": 0, "max_attempts": max_attempts,
            "available_at": available_at or now, "created_at": now, "updated_at": now,
        }
        dialect = self.db.get_bind().dialect.name
        if dialect == "postgresql":
            statement = postgres_insert(FinanceProjectionEvent).values(**values)
        elif dialect == "sqlite":
            statement = sqlite_insert(FinanceProjectionEvent).values(**values)
        else:
            statement = None
        if statement is not None:
            self.db.execute(statement.on_conflict_do_nothing(index_elements=["tenant_id", "dedupe_key"]))
        else:
            existing = self._by_dedupe(dedupe_key)
            if existing is None:
                self.db.add(FinanceProjectionEvent(**values))
        self.db.flush()
        return self._by_dedupe(dedupe_key)  # type: ignore[return-value]

    def _by_dedupe(self, dedupe_key: str) -> FinanceProjectionEvent | None:
        return self.db.scalar(select(FinanceProjectionEvent).where(
            FinanceProjectionEvent.tenant_id == self.tenant_id,
            FinanceProjectionEvent.dedupe_key == dedupe_key,
        ))

    def claim(self, *, limit: int = 25, worker_id: str = "finance-projection-worker", lease_seconds: int = 300) -> list[FinanceProjectionEvent]:
        if limit < 1 or limit > 500:
            raise ValueError("limit deve estar entre 1 e 500")
        if not worker_id or lease_seconds < 1:
            raise ValueError("worker_id e lease_seconds sao obrigatorios")
        now = utcnow()
        lease_cutoff = now - timedelta(seconds=lease_seconds)
        eligible = select(FinanceProjectionEvent).where(
            FinanceProjectionEvent.tenant_id == self.tenant_id,
            FinanceProjectionEvent.available_at <= now,
            or_(
                and_(FinanceProjectionEvent.status.in_(("pending", "failed")), FinanceProjectionEvent.attempts < FinanceProjectionEvent.max_attempts),
                and_(FinanceProjectionEvent.status == "processing", FinanceProjectionEvent.locked_at < lease_cutoff),
            ),
        ).order_by(FinanceProjectionEvent.available_at, FinanceProjectionEvent.created_at).limit(limit).with_for_update(skip_locked=True)
        rows = list(self.db.scalars(eligible).all())
        claimed: list[FinanceProjectionEvent] = []
        for row in rows:
            if row.status == "processing" and row.attempts >= row.max_attempts:
                # A worker died after consuming the final attempt. Preserve
                # the event as terminal instead of allowing attempts to
                # exceed the database invariant.
                row.status = "dead"
                row.locked_at = row.locked_by = None
                row.last_error = row.last_error or "Lease expirado após a última tentativa."
                row.updated_at = now
                continue
            row.status = "processing"
            row.attempts += 1
            row.locked_at = now
            row.locked_by = worker_id[:160]
            row.updated_at = now
            claimed.append(row)
        self.db.commit()
        return claimed

    def complete(self, event_id: str, *, worker_id: str) -> bool:
        row = self._locked_owned(event_id, worker_id)
        if row is None:
            return False
        now = utcnow()
        row.status, row.processed_at, row.last_error = "processed", now, None
        row.locked_at = row.locked_by = None
        row.updated_at = now
        self.db.commit()
        return True

    def fail(self, event_id: str, *, worker_id: str, error: str, retry_delay_seconds: int = 60) -> str | None:
        row = self._locked_owned(event_id, worker_id)
        if row is None:
            return None
        now = utcnow()
        terminal = row.attempts >= row.max_attempts
        row.status = "dead" if terminal else "failed"
        row.last_error = str(error)[:_MAX_ERROR_LENGTH]
        row.available_at = now + timedelta(seconds=max(0, retry_delay_seconds))
        row.locked_at = row.locked_by = None
        row.updated_at = now
        self.db.commit()
        return row.status

    def _locked_owned(self, event_id: str, worker_id: str) -> FinanceProjectionEvent | None:
        return self.db.scalar(select(FinanceProjectionEvent).where(
            FinanceProjectionEvent.id == event_id,
            FinanceProjectionEvent.tenant_id == self.tenant_id,
            FinanceProjectionEvent.status == "processing",
            FinanceProjectionEvent.locked_by == worker_id,
        ).with_for_update())

    def process_pending(
        self,
        handler: Callable[[FinanceProjectionEvent], Any],
        *,
        limit: int = 25,
        worker_id: str = "finance-projection-worker",
        retry_delay_seconds: int = 60,
    ) -> dict[str, int]:
        claimed = self.claim(limit=limit, worker_id=worker_id)
        counts = {"claimed": len(claimed), "processed": 0, "failed": 0, "dead": 0}
        for row in claimed:
            try:
                handler(row)
            except Exception as exc:  # worker isolation: one event cannot stop the batch
                status = self.fail(row.id, worker_id=worker_id, error=str(exc), retry_delay_seconds=retry_delay_seconds)
                counts["dead" if status == "dead" else "failed"] += 1
            else:
                if self.complete(row.id, worker_id=worker_id):
                    counts["processed"] += 1
        return counts

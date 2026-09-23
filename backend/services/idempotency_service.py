from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.exceptions import IdempotencyConflict, IdempotencyKeyRequired
from backend.models.idempotency import IdempotencyKey


@dataclass(frozen=True)
class IdempotencyClaim:
    record: IdempotencyKey
    replay_resource_id: str | None = None


class IdempotencyService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    @staticmethod
    def _digest(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _request_digest(payload: Any) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
        return IdempotencyService._digest(canonical)

    def claim(self, key: str | None, operation: str, payload: Any) -> IdempotencyClaim:
        normalized = (key or "").strip()
        if not normalized:
            raise IdempotencyKeyRequired()
        if len(normalized) > 200:
            raise IdempotencyConflict("A chave de idempotencia excede 200 caracteres.")

        key_hash = self._digest(normalized)
        request_hash = self._request_digest(payload)
        existing = self._find(operation, key_hash)
        if existing:
            return self._existing_claim(existing, request_hash)

        now = datetime.now(timezone.utc)
        record = IdempotencyKey(
            id=str(uuid.uuid4()), tenant_id=self.tenant_id, operation=operation,
            key_hash=key_hash, request_hash=request_hash, status="processing",
            expires_at=now + timedelta(hours=24),
        )
        self.db.add(record)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self._find(operation, key_hash)
            if existing:
                return self._existing_claim(existing, request_hash)
            raise
        self.db.refresh(record)
        return IdempotencyClaim(record=record)

    def complete(self, record: IdempotencyKey, resource_id: str) -> None:
        record.status = "completed"
        record.resource_id = resource_id
        record.updated_at = datetime.now(timezone.utc)
        self.db.add(record)
        self.db.commit()

    def _find(self, operation: str, key_hash: str) -> IdempotencyKey | None:
        return self.db.query(IdempotencyKey).filter(
            IdempotencyKey.tenant_id == self.tenant_id,
            IdempotencyKey.operation == operation,
            IdempotencyKey.key_hash == key_hash,
        ).first()

    @staticmethod
    def _existing_claim(record: IdempotencyKey, request_hash: str) -> IdempotencyClaim:
        if record.request_hash != request_hash:
            raise IdempotencyConflict("A mesma chave foi usada com outro payload.")
        if record.status == "completed" and record.resource_id:
            return IdempotencyClaim(record=record, replay_resource_id=record.resource_id)
        raise IdempotencyConflict("Uma requisicao com esta chave ainda esta em processamento.")

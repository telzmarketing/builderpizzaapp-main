from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.core.tenant_context import TenantContext
from backend.core.wave6_tenant_context import wave6_tenant_id
from backend.models.crm import CustomerCommercialMemory
from backend.models.customer import Customer
from backend.schemas.customer_commercial_memory import CustomerCommercialMemoryIn


class CustomerCommercialMemoryError(ValueError):
    pass


class CustomerCommercialMemoryService:
    def __init__(self, db: Session, context: TenantContext | None = None, actor_id: str | None = None):
        self.db = db
        self.tenant_id = wave6_tenant_id(context)
        self.actor_id = actor_id

    def _customer(self, customer_id: str) -> Customer:
        customer = self.db.query(Customer).filter(
            Customer.id == customer_id,
            Customer.tenant_id == self.tenant_id,
        ).first()
        if not customer:
            raise CustomerCommercialMemoryError("Cliente nao encontrado neste tenant.")
        return customer

    @staticmethod
    def _out(row: CustomerCommercialMemory) -> dict:
        return {
            "id": row.id, "tenant_id": row.tenant_id, "customer_id": row.customer_id,
            "memory_key": row.memory_key, "memory_type": row.memory_type, "value": row.value,
            "source": row.source, "confidence": row.confidence, "active": bool(row.active),
            "last_observed_at": row.last_observed_at, "created_by": row.created_by,
            "created_at": row.created_at, "updated_at": row.updated_at,
        }

    def list(self, customer_id: str, *, active_only: bool = True) -> list[dict]:
        self._customer(customer_id)
        query = self.db.query(CustomerCommercialMemory).filter(
            CustomerCommercialMemory.tenant_id == self.tenant_id,
            CustomerCommercialMemory.customer_id == customer_id,
        )
        if active_only:
            query = query.filter(CustomerCommercialMemory.active.is_(True))
        return [self._out(row) for row in query.order_by(CustomerCommercialMemory.updated_at.desc()).limit(100).all()]

    def upsert(self, customer_id: str, payload: CustomerCommercialMemoryIn) -> dict:
        self._customer(customer_id)
        row = self.db.query(CustomerCommercialMemory).filter(
            CustomerCommercialMemory.tenant_id == self.tenant_id,
            CustomerCommercialMemory.customer_id == customer_id,
            CustomerCommercialMemory.memory_key == payload.memory_key.strip(),
        ).first()
        if not row:
            row = CustomerCommercialMemory(
                id=f"cmem-{uuid.uuid4().hex[:14]}",
                tenant_id=self.tenant_id,
                customer_id=customer_id,
                memory_key=payload.memory_key.strip(),
                created_by=self.actor_id,
            )
            self.db.add(row)
        row.memory_type = payload.memory_type
        row.value = payload.value.strip()
        row.source = payload.source.strip()
        row.confidence = payload.confidence
        row.active = payload.active
        row.last_observed_at = datetime.now(timezone.utc)
        self.db.flush()
        return self._out(row)

    def deactivate(self, customer_id: str, memory_id: str) -> None:
        self._customer(customer_id)
        row = self.db.query(CustomerCommercialMemory).filter(
            CustomerCommercialMemory.id == memory_id,
            CustomerCommercialMemory.tenant_id == self.tenant_id,
            CustomerCommercialMemory.customer_id == customer_id,
        ).first()
        if not row:
            raise CustomerCommercialMemoryError("Memoria comercial nao encontrada neste tenant.")
        row.active = False
        row.last_observed_at = datetime.now(timezone.utc)

    def ai_context(self, customer_id: str | None) -> list[dict]:
        if not customer_id:
            return []
        return self.list(customer_id, active_only=True)[:20]

    def observe_agent_message(self, customer_id: str | None, message: str) -> list[dict]:
        """Persist only explicit commercial signals, never the raw conversation."""
        if not customer_id:
            return []
        observed = []
        normalized = unicodedata.normalize("NFKD", message or "")
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        patterns = (
            ("preference", r"(?:gosto de|prefiro|adoro|sempre pe[cç]o)\s+([^.!?\n]{2,120})"),
            ("avoidance", r"(?:nao gosto de|não gosto de|evite)\s+([^.!?\n]{2,120})"),
        )
        for memory_type, pattern in patterns:
            match = re.search(pattern, normalized, flags=re.IGNORECASE)
            if not match:
                continue
            value = re.sub(r"\s+", " ", match.group(1)).strip(" ,;")
            key_value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:100]
            if not key_value:
                continue
            observed.append(self.upsert(customer_id, CustomerCommercialMemoryIn(
                memory_key=f"{memory_type}:{key_value}", memory_type=memory_type,
                value=value, source="agente_whatsapp", confidence="medium",
            )))
        return observed

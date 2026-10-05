from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.tenant_context import TenantContextMissing
from backend.core.tenant_execution import background_context_enforcement_enabled
from backend.core.events import DeliveryAssigned
from backend.models.agente_whatsapp import (
    AgenteWhatsAppChannelSettings,
    AgenteWhatsAppContext,
    AgenteWhatsAppEvent,
    AgenteWhatsAppMessage,
    AgenteWhatsAppOutbox,
    AgenteWhatsAppSession,
)
from backend.models.delivery import DeliveryPerson
from backend.services.customer_identity_service import normalize_phone

ASSIGNMENT_NOTICE_TEMPLATE = "{name}, você recebeu uma nova entrega."
DRIVER_REPLY_FALLBACK = (
    "Esse sistema serve apenas para avisos de entregas, para consultar suas entregas acesse o aplicativo."
)
SOURCE = "delivery_driver_whatsapp"


def _json_dump(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, default=str)


class DeliveryDriverWhatsAppService:
    def __init__(self, db: Session):
        self._db = db

    def handle_delivery_assigned(self, event: DeliveryAssigned) -> dict[str, Any]:
        if background_context_enforcement_enabled() and not event.tenant_id:
            raise TenantContextMissing("Evento de entrega sem tenant confiavel.")
        person_query = self._db.query(DeliveryPerson).filter(
            DeliveryPerson.id == event.delivery_person_id,
            DeliveryPerson.active == True,  # noqa: E712
            DeliveryPerson.deleted_at.is_(None),
        )
        if event.tenant_id:
            person_query = person_query.filter(DeliveryPerson.tenant_id == event.tenant_id)
        person = person_query.first()
        if not person:
            return {"sent": False, "status": "driver_not_found"}

        phone = normalize_phone(person.phone)
        if not phone:
            return {"sent": False, "status": "driver_without_phone"}

        text = ASSIGNMENT_NOTICE_TEMPLATE.format(name=(person.name or event.delivery_person_name).strip())

        return self._queue_driver_message(
            phone=phone,
            text=text,
            event_type="delivery_driver_assignment_notice",
            idempotency_key=f"delivery_driver_assignment_notice:{event.delivery_id}:{event.delivery_person_id}",
            provider=self._active_provider(event.tenant_id),
            payload={
                "delivery_id": event.delivery_id,
                "order_id": event.order_id,
                "delivery_person_id": event.delivery_person_id,
                "delivery_person_name": person.name or event.delivery_person_name,
                "estimated_minutes": event.estimated_minutes,
                "tenant_id": event.tenant_id,
            },
        )

    def process_driver_reply(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if payload.get("event_type") != "message_received":
            return None

        item = payload.get("message") or {}
        if item.get("from_me") is True:
            return None

        remote = item.get("remote_jid") or item.get("from") or item.get("phone")
        phone = normalize_phone(str(remote).split("@", 1)[0] if remote else "")
        provider_message_id = str(item.get("id") or item.get("message_id") or "").strip()
        if not phone:
            return None

        # ``_trusted_tenant_id`` is attached by the gateway after resolving
        # its persisted instance.  Never trust a tenant field from provider
        # payload JSON.
        tenant_id = str(payload.get("_trusted_tenant_id") or "").strip() or None
        if background_context_enforcement_enabled() and not tenant_id:
            return {"handled": False, "queued": False, "ignored": 1, "status": "tenant_context_missing"}
        person = self._find_driver_by_phone(phone, tenant_id=tenant_id)
        if not person:
            return None

        idempotency_key = (
            f"delivery_driver_reply_fallback:{provider_message_id}"
            if provider_message_id
            else f"delivery_driver_reply_fallback:{phone}:{uuid.uuid4()}"
        )
        queued = self._queue_driver_message(
            phone=phone,
            text=DRIVER_REPLY_FALLBACK,
            event_type="delivery_driver_reply_fallback",
            idempotency_key=idempotency_key,
            provider="baileys",
            payload={
                "delivery_person_id": person.id,
                "tenant_id": person.tenant_id,
                "provider_message_id": provider_message_id or None,
                "instance_id": payload.get("instance_id"),
            },
        )
        return {
            "handled": True,
            "queued": bool(queued.get("queued")),
            "duplicates": 1 if queued.get("reason") == "already_queued" else 0,
            "ignored": 0,
            "status": queued.get("reason") or "queued",
            "message_id": queued.get("message_id"),
            "outbox_id": queued.get("outbox_id"),
        }

    def _find_driver_by_phone(self, phone: str, *, tenant_id: str | None = None) -> DeliveryPerson | None:
        query = self._db.query(DeliveryPerson).filter(
            DeliveryPerson.active == True,  # noqa: E712
            DeliveryPerson.deleted_at.is_(None),
        )
        if tenant_id:
            query = query.filter(DeliveryPerson.tenant_id == tenant_id)
        people = query.all()
        matches = []
        for person in people:
            if self._same_phone(phone, normalize_phone(person.phone)):
                matches.append(person)
        # A provider callback only identifies a phone number.  Once Wave 7 is
        # enabled, a duplicated driver number across establishments is
        # ambiguous and must not trigger a message for either tenant.
        if (get_settings().MULTI_TENANT_WAVE7_ORM_ENABLED or background_context_enforcement_enabled()) and len(matches) != 1:
            return None
        return matches[0] if matches else None

    def _same_phone(self, left: str, right: str) -> bool:
        if not left or not right:
            return False
        if left == right:
            return True
        if len(left) >= 8 and len(right) >= 8 and (left.endswith(right) or right.endswith(left)):
            return True
        left_without_country = left[2:] if left.startswith("55") and len(left) > 11 else left
        right_without_country = right[2:] if right.startswith("55") and len(right) > 11 else right
        return bool(
            left_without_country
            and right_without_country
            and len(left_without_country) >= 8
            and len(right_without_country) >= 8
            and (
                left_without_country == right_without_country
                or left_without_country.endswith(right_without_country)
                or right_without_country.endswith(left_without_country)
            )
        )

    def _queue_driver_message(
        self,
        *,
        phone: str,
        text: str,
        event_type: str,
        idempotency_key: str,
        provider: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        tenant_id = str(payload.get("tenant_id") or "").strip() or None
        existing = (
            self._db.query(AgenteWhatsAppOutbox)
            .filter(
                AgenteWhatsAppOutbox.idempotency_key == idempotency_key,
                AgenteWhatsAppOutbox.tenant_id == tenant_id,
            )
            .first()
        )
        if existing:
            return {
                "queued": False,
                "reason": "already_queued",
                "message_id": existing.message_id,
                "outbox_id": existing.id,
            }

        now = datetime.now(timezone.utc)
        session = self._get_or_create_driver_session(phone=phone, provider=provider, tenant_id=tenant_id)
        message = AgenteWhatsAppMessage(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            session_id=session.id,
            customer_id=None,
            direction="outbound",
            sender_type="system",
            message_type="text",
            body=text,
            provider_status="queued",
            raw_payload_json=_json_dump({"source": SOURCE, "event_type": event_type, "payload": payload}),
            created_at=now,
        )
        self._db.add(message)
        self._db.flush()

        outbox = AgenteWhatsAppOutbox(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            message_id=message.id,
            session_id=session.id,
            customer_id=None,
            phone=phone,
            provider=provider if provider in {"official", "baileys"} else "official",
            status="pending",
            attempts=0,
            max_attempts=3,
            idempotency_key=idempotency_key,
            payload_json=_json_dump(
                {
                    "message_id": message.id,
                    "session_id": session.id,
                    "message_type": "text",
                    "body": text,
                    "source": SOURCE,
                    "event_type": event_type,
                    "payload": payload,
                }
            ),
            next_attempt_at=now,
            created_at=now,
            updated_at=now,
        )
        self._db.add(outbox)
        self._db.add(
            AgenteWhatsAppEvent(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                session_id=session.id,
                customer_id=None,
                order_id=payload.get("order_id"),
                event_type=event_type,
                source=SOURCE,
                payload_json=_json_dump(
                    {
                        "message_id": message.id,
                        "outbox_id": outbox.id,
                        "idempotency_key": idempotency_key,
                        "phone": phone,
                        **payload,
                    }
                ),
                processed_at=now,
                created_at=now,
            )
        )
        self._db.flush()
        return {"queued": True, "message_id": message.id, "outbox_id": outbox.id}

    def _get_or_create_driver_session(self, *, phone: str, provider: str, tenant_id: str | None) -> AgenteWhatsAppSession:
        existing = (
            self._db.query(AgenteWhatsAppSession)
            .filter(
                AgenteWhatsAppSession.tenant_id == tenant_id,
                AgenteWhatsAppSession.phone == phone,
                AgenteWhatsAppSession.origin == "delivery_driver_notice",
                AgenteWhatsAppSession.status.in_(["open", "waiting_human", "human", "ai_paused"]),
            )
            .order_by(AgenteWhatsAppSession.created_at.desc())
            .first()
        )
        if existing:
            existing.provider = provider if provider in {"official", "baileys"} else existing.provider
            existing.ai_enabled = False
            existing.automation_blocked = True
            existing.updated_at = datetime.now(timezone.utc)
            return existing

        now = datetime.now(timezone.utc)
        session = AgenteWhatsAppSession(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            customer_id=None,
            phone=phone,
            provider=provider if provider in {"official", "baileys"} else "official",
            origin="delivery_driver_notice",
            ai_enabled=False,
            automation_blocked=True,
            metadata_json=_json_dump({"source": SOURCE, "audience": "delivery_person", "tenant_id": tenant_id}),
            created_at=now,
            updated_at=now,
        )
        self._db.add(session)
        self._db.flush()
        self._db.add(
            AgenteWhatsAppContext(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                session_id=session.id,
                customer_id=None,
            )
        )
        return session

    def _active_provider(self, tenant_id: str | None) -> str:
        settings = (
            self._db.query(AgenteWhatsAppChannelSettings)
            .filter(
                AgenteWhatsAppChannelSettings.id == "default",
                AgenteWhatsAppChannelSettings.tenant_id == tenant_id,
            )
            .first()
        )
        if settings and settings.active_provider in {"official", "baileys"}:
            return settings.active_provider
        return "official"

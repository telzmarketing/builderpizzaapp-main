from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.agente_whatsapp import (
    AgenteWhatsAppCampaign,
    AgenteWhatsAppContext,
    AgenteWhatsAppEvent,
    AgenteWhatsAppMessage,
    AgenteWhatsAppSession,
    AgenteWhatsAppStory,
)
from backend.models.customer import Customer
from backend.services.customer_identity_service import CustomerIdentityService, normalize_phone


def _json_dump(value: dict[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False)


def _json_load(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


class AgenteWhatsAppService:
    def __init__(self, db: Session):
        self._db = db

    def dashboard(self) -> dict[str, int]:
        today_start = datetime.combine(date.today(), time.min, tzinfo=timezone.utc)
        return {
            "sessions_open": self._count_sessions("open"),
            "sessions_human": self._count_sessions("human"),
            "sessions_ai_paused": self._count_sessions("ai_paused"),
            "messages_today": self._count_messages(today_start),
            "inbound_today": self._count_messages(today_start, "inbound"),
            "outbound_today": self._count_messages(today_start, "outbound"),
            "campaigns_total": self._db.query(func.count(AgenteWhatsAppCampaign.id)).scalar() or 0,
            "stories_total": self._db.query(func.count(AgenteWhatsAppStory.id)).scalar() or 0,
        }

    def _count_sessions(self, status: str) -> int:
        return (
            self._db.query(func.count(AgenteWhatsAppSession.id))
            .filter(AgenteWhatsAppSession.status == status)
            .scalar()
            or 0
        )

    def _count_messages(self, since: datetime, direction: str | None = None) -> int:
        q = self._db.query(func.count(AgenteWhatsAppMessage.id)).filter(AgenteWhatsAppMessage.created_at >= since)
        if direction:
            q = q.filter(AgenteWhatsAppMessage.direction == direction)
        return q.scalar() or 0

    def list_sessions(self, *, status: str | None = None, limit: int = 50) -> list[AgenteWhatsAppSession]:
        q = self._db.query(AgenteWhatsAppSession)
        if status:
            q = q.filter(AgenteWhatsAppSession.status == status)
        return (
            q.order_by(AgenteWhatsAppSession.last_message_at.desc().nullslast(), AgenteWhatsAppSession.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_session(self, session_id: str) -> AgenteWhatsAppSession | None:
        return self._db.query(AgenteWhatsAppSession).filter(AgenteWhatsAppSession.id == session_id).first()

    def get_or_create_session(
        self,
        *,
        phone: str,
        customer_id: str | None = None,
        provider: str = "official",
        provider_contact_id: str | None = None,
        origin: str = "manual",
        ai_enabled: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[AgenteWhatsAppSession, bool]:
        normalized_phone = normalize_phone(phone)
        if not normalized_phone:
            raise ValueError("Telefone invalido.")

        customer = None
        if customer_id:
            customer = self._db.query(Customer).filter(Customer.id == customer_id).first()
            if not customer:
                raise ValueError("Cliente nao encontrado.")
        else:
            customer, _created = CustomerIdentityService(self._db).get_or_create_whatsapp_lead(
                phone=normalized_phone,
                source="agente_whatsapp",
            )

        existing = (
            self._db.query(AgenteWhatsAppSession)
            .filter(
                AgenteWhatsAppSession.phone == normalized_phone,
                AgenteWhatsAppSession.status.in_(["open", "waiting_human", "human", "ai_paused"]),
            )
            .order_by(AgenteWhatsAppSession.created_at.desc())
            .first()
        )
        if existing:
            if customer and not existing.customer_id:
                existing.customer_id = customer.id
            existing.provider = provider or existing.provider
            existing.provider_contact_id = provider_contact_id or existing.provider_contact_id
            existing.updated_at = datetime.now(timezone.utc)
            return existing, False

        session = AgenteWhatsAppSession(
            id=str(uuid.uuid4()),
            customer_id=customer.id if customer else None,
            phone=normalized_phone,
            provider=provider,
            provider_contact_id=provider_contact_id,
            origin=origin,
            ai_enabled=ai_enabled,
            metadata_json=_json_dump(metadata),
        )
        self._db.add(session)
        self._db.flush()
        self._db.add(
            AgenteWhatsAppContext(
                id=str(uuid.uuid4()),
                session_id=session.id,
                customer_id=session.customer_id,
            )
        )
        self.add_event(
            event_type="agente_whatsapp_session_started",
            session_id=session.id,
            customer_id=session.customer_id,
            source=origin,
            payload={"phone": normalized_phone, "provider": provider},
            flush=False,
        )
        return session, True

    def update_session(self, session: AgenteWhatsAppSession, data: dict[str, Any]) -> AgenteWhatsAppSession:
        metadata = data.pop("metadata", None)
        for key, value in data.items():
            if value is not None:
                setattr(session, key, value)
        if metadata is not None:
            session.metadata_json = _json_dump(metadata)
        session.updated_at = datetime.now(timezone.utc)
        return session

    def list_messages(self, session_id: str, *, limit: int = 100) -> list[AgenteWhatsAppMessage]:
        return (
            self._db.query(AgenteWhatsAppMessage)
            .filter(AgenteWhatsAppMessage.session_id == session_id)
            .order_by(AgenteWhatsAppMessage.created_at.asc())
            .limit(limit)
            .all()
        )

    def add_message(
        self,
        session: AgenteWhatsAppSession,
        *,
        direction: str,
        sender_type: str,
        message_type: str = "text",
        body: str | None = None,
        media_url: str | None = None,
        provider_message_id: str | None = None,
        provider_status: str | None = None,
        raw_payload: dict[str, Any] | None = None,
    ) -> AgenteWhatsAppMessage:
        if provider_message_id:
            existing = (
                self._db.query(AgenteWhatsAppMessage)
                .filter(AgenteWhatsAppMessage.provider_message_id == provider_message_id)
                .first()
            )
            if existing:
                return existing

        now = datetime.now(timezone.utc)
        message = AgenteWhatsAppMessage(
            id=str(uuid.uuid4()),
            session_id=session.id,
            customer_id=session.customer_id,
            direction=direction,
            sender_type=sender_type,
            message_type=message_type,
            body=body,
            media_url=media_url,
            provider_message_id=provider_message_id,
            provider_status=provider_status,
            raw_payload_json=_json_dump(raw_payload),
            created_at=now,
        )
        self._db.add(message)
        session.last_message_at = now
        session.updated_at = now
        self.add_event(
            event_type="agente_whatsapp_message_received" if direction == "inbound" else "agente_whatsapp_message_sent",
            session_id=session.id,
            customer_id=session.customer_id,
            source="manual",
            payload={"message_id": message.id, "sender_type": sender_type, "message_type": message_type},
            flush=False,
        )
        return message

    def process_meta_webhook(self, payload: dict[str, Any]) -> dict[str, int]:
        received = 0
        duplicates = 0
        status_updates = 0

        for entry in payload.get("entry", []) or []:
            for change in entry.get("changes", []) or []:
                value = change.get("value") or {}
                contact_names = {
                    (contact.get("wa_id") or contact.get("input") or ""): (
                        ((contact.get("profile") or {}).get("name")) or None
                    )
                    for contact in value.get("contacts", []) or []
                }

                for status_item in value.get("statuses", []) or []:
                    if self.update_message_status(
                        provider_message_id=status_item.get("id"),
                        provider_status=status_item.get("status"),
                        raw_payload=status_item,
                    ):
                        status_updates += 1

                for item in value.get("messages", []) or []:
                    phone = normalize_phone(item.get("from"))
                    provider_message_id = item.get("id")
                    if not phone or not provider_message_id:
                        continue
                    if self._message_exists(provider_message_id):
                        duplicates += 1
                        continue

                    session, _created = self.get_or_create_session(
                        phone=phone,
                        provider="official",
                        provider_contact_id=item.get("from"),
                        origin="inbound",
                        metadata={"source": "meta_webhook"},
                    )
                    customer = session.customer
                    display_name = contact_names.get(item.get("from") or phone)
                    if customer and display_name and customer.name.startswith("Cliente WhatsApp"):
                        customer.name = display_name

                    message_type, body, media_url = self._extract_meta_message_content(item)
                    self.add_message(
                        session,
                        direction="inbound",
                        sender_type="customer",
                        message_type=message_type,
                        body=body,
                        media_url=media_url,
                        provider_message_id=provider_message_id,
                        provider_status="received",
                        raw_payload=item,
                    )
                    received += 1

        return {"received": received, "duplicates": duplicates, "status_updates": status_updates}

    def process_evolution_webhook(self, payload: dict[str, Any]) -> dict[str, int]:
        received = 0
        duplicates = 0
        items = self._extract_evolution_items(payload)
        for item in items:
            key = item.get("key") or {}
            if key.get("fromMe") is True:
                continue

            remote = key.get("remoteJid") or item.get("remoteJid") or item.get("from")
            phone = normalize_phone(str(remote).split("@", 1)[0] if remote else "")
            provider_message_id = key.get("id") or item.get("id") or item.get("messageId")
            if not phone or not provider_message_id:
                continue
            if self._message_exists(provider_message_id):
                duplicates += 1
                continue

            session, _created = self.get_or_create_session(
                phone=phone,
                provider="evolution",
                provider_contact_id=str(remote) if remote else None,
                origin="inbound",
                metadata={"source": "evolution_webhook", "instance": payload.get("instance")},
            )
            if session.customer and item.get("pushName") and session.customer.name.startswith("Cliente WhatsApp"):
                session.customer.name = item.get("pushName")

            message_type, body, media_url = self._extract_evolution_message_content(item)
            self.add_message(
                session,
                direction="inbound",
                sender_type="customer",
                message_type=message_type,
                body=body,
                media_url=media_url,
                provider_message_id=str(provider_message_id),
                provider_status="received",
                raw_payload=item,
            )
            received += 1

        return {"received": received, "duplicates": duplicates, "status_updates": 0}

    def update_message_status(
        self,
        *,
        provider_message_id: str | None,
        provider_status: str | None,
        raw_payload: dict[str, Any] | None = None,
    ) -> bool:
        if not provider_message_id or not provider_status:
            return False
        message = (
            self._db.query(AgenteWhatsAppMessage)
            .filter(AgenteWhatsAppMessage.provider_message_id == provider_message_id)
            .first()
        )
        if not message:
            return False
        message.provider_status = provider_status
        now = datetime.now(timezone.utc)
        if provider_status == "delivered" and not message.delivered_at:
            message.delivered_at = now
        if provider_status == "read" and not message.read_at:
            message.read_at = now
        if raw_payload:
            message.raw_payload_json = _json_dump(raw_payload)
        return True

    def _message_exists(self, provider_message_id: str | None) -> bool:
        if not provider_message_id:
            return False
        return (
            self._db.query(AgenteWhatsAppMessage.id)
            .filter(AgenteWhatsAppMessage.provider_message_id == provider_message_id)
            .first()
            is not None
        )

    @staticmethod
    def _extract_meta_message_content(item: dict[str, Any]) -> tuple[str, str | None, str | None]:
        message_type = item.get("type") or "text"
        if message_type == "text":
            return "text", ((item.get("text") or {}).get("body")), None
        if message_type in {"image", "audio", "video", "document", "sticker"}:
            media = item.get(message_type) or {}
            body = media.get("caption") or media.get("filename")
            media_url = media.get("link") or media.get("id")
            return message_type, body, media_url
        if message_type == "button":
            button = item.get("button") or {}
            return "button", button.get("text") or button.get("payload"), None
        if message_type == "interactive":
            interactive = item.get("interactive") or {}
            return "interactive", json.dumps(interactive, ensure_ascii=False), None
        return str(message_type), json.dumps(item.get(message_type) or {}, ensure_ascii=False), None

    @staticmethod
    def _extract_evolution_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            if isinstance(data.get("messages"), list):
                return [item for item in data["messages"] if isinstance(item, dict)]
            return [data]
        if isinstance(payload.get("messages"), list):
            return [item for item in payload["messages"] if isinstance(item, dict)]
        return [payload]

    @staticmethod
    def _extract_evolution_message_content(item: dict[str, Any]) -> tuple[str, str | None, str | None]:
        message = item.get("message") or {}
        if isinstance(message.get("conversation"), str):
            return "text", message.get("conversation"), None
        if isinstance(message.get("extendedTextMessage"), dict):
            return "text", message["extendedTextMessage"].get("text"), None

        for key, message_type in [
            ("imageMessage", "image"),
            ("audioMessage", "audio"),
            ("videoMessage", "video"),
            ("documentMessage", "document"),
            ("stickerMessage", "sticker"),
        ]:
            media = message.get(key)
            if isinstance(media, dict):
                return message_type, media.get("caption") or media.get("fileName"), media.get("url") or media.get("mediaKey")

        if isinstance(item.get("messageText"), str):
            return "text", item.get("messageText"), None
        if isinstance(item.get("text"), str):
            return "text", item.get("text"), None
        return "unknown", json.dumps(message or item, ensure_ascii=False), None

    def add_event(
        self,
        *,
        event_type: str,
        session_id: str | None = None,
        customer_id: str | None = None,
        order_id: str | None = None,
        source: str = "agente_whatsapp",
        payload: dict[str, Any] | None = None,
        flush: bool = True,
    ) -> AgenteWhatsAppEvent:
        event = AgenteWhatsAppEvent(
            id=str(uuid.uuid4()),
            session_id=session_id,
            customer_id=customer_id,
            order_id=order_id,
            event_type=event_type,
            source=source,
            payload_json=_json_dump(payload),
        )
        self._db.add(event)
        if flush:
            self._db.flush()
        return event

    def serialize_session(self, session: AgenteWhatsAppSession) -> dict[str, Any]:
        return {
            "id": session.id,
            "customer_id": session.customer_id,
            "customer_name": session.customer.name if session.customer else None,
            "phone": session.phone,
            "provider": session.provider,
            "provider_contact_id": session.provider_contact_id,
            "status": session.status,
            "origin": session.origin,
            "current_intent": session.current_intent,
            "last_message_at": session.last_message_at,
            "assigned_admin_id": session.assigned_admin_id,
            "ai_enabled": bool(session.ai_enabled),
            "automation_blocked": bool(session.automation_blocked),
            "metadata": _json_load(session.metadata_json),
            "created_at": session.created_at,
            "updated_at": session.updated_at,
        }

    def serialize_message(self, message: AgenteWhatsAppMessage) -> dict[str, Any]:
        return {
            "id": message.id,
            "session_id": message.session_id,
            "customer_id": message.customer_id,
            "direction": message.direction,
            "sender_type": message.sender_type,
            "message_type": message.message_type,
            "body": message.body,
            "media_url": message.media_url,
            "provider_message_id": message.provider_message_id,
            "provider_status": message.provider_status,
            "error": message.error,
            "raw_payload": _json_load(message.raw_payload_json),
            "created_at": message.created_at,
            "delivered_at": message.delivered_at,
            "read_at": message.read_at,
        }

    def serialize_event(self, event: AgenteWhatsAppEvent) -> dict[str, Any]:
        return {
            "id": event.id,
            "session_id": event.session_id,
            "customer_id": event.customer_id,
            "order_id": event.order_id,
            "event_type": event.event_type,
            "source": event.source,
            "payload": _json_load(event.payload_json),
            "processed_at": event.processed_at,
            "created_at": event.created_at,
        }

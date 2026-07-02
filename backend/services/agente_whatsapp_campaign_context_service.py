from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.agente_whatsapp import AgenteWhatsAppContext, AgenteWhatsAppMessage, AgenteWhatsAppSession


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _json_dump(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, default=str)


def _json_load(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _snapshot_text(value: str | None, *, limit: int = 1600) -> str | None:
    text_value = (value or "").strip()
    if not text_value:
        return None
    return text_value[:limit]


class AgenteWhatsAppCampaignContextService:
    """Resolve campaign context without trusting mutable campaign/template state."""

    def __init__(self, db: Session):
        self._db = db
        self._settings = get_settings()

    def resolve_for_message(self, message_id: str, *, persist: bool = True) -> dict[str, Any]:
        message = self._db.query(AgenteWhatsAppMessage).filter(AgenteWhatsAppMessage.id == message_id).first()
        if not message:
            raise ValueError("Mensagem do AGENTE WHATSAPP nao encontrada.")
        return self.resolve_message(message, persist=persist)

    def resolve_latest_for_session(self, session_id: str, *, persist: bool = True) -> dict[str, Any]:
        message = (
            self._db.query(AgenteWhatsAppMessage)
            .filter(
                AgenteWhatsAppMessage.session_id == session_id,
                AgenteWhatsAppMessage.direction == "inbound",
            )
            .order_by(AgenteWhatsAppMessage.created_at.desc())
            .first()
        )
        if not message:
            return self._empty_context("no_inbound_message")
        return self.resolve_message(message, persist=persist)

    def resolve_message(self, message: AgenteWhatsAppMessage, *, persist: bool = True) -> dict[str, Any]:
        if not self._settings.WHATSAPP_CAMPAIGN_CONTEXT_ENABLED:
            return self._empty_context("disabled")

        delivery = None
        source = "none"
        candidates: list[Any] = []

        if message.campaign_delivery_id:
            delivery = self._delivery_by_id(message.campaign_delivery_id)
            source = "message_link" if delivery else "message_link_missing"

        if not delivery and message.quoted_provider_message_id:
            delivery = self._delivery_by_quoted_provider_id(message.quoted_provider_message_id)
            source = "quoted_provider_message_id" if delivery else "quoted_provider_message_id_missing"

        if not delivery:
            candidates = self._recent_deliveries_for_session(message)
            narrowed = self._narrow_window_candidates(candidates)
            if len(narrowed) == 1:
                delivery = narrowed[0]
                source = "window_unique"
            elif len(narrowed) > 1:
                source = "window_ambiguous"
                payload = self._payload(
                    status="ambiguous",
                    source=source,
                    message=message,
                    candidates=narrowed,
                    delivery=None,
                )
                if persist:
                    self._persist_context(message, payload, delivery=None)
                return payload
            else:
                source = "not_found"

        payload = self._payload(
            status="resolved" if delivery else "not_found",
            source=source,
            message=message,
            candidates=candidates,
            delivery=delivery,
        )
        if persist:
            self._persist_context(message, payload, delivery=delivery)
        return payload

    def _delivery_by_id(self, delivery_id: str):
        WhatsAppCampaignDelivery, _WhatsAppCampaign = self._models()
        return (
            self._db.query(WhatsAppCampaignDelivery)
            .filter(WhatsAppCampaignDelivery.id == delivery_id)
            .first()
        )

    def _delivery_by_quoted_provider_id(self, provider_message_id: str):
        WhatsAppCampaignDelivery, _WhatsAppCampaign = self._models()
        quoted_message = (
            self._db.query(AgenteWhatsAppMessage)
            .filter(AgenteWhatsAppMessage.provider_message_id == provider_message_id)
            .first()
        )
        if quoted_message and quoted_message.campaign_delivery_id:
            return self._delivery_by_id(quoted_message.campaign_delivery_id)
        return (
            self._db.query(WhatsAppCampaignDelivery)
            .filter(WhatsAppCampaignDelivery.provider_message_id == provider_message_id)
            .order_by(WhatsAppCampaignDelivery.created_at.desc())
            .first()
        )

    def _recent_deliveries_for_session(self, message: AgenteWhatsAppMessage) -> list[Any]:
        WhatsAppCampaignDelivery, _WhatsAppCampaign = self._models()
        session = message.session
        phone = session.phone if session else None
        if not phone:
            return []
        window_start = (message.created_at or _now_utc()) - timedelta(hours=max(1, self._settings.WHATSAPP_CAMPAIGN_CONTEXT_WINDOW_HOURS))
        return (
            self._db.query(WhatsAppCampaignDelivery)
            .filter(
                WhatsAppCampaignDelivery.phone_normalized == phone,
                or_(
                    WhatsAppCampaignDelivery.sent_at >= window_start,
                    WhatsAppCampaignDelivery.created_at >= window_start,
                ),
            )
            .order_by(WhatsAppCampaignDelivery.sent_at.desc().nullslast(), WhatsAppCampaignDelivery.created_at.desc())
            .limit(10)
            .all()
        )

    def _narrow_window_candidates(self, candidates: list[Any]) -> list[Any]:
        if not candidates:
            return []
        priority_hours = max(1, self._settings.WHATSAPP_CAMPAIGN_PRIORITY_WINDOW_HOURS)
        priority_start = _now_utc() - timedelta(hours=priority_hours)
        priority = [
            item
            for item in candidates
            if (item.sent_at or item.created_at or _now_utc()) >= priority_start
        ]
        return priority or candidates

    def _payload(
        self,
        *,
        status: str,
        source: str,
        message: AgenteWhatsAppMessage,
        candidates: list[Any],
        delivery: Any | None,
    ) -> dict[str, Any]:
        selected = self._serialize_delivery(delivery) if delivery else None
        candidate_payload = [self._serialize_delivery(item) for item in candidates[:5]]
        return {
            "status": status,
            "source": source,
            "message_id": message.id,
            "session_id": message.session_id,
            "campaign_delivery_id": selected.get("id") if selected else None,
            "campaign_id": selected.get("campaign_id") if selected else None,
            "selected": selected,
            "candidates": candidate_payload,
            "ambiguous": status == "ambiguous",
            "instructions": self._instructions(status, selected, candidate_payload),
            "resolved_at": _now_utc(),
        }

    def _serialize_delivery(self, delivery: Any | None) -> dict[str, Any]:
        if not delivery:
            return {}
        return {
            "id": delivery.id,
            "campaign_id": delivery.campaign_id,
            "template_id": delivery.template_id,
            "whatsapp_message_id": delivery.whatsapp_message_id,
            "provider": delivery.provider,
            "provider_message_id": delivery.provider_message_id,
            "phone_normalized": delivery.phone_normalized,
            "recipient_name": delivery.recipient_name,
            "campaign_name": delivery.campaign_name_snapshot,
            "template_name": delivery.template_name_snapshot,
            "message_type": delivery.message_type,
            "message_text": _snapshot_text(delivery.message_text_snapshot),
            "caption": _snapshot_text(delivery.caption_snapshot, limit=600),
            "media_type": delivery.media_type,
            "media_url": delivery.media_url,
            "status": delivery.status,
            "sent_at": delivery.sent_at,
            "delivered_at": delivery.delivered_at,
            "read_at": delivery.read_at,
            "replied_at": delivery.replied_at,
            "failed_at": delivery.failed_at,
            "variables": _json_load(delivery.variables_json),
        }

    def _instructions(self, status: str, selected: dict[str, Any] | None, candidates: list[dict[str, Any]]) -> list[str]:
        if status == "resolved" and selected:
            return [
                "Usar somente o snapshot selecionado da campanha como evidencia comercial.",
                "Nao inventar preco, validade, cupom, brinde ou produto que nao esteja no snapshot.",
                "Se o cliente pedir algo alem do snapshot, consultar ferramentas reais do ERP antes de afirmar.",
            ]
        if status == "ambiguous" and candidates:
            return [
                "Existem multiplas campanhas recentes possiveis.",
                "Nao escolher oferta por conta propria.",
                "Perguntar de qual campanha/oferta o cliente esta falando antes de prometer valor ou beneficio.",
            ]
        return [
            "Nenhuma campanha segura foi encontrada.",
            "Nao atribuir a conversa a uma campanha nem inventar oferta.",
            "Usar apenas ferramentas reais do ERP para responder sobre preco, produto, cupom ou disponibilidade.",
        ]

    def _persist_context(self, message: AgenteWhatsAppMessage, payload: dict[str, Any], *, delivery: Any | None) -> None:
        session = message.session
        if not session:
            return
        if delivery:
            message.campaign_delivery_id = message.campaign_delivery_id or delivery.id
            message.campaign_id = message.campaign_id or delivery.campaign_id
            if not delivery.replied_at:
                delivery.replied_at = message.created_at or _now_utc()
            delivery.conversation_id = delivery.conversation_id or session.id
            delivery.updated_at = _now_utc()

        context = session.context
        if not context:
            context = AgenteWhatsAppContext(
                id=str(uuid.uuid4()),
                session_id=session.id,
                customer_id=session.customer_id,
            )
            self._db.add(context)

        short_context = _json_load(context.short_context_json)
        long_context = _json_load(context.long_context_json)
        short_context["campaign_context"] = payload
        long_context["last_campaign_context"] = payload
        context.short_context_json = _json_dump(short_context)
        context.long_context_json = _json_dump(long_context)
        context.updated_at = _now_utc()
        self._db.flush()

    def _empty_context(self, source: str) -> dict[str, Any]:
        return {
            "status": "not_found" if source != "disabled" else "disabled",
            "source": source,
            "message_id": None,
            "session_id": None,
            "campaign_delivery_id": None,
            "campaign_id": None,
            "selected": None,
            "candidates": [],
            "ambiguous": False,
            "instructions": self._instructions("not_found", None, []),
            "resolved_at": _now_utc(),
        }

    @staticmethod
    def _models():
        from backend.routes.whatsapp_marketing import WhatsAppCampaign, WhatsAppCampaignDelivery

        return WhatsAppCampaignDelivery, WhatsAppCampaign

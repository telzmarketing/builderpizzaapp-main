from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.core.local_time import local_period_bounds, local_today
from backend.models.agente_whatsapp import (
    AgenteWhatsAppAISettings,
    AgenteWhatsAppCampaign,
    AgenteWhatsAppContext,
    AgenteWhatsAppEvent,
    AgenteWhatsAppMessage,
    AgenteWhatsAppOutbox,
    AgenteWhatsAppSession,
    AgenteWhatsAppStory,
)
from backend.models.customer import Customer
from backend.models.customer_event import CustomerEvent
from backend.models.customer_identity import CustomerChannel
from backend.models.loyalty import CustomerLoyalty
from backend.models.order import Order
from backend.services.agente_whatsapp_outbox_service import AgenteWhatsAppOutboxService
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
        today_start, _today_end = local_period_bounds(local_today(), local_today())
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

    def operational_metrics(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        start_dt, end_dt = local_period_bounds(local_today(), local_today())
        active_statuses = ["open", "waiting_human", "human", "ai_paused"]
        online_since = now - timedelta(minutes=5)

        open_q = self._db.query(AgenteWhatsAppSession).filter(AgenteWhatsAppSession.status.in_(active_statuses))
        waiting_response = (
            self._db.query(func.count(AgenteWhatsAppSession.id))
            .filter(AgenteWhatsAppSession.status == "waiting_human")
            .scalar()
            or 0
        )
        finalized_today = (
            self._db.query(func.count(AgenteWhatsAppSession.id))
            .filter(
                AgenteWhatsAppSession.status == "closed",
                AgenteWhatsAppSession.updated_at >= start_dt,
                AgenteWhatsAppSession.updated_at <= end_dt,
            )
            .scalar()
            or 0
        )
        unread_messages = (
            self._db.query(func.count(AgenteWhatsAppMessage.id))
            .filter(
                AgenteWhatsAppMessage.direction == "inbound",
                AgenteWhatsAppMessage.read_at.is_(None),
            )
            .scalar()
            or 0
        )
        ai_settings = self._db.query(AgenteWhatsAppAISettings).filter(AgenteWhatsAppAISettings.id == "default").first()
        chatbots_online = 1 if ai_settings is None or ai_settings.enabled else 0
        active_ai_agents = (
            open_q.filter(AgenteWhatsAppSession.ai_enabled.is_(True)).count()
        )
        human_attendants_online = (
            self._db.query(func.count(func.distinct(AgenteWhatsAppSession.assigned_admin_id)))
            .filter(
                AgenteWhatsAppSession.status == "human",
                AgenteWhatsAppSession.assigned_admin_id.isnot(None),
                AgenteWhatsAppSession.last_message_at >= online_since,
            )
            .scalar()
            or 0
        )
        conversations_online = (
            self._db.query(func.count(AgenteWhatsAppSession.id))
            .filter(
                AgenteWhatsAppSession.status.in_(active_statuses),
                AgenteWhatsAppSession.last_message_at >= online_since,
            )
            .scalar()
            or 0
        )

        return {
            "chatbots_online": chatbots_online,
            "conversations_online": conversations_online,
            "active_attendances": open_q.count(),
            "waiting_response": waiting_response,
            "finalized_today": finalized_today,
            "unread_messages": unread_messages,
            "avg_response_time_seconds": self._avg_response_time_seconds(start_dt, end_dt),
            "avg_attendance_time_seconds": self._avg_attendance_time_seconds(start_dt, end_dt),
            "simultaneous_attendances": open_q.count(),
            "active_ai_agents": active_ai_agents,
            "human_attendants_online": human_attendants_online,
            "generated_at": now,
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

    def campaign_templates(self) -> list[dict[str, str]]:
        return [
            {
                "id": "recompra",
                "name": "Recompra",
                "category": "retencao",
                "body": "Oi {{primeiro_nome}}, bateu aquela vontade de pizza hoje? Posso te mandar nossas opcoes mais pedidas.",
            },
            {
                "id": "promocao",
                "name": "Promocao do dia",
                "category": "vendas",
                "body": "Oi {{primeiro_nome}}, temos uma promocao especial hoje. Quer que eu te envie o cardapio?",
            },
            {
                "id": "cupom",
                "name": "Cupom relampago",
                "category": "marketing",
                "body": "Oi {{primeiro_nome}}, se pedir hoje pelo WhatsApp eu consigo te ajudar com uma oferta especial.",
            },
        ]

    def story_templates(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "promocao-dia",
                "name": "Promocao do dia",
                "title": "Promocao do dia",
                "caption": "Hoje tem oferta especial no Del Basito. Chame aqui e faca seu pedido.",
                "cta_text": "Pedir agora",
                "cta_url": None,
            },
            {
                "id": "pizza-mais-vendida",
                "name": "Pizza mais vendida",
                "title": "Mais pedida da noite",
                "caption": "A queridinha da casa esta saindo muito hoje. Quer garantir a sua?",
                "cta_text": "Ver cardapio",
                "cta_url": None,
            },
            {
                "id": "cupom-relampago",
                "name": "Cupom relampago",
                "title": "Oferta por tempo limitado",
                "caption": "Tem condicao especial por tempo limitado. Responda este status para pedir.",
                "cta_text": "Quero a oferta",
                "cta_url": None,
            },
        ]

    def automation_templates(self) -> list[dict[str, Any]]:
        return [
            {
                "key": "recompra",
                "name": "Recompra",
                "trigger": "last_order_after_14_days",
                "cooldown_days": 7,
                "description": "Clientes que compraram antes e ficaram alguns dias sem novo pedido.",
                "default_message": "Oi {{primeiro_nome}}, passando para te lembrar das pizzas que voce gosta. Quer repetir o ultimo pedido ou ver o cardapio de hoje?",
            },
            {
                "key": "reativacao",
                "name": "Reativacao",
                "trigger": "last_order_after_30_days",
                "cooldown_days": 14,
                "description": "Clientes inativos ha mais tempo, com abordagem mais cuidadosa.",
                "default_message": "Oi {{primeiro_nome}}, sentimos sua falta por aqui. Quer que eu te envie uma sugestao especial para hoje?",
            },
            {
                "key": "carrinho_abandonado",
                "name": "Carrinho abandonado",
                "trigger": "cart_item_added_without_order",
                "cooldown_days": 1,
                "description": "Clientes que adicionaram produto ao carrinho e nao finalizaram pedido.",
                "default_message": "Oi {{primeiro_nome}}, vi que voce estava escolhendo seu pedido. Quer ajuda para finalizar?",
            },
            {
                "key": "aniversario",
                "name": "Aniversario",
                "trigger": "birthday_today",
                "cooldown_days": 365,
                "description": "Clientes aniversariantes do dia.",
                "default_message": "Feliz aniversario, {{primeiro_nome}}! Que seu dia seja incrivel. Quer comemorar com uma pizza especial?",
            },
            {
                "key": "fidelidade",
                "name": "Fidelidade",
                "trigger": "loyalty_points_available",
                "cooldown_days": 7,
                "description": "Clientes com pontos de fidelidade disponiveis.",
                "default_message": "Oi {{primeiro_nome}}, voce tem {{pontos}} pontos no programa de fidelidade. Quer ver beneficios disponiveis?",
            },
        ]

    def run_commercial_automation(
        self,
        *,
        key: str,
        limit: int = 50,
        dry_run: bool = False,
        message_template: str | None = None,
    ) -> dict[str, Any]:
        template = self._automation_template(key)
        if not template:
            raise ValueError("Automacao comercial nao encontrada.")
        candidates = self._automation_candidates(key, limit=limit)
        default_message = message_template or template["default_message"]
        queued = 0
        skipped = 0

        if not dry_run:
            for candidate in candidates:
                if self._automation_recently_sent(key, candidate["customer_id"], template["cooldown_days"]):
                    skipped += 1
                    continue
                session, _created = self.get_or_create_session(
                    phone=candidate["phone"],
                    customer_id=candidate["customer_id"],
                    provider="official",
                    origin="campaign",
                    metadata={"automation_key": key, "automation_name": template["name"]},
                )
                body = self._render_automation_template(default_message, candidate)
                self.add_message(
                    session,
                    direction="outbound",
                    sender_type="system",
                    message_type="text",
                    body=body,
                    provider_status="queued",
                    raw_payload={
                        "source": "agente_whatsapp_automation",
                        "automation_key": key,
                        "automation_name": template["name"],
                        "recipient_phone": candidate["phone"],
                    },
                )
                self.add_event(
                    event_type=f"automation_{key}",
                    session_id=session.id,
                    customer_id=candidate["customer_id"],
                    source="agente_whatsapp_automation",
                    payload={"automation_key": key, "phone": candidate["phone"]},
                    flush=False,
                )
                queued += 1

        enqueue_result = {"enqueued": 0}
        if queued:
            enqueue_result = AgenteWhatsAppOutboxService(self._db).enqueue_queued_messages(limit=max(queued, 20))
        self._db.flush()
        return {
            "key": key,
            "dry_run": dry_run,
            "eligible": len(candidates),
            "queued": queued,
            "skipped": skipped,
            "enqueued": enqueue_result["enqueued"],
            "candidates": candidates[:50],
        }

    def run_due_commercial_automations(self, *, limit_per_automation: int = 30) -> dict[str, Any]:
        results = [
            self.run_commercial_automation(key=item["key"], limit=limit_per_automation, dry_run=False)
            for item in self.automation_templates()
        ]
        return {
            "processed": len(results),
            "queued": sum(item["queued"] for item in results),
            "enqueued": sum(item["enqueued"] for item in results),
            "automations": results,
        }

    def _automation_template(self, key: str) -> dict[str, Any] | None:
        return next((item for item in self.automation_templates() if item["key"] == key), None)

    def _automation_candidates(self, key: str, *, limit: int) -> list[dict[str, Any]]:
        if key == "recompra":
            cutoff = datetime.now(timezone.utc) - timedelta(days=14)
            q = self._base_customer_query().filter(Customer.last_order_at.isnot(None), Customer.last_order_at <= cutoff)
        elif key == "reativacao":
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            q = self._base_customer_query().filter(Customer.last_order_at.isnot(None), Customer.last_order_at <= cutoff)
        elif key == "aniversario":
            today = local_today()
            q = self._base_customer_query().filter(
                Customer.birth_date.isnot(None),
                func.extract("month", Customer.birth_date) == today.month,
                func.extract("day", Customer.birth_date) == today.day,
            )
        elif key == "fidelidade":
            q = (
                self._base_customer_query()
                .join(CustomerLoyalty, CustomerLoyalty.customer_id == Customer.id)
                .filter(CustomerLoyalty.total_points > 0)
            )
        elif key == "carrinho_abandonado":
            return self._abandoned_cart_candidates(limit=limit)
        else:
            return []

        customers = q.order_by(Customer.last_order_at.asc().nullslast(), Customer.created_at.desc()).limit(limit * 2).all()
        return [self._customer_candidate(customer, key) for customer in customers if self._customer_has_whatsapp_permission(customer)][:limit]

    def _base_customer_query(self):
        return self._db.query(Customer).filter(Customer.phone.isnot(None), Customer.phone != "")

    def _abandoned_cart_candidates(self, *, limit: int) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=60)
        rows = (
            self._db.query(CustomerEvent, Customer)
            .join(Customer, Customer.id == CustomerEvent.customer_id)
            .filter(
                CustomerEvent.event_type.in_(["cart_item_added", "add_to_cart"]),
                CustomerEvent.created_at <= cutoff,
                Customer.phone.isnot(None),
                Customer.phone != "",
            )
            .order_by(CustomerEvent.created_at.desc())
            .limit(limit * 4)
            .all()
        )
        seen: set[str] = set()
        candidates: list[dict[str, Any]] = []
        for event, customer in rows:
            if customer.id in seen or not self._customer_has_whatsapp_permission(customer):
                continue
            order_after_cart = (
                self._db.query(func.count(Order.id))
                .filter(Order.customer_id == customer.id, Order.created_at >= event.created_at)
                .scalar()
                or 0
            )
            if order_after_cart:
                continue
            seen.add(customer.id)
            item = self._customer_candidate(customer, "carrinho_abandonado")
            item["reason"] = "Produto adicionado ao carrinho sem pedido posterior."
            candidates.append(item)
            if len(candidates) >= limit:
                break
        return candidates

    def _customer_candidate(self, customer: Customer, key: str) -> dict[str, Any]:
        loyalty_points = customer.loyalty_account.total_points if getattr(customer, "loyalty_account", None) else None
        reasons = {
            "recompra": "Cliente com historico de compra e sem pedido recente.",
            "reativacao": "Cliente inativo ha mais de 30 dias.",
            "aniversario": "Cliente aniversariante hoje.",
            "fidelidade": "Cliente com pontos de fidelidade disponiveis.",
        }
        return {
            "customer_id": customer.id,
            "name": customer.name,
            "phone": normalize_phone(customer.phone),
            "reason": reasons.get(key, "Cliente elegivel."),
            "last_order_at": customer.last_order_at,
            "total_orders": customer.total_orders,
            "total_spent": customer.total_spent,
            "loyalty_points": loyalty_points,
        }

    def _customer_has_whatsapp_permission(self, customer: Customer) -> bool:
        if customer.marketing_whatsapp_consent or customer.source == "agente_whatsapp":
            return True
        channel = (
            self._db.query(CustomerChannel)
            .filter(CustomerChannel.customer_id == customer.id, CustomerChannel.channel == "whatsapp")
            .first()
        )
        return bool(channel and (channel.marketing_consent or channel.source == "agente_whatsapp"))

    def _automation_recently_sent(self, key: str, customer_id: str, cooldown_days: int) -> bool:
        since = datetime.now(timezone.utc) - timedelta(days=max(1, cooldown_days))
        return (
            self._db.query(func.count(AgenteWhatsAppEvent.id))
            .filter(
                AgenteWhatsAppEvent.customer_id == customer_id,
                AgenteWhatsAppEvent.event_type == f"automation_{key}",
                AgenteWhatsAppEvent.created_at >= since,
            )
            .scalar()
            or 0
        ) > 0

    def _render_automation_template(self, template: str, candidate: dict[str, Any]) -> str:
        name = candidate.get("name") or "cliente"
        first_name = name.split(" ")[0]
        return (
            template.replace("{{nome}}", name)
            .replace("{{primeiro_nome}}", first_name)
            .replace("{{telefone}}", candidate.get("phone") or "")
            .replace("{{pontos}}", str(candidate.get("loyalty_points") or 0))
        )

    def list_campaigns(self, *, limit: int = 50) -> list[AgenteWhatsAppCampaign]:
        return (
            self._db.query(AgenteWhatsAppCampaign)
            .order_by(AgenteWhatsAppCampaign.updated_at.desc().nullslast(), AgenteWhatsAppCampaign.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_campaign(self, campaign_id: str) -> AgenteWhatsAppCampaign | None:
        return self._db.query(AgenteWhatsAppCampaign).filter(AgenteWhatsAppCampaign.id == campaign_id).first()

    def create_campaign(self, data: dict[str, Any], *, created_by: str | None = None) -> AgenteWhatsAppCampaign:
        audience_type = data.get("audience_type") or "manual"
        template = (data.get("message_template") or "").strip()
        if not template:
            raise ValueError("Mensagem da campanha e obrigatoria.")

        phones = self._normalize_phone_list(data.get("phones") or [])
        if audience_type == "manual" and not phones:
            raise ValueError("Informe pelo menos um telefone para campanha manual.")

        scheduled_at = data.get("scheduled_at")
        if scheduled_at and not scheduled_at.tzinfo:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        status = "scheduled" if scheduled_at and scheduled_at > now else "draft"
        campaign = AgenteWhatsAppCampaign(
            id=str(uuid.uuid4()),
            name=data["name"].strip(),
            status=status,
            campaign_type=data.get("campaign_type") or "manual",
            audience_json=_json_dump({
                "audience_type": audience_type,
                "phones": phones,
                "message_template": template,
            }),
            scheduled_at=scheduled_at,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self._db.add(campaign)
        self._db.flush()
        return campaign

    def dispatch_campaign(self, campaign: AgenteWhatsAppCampaign, *, force: bool = False) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        if campaign.scheduled_at and campaign.scheduled_at > now and not force:
            campaign.status = "scheduled"
            campaign.updated_at = now
            self._db.flush()
            return {
                "campaign_id": campaign.id,
                "status": campaign.status,
                "recipients": 0,
                "queued": 0,
                "skipped": 0,
                "enqueued": 0,
            }

        audience = _json_load(campaign.audience_json)
        recipients = self._resolve_campaign_recipients(audience)
        queued = 0
        skipped = 0
        template = audience.get("message_template") or ""
        campaign.status = "sending"
        campaign.updated_at = now

        for recipient in recipients:
            phone = recipient["phone"]
            if self._campaign_message_exists(campaign.id, phone):
                skipped += 1
                continue
            session, _created = self.get_or_create_session(
                phone=phone,
                customer_id=recipient.get("customer_id"),
                provider="official",
                origin="campaign",
                metadata={"campaign_id": campaign.id, "campaign_name": campaign.name},
            )
            body = self._render_campaign_template(template, recipient)
            self.add_message(
                session,
                direction="outbound",
                sender_type="system",
                message_type="text",
                body=body,
                provider_status="queued",
                raw_payload={
                    "source": "agente_whatsapp_campaign",
                    "campaign_id": campaign.id,
                    "campaign_name": campaign.name,
                    "recipient_phone": phone,
                },
            )
            queued += 1

        enqueue_result = AgenteWhatsAppOutboxService(self._db).enqueue_queued_messages(limit=max(queued, 20))
        campaign.sent_count = (campaign.sent_count or 0) + queued
        campaign.status = "queued" if queued else "sent"
        campaign.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        return {
            "campaign_id": campaign.id,
            "status": campaign.status,
            "recipients": len(recipients),
            "queued": queued,
            "skipped": skipped,
            "enqueued": enqueue_result["enqueued"],
        }

    def process_scheduled_campaigns(self, *, limit: int = 10) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        rows = (
            self._db.query(AgenteWhatsAppCampaign)
            .filter(
                AgenteWhatsAppCampaign.status == "scheduled",
                AgenteWhatsAppCampaign.scheduled_at.isnot(None),
                AgenteWhatsAppCampaign.scheduled_at <= now,
            )
            .order_by(AgenteWhatsAppCampaign.scheduled_at.asc())
            .limit(limit)
            .all()
        )
        results = [self.dispatch_campaign(campaign, force=True) for campaign in rows]
        return {
            "processed": len(results),
            "queued": sum(item["queued"] for item in results),
            "enqueued": sum(item["enqueued"] for item in results),
            "campaigns": results,
        }

    def serialize_campaign(self, campaign: AgenteWhatsAppCampaign) -> dict[str, Any]:
        audience = _json_load(campaign.audience_json)
        return {
            "id": campaign.id,
            "name": campaign.name,
            "status": campaign.status,
            "campaign_type": campaign.campaign_type,
            "audience": audience,
            "message_template": audience.get("message_template") or "",
            "scheduled_at": campaign.scheduled_at,
            "sent_count": campaign.sent_count,
            "delivered_count": campaign.delivered_count,
            "read_count": campaign.read_count,
            "replied_count": campaign.replied_count,
            "conversion_count": campaign.conversion_count,
            "revenue": campaign.revenue,
            "metrics": self.campaign_metrics(campaign.id),
            "created_by": campaign.created_by,
            "created_at": campaign.created_at,
            "updated_at": campaign.updated_at,
        }

    def campaign_metrics(self, campaign_id: str) -> dict[str, Any]:
        message_filter = AgenteWhatsAppMessage.raw_payload_json.like(f"%{campaign_id}%")
        total_messages = self._db.query(func.count(AgenteWhatsAppMessage.id)).filter(message_filter).scalar() or 0
        status_rows = (
            self._db.query(AgenteWhatsAppOutbox.status, func.count(AgenteWhatsAppOutbox.id))
            .join(AgenteWhatsAppMessage, AgenteWhatsAppMessage.id == AgenteWhatsAppOutbox.message_id)
            .filter(message_filter)
            .group_by(AgenteWhatsAppOutbox.status)
            .all()
        )
        by_status = {status: int(count or 0) for status, count in status_rows}
        return {
            "messages": total_messages,
            "pending": by_status.get("pending", 0),
            "sent": by_status.get("sent", 0),
            "failed": by_status.get("failed", 0),
            "dead": by_status.get("dead", 0),
        }

    def _resolve_campaign_recipients(self, audience: dict[str, Any]) -> list[dict[str, Any]]:
        audience_type = audience.get("audience_type") or "manual"
        recipients: dict[str, dict[str, Any]] = {}

        def add(phone: str, *, customer: Customer | None = None, name: str | None = None):
            normalized = normalize_phone(phone)
            if not normalized:
                return
            recipients[normalized] = {
                "phone": normalized,
                "customer_id": customer.id if customer else None,
                "name": (customer.name if customer else name) or "",
                "first_name": ((customer.name if customer else name) or "").split(" ")[0],
            }

        if audience_type == "manual":
            for phone in audience.get("phones") or []:
                add(phone)
        elif audience_type == "customers":
            customers = (
                self._db.query(Customer)
                .filter(Customer.phone.isnot(None), Customer.phone != "", Customer.marketing_whatsapp_consent.is_(True))
                .limit(1000)
                .all()
            )
            for customer in customers:
                add(customer.phone, customer=customer)
        elif audience_type == "leads":
            rows = (
                self._db.query(CustomerChannel, Customer)
                .join(Customer, Customer.id == CustomerChannel.customer_id)
                .filter(CustomerChannel.channel == "whatsapp")
                .limit(1000)
                .all()
            )
            for channel, customer in rows:
                add(channel.normalized_identifier or channel.identifier, customer=customer)

        return list(recipients.values())

    def _normalize_phone_list(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        phones: list[str] = []
        for value in values:
            for part in str(value).replace("\n", ",").split(","):
                normalized = normalize_phone(part)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    phones.append(normalized)
        return phones

    def _campaign_message_exists(self, campaign_id: str, phone: str) -> bool:
        return (
            self._db.query(func.count(AgenteWhatsAppMessage.id))
            .join(AgenteWhatsAppSession, AgenteWhatsAppSession.id == AgenteWhatsAppMessage.session_id)
            .filter(
                AgenteWhatsAppSession.phone == phone,
                AgenteWhatsAppMessage.raw_payload_json.like(f"%{campaign_id}%"),
            )
            .scalar()
            or 0
        ) > 0

    def _render_campaign_template(self, template: str, recipient: dict[str, Any]) -> str:
        first_name = recipient.get("first_name") or "cliente"
        name = recipient.get("name") or first_name
        return (
            template.replace("{{primeiro_nome}}", first_name)
            .replace("{{nome}}", name)
            .replace("{{telefone}}", recipient.get("phone") or "")
        )

    def list_stories(self, *, status: str | None = None, limit: int = 50) -> list[AgenteWhatsAppStory]:
        q = self._db.query(AgenteWhatsAppStory)
        if status:
            q = q.filter(AgenteWhatsAppStory.status == status)
        return (
            q.order_by(AgenteWhatsAppStory.updated_at.desc().nullslast(), AgenteWhatsAppStory.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_story(self, story_id: str) -> AgenteWhatsAppStory | None:
        return self._db.query(AgenteWhatsAppStory).filter(AgenteWhatsAppStory.id == story_id).first()

    def create_story(self, data: dict[str, Any], *, created_by: str | None = None) -> AgenteWhatsAppStory:
        scheduled_at = data.get("scheduled_at")
        if scheduled_at and not scheduled_at.tzinfo:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        status = "scheduled" if scheduled_at and scheduled_at > now else "draft"
        story = AgenteWhatsAppStory(
            id=str(uuid.uuid4()),
            campaign_id=data.get("campaign_id") or None,
            title=data["title"].strip(),
            media_type=data["media_type"],
            media_url=data["media_url"].strip(),
            caption=(data.get("caption") or "").strip() or None,
            cta_text=(data.get("cta_text") or "").strip() or None,
            cta_url=(data.get("cta_url") or "").strip() or None,
            status=status,
            scheduled_at=scheduled_at,
            metrics_json=_json_dump({"views": 0, "replies": 0, "clicks": 0, "conversions": 0}),
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self._db.add(story)
        self._db.flush()
        return story

    def update_story(self, story: AgenteWhatsAppStory, data: dict[str, Any]) -> AgenteWhatsAppStory:
        allowed = {"title", "media_type", "media_url", "caption", "cta_text", "cta_url", "campaign_id", "scheduled_at", "status"}
        for key, value in data.items():
            if key not in allowed or value is None:
                continue
            if key == "scheduled_at" and value and not value.tzinfo:
                value = value.replace(tzinfo=timezone.utc)
            setattr(story, key, value)
        story.updated_at = datetime.now(timezone.utc)
        return story

    def publish_story(self, story: AgenteWhatsAppStory, *, force: bool = False) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        if story.scheduled_at and story.scheduled_at > now and not force:
            story.status = "scheduled"
            story.updated_at = now
            self._db.flush()
            return {"story_id": story.id, "status": story.status, "published": False}

        metrics = _json_load(story.metrics_json)
        metrics["published_count"] = int(metrics.get("published_count") or 0) + 1
        metrics["last_published_at"] = now.isoformat()
        story.status = "published"
        story.published_at = now
        story.provider_story_id = story.provider_story_id or f"local-{story.id}"
        story.metrics_json = _json_dump(metrics)
        story.updated_at = now
        self._db.flush()
        return {"story_id": story.id, "status": story.status, "published": True}

    def process_scheduled_stories(self, *, limit: int = 10) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        rows = (
            self._db.query(AgenteWhatsAppStory)
            .filter(
                AgenteWhatsAppStory.status == "scheduled",
                AgenteWhatsAppStory.scheduled_at.isnot(None),
                AgenteWhatsAppStory.scheduled_at <= now,
            )
            .order_by(AgenteWhatsAppStory.scheduled_at.asc())
            .limit(limit)
            .all()
        )
        results = [self.publish_story(story, force=True) for story in rows]
        return {
            "processed": len(results),
            "published": sum(1 for item in results if item["published"]),
            "stories": results,
        }

    def serialize_story(self, story: AgenteWhatsAppStory) -> dict[str, Any]:
        return {
            "id": story.id,
            "campaign_id": story.campaign_id,
            "title": story.title,
            "media_type": story.media_type,
            "media_url": story.media_url,
            "caption": story.caption,
            "cta_text": story.cta_text,
            "cta_url": story.cta_url,
            "status": story.status,
            "scheduled_at": story.scheduled_at,
            "published_at": story.published_at,
            "provider_story_id": story.provider_story_id,
            "metrics": _json_load(story.metrics_json),
            "created_by": story.created_by,
            "created_at": story.created_at,
            "updated_at": story.updated_at,
        }

    def list_sessions(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        search: str | None = None,
        assigned_admin_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[AgenteWhatsAppSession]:
        q = self._db.query(AgenteWhatsAppSession)
        if status:
            q = q.filter(AgenteWhatsAppSession.status == status)
        if assigned_admin_id:
            q = q.filter(AgenteWhatsAppSession.assigned_admin_id == assigned_admin_id)
        if date_from or date_to:
            start_date = date_from or local_today()
            end_date = date_to or start_date
            start_dt, end_dt = local_period_bounds(start_date, end_date)
            q = q.filter(
                AgenteWhatsAppSession.updated_at >= start_dt,
                AgenteWhatsAppSession.updated_at <= end_dt,
            )
        if search:
            term = f"%{search.strip()}%"
            q = q.outerjoin(Customer, Customer.id == AgenteWhatsAppSession.customer_id).filter(
                or_(
                    AgenteWhatsAppSession.phone.ilike(term),
                    AgenteWhatsAppSession.current_intent.ilike(term),
                    AgenteWhatsAppSession.provider.ilike(term),
                    Customer.name.ilike(term),
                )
            )
        return (
            q.order_by(AgenteWhatsAppSession.last_message_at.desc().nullslast(), AgenteWhatsAppSession.created_at.desc())
            .limit(limit)
            .all()
        )

    def list_conversations(
        self,
        *,
        status: str | None = None,
        limit: int = 80,
        search: str | None = None,
        assigned_admin_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        sessions = self.list_sessions(
            status=status,
            limit=limit,
            search=search,
            assigned_admin_id=assigned_admin_id,
            date_from=date_from,
            date_to=date_to,
        )
        return [self.serialize_conversation(session) for session in sessions]

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

    def latest_message(self, session_id: str) -> AgenteWhatsAppMessage | None:
        return (
            self._db.query(AgenteWhatsAppMessage)
            .filter(AgenteWhatsAppMessage.session_id == session_id)
            .order_by(AgenteWhatsAppMessage.created_at.desc())
            .first()
        )

    def unread_count(self, session_id: str) -> int:
        return (
            self._db.query(func.count(AgenteWhatsAppMessage.id))
            .filter(
                AgenteWhatsAppMessage.session_id == session_id,
                AgenteWhatsAppMessage.direction == "inbound",
                AgenteWhatsAppMessage.read_at.is_(None),
            )
            .scalar()
            or 0
        )

    def _avg_response_time_seconds(self, start_dt: datetime, end_dt: datetime) -> float:
        rows = (
            self._db.query(AgenteWhatsAppMessage)
            .filter(
                AgenteWhatsAppMessage.created_at >= start_dt,
                AgenteWhatsAppMessage.created_at <= end_dt,
            )
            .order_by(AgenteWhatsAppMessage.session_id.asc(), AgenteWhatsAppMessage.created_at.asc())
            .all()
        )
        pending_inbound: dict[str, datetime] = {}
        response_times: list[float] = []
        for message in rows:
            if message.direction == "inbound":
                pending_inbound[message.session_id] = message.created_at
            elif message.direction == "outbound" and message.session_id in pending_inbound:
                delta = (message.created_at - pending_inbound.pop(message.session_id)).total_seconds()
                if delta >= 0:
                    response_times.append(delta)
        return round(sum(response_times) / len(response_times), 2) if response_times else 0.0

    def _avg_attendance_time_seconds(self, start_dt: datetime, end_dt: datetime) -> float:
        rows = (
            self._db.query(AgenteWhatsAppSession)
            .filter(
                AgenteWhatsAppSession.status == "closed",
                AgenteWhatsAppSession.updated_at >= start_dt,
                AgenteWhatsAppSession.updated_at <= end_dt,
            )
            .all()
        )
        durations = [
            (row.updated_at - row.created_at).total_seconds()
            for row in rows
            if row.created_at and row.updated_at and row.updated_at >= row.created_at
        ]
        return round(sum(durations) / len(durations), 2) if durations else 0.0

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

    def process_baileys_runtime_event(self, payload: dict[str, Any]) -> dict[str, int]:
        if payload.get("event_type") != "message_received":
            return {"received": 0, "duplicates": 0, "status_updates": 0, "ignored": 1}

        item = payload.get("message") or {}
        if item.get("from_me") is True:
            return {"received": 0, "duplicates": 0, "status_updates": 0, "ignored": 1}

        remote = item.get("remote_jid") or item.get("from") or item.get("phone")
        phone = normalize_phone(str(remote).split("@", 1)[0] if remote else "")
        provider_message_id = item.get("id") or item.get("message_id")
        if not phone or not provider_message_id:
            return {"received": 0, "duplicates": 0, "status_updates": 0, "ignored": 1}
        if self._message_exists(str(provider_message_id)):
            return {"received": 0, "duplicates": 1, "status_updates": 0, "ignored": 0}

        session, _created = self.get_or_create_session(
            phone=phone,
            provider="baileys",
            provider_contact_id=str(remote) if remote else None,
            origin="inbound",
            metadata={"source": "baileys_runtime", "instance_id": payload.get("instance_id")},
        )
        push_name = item.get("push_name")
        if session.customer and push_name and session.customer.name.startswith("Cliente WhatsApp"):
            session.customer.name = str(push_name)

        message_type = str(item.get("message_type") or "text")
        body = item.get("body")
        media_url = item.get("media_url")
        self.add_message(
            session,
            direction="inbound",
            sender_type="customer",
            message_type=message_type,
            body=str(body) if body is not None else None,
            media_url=str(media_url) if media_url else None,
            provider_message_id=str(provider_message_id),
            provider_status="received",
            raw_payload=payload,
        )
        return {"received": 1, "duplicates": 0, "status_updates": 0, "ignored": 0}

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

    def serialize_conversation(self, session: AgenteWhatsAppSession) -> dict[str, Any]:
        last_message = self.latest_message(session.id)
        attendance_mode = "human" if session.status == "human" or not session.ai_enabled else "ai"
        return {
            **self.serialize_session(session),
            "last_message": self.serialize_message(last_message) if last_message else None,
            "unread_count": self.unread_count(session.id),
            "attendance_mode": attendance_mode,
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

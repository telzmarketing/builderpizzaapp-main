"""Central WhatsApp marketing eligibility and customer contact risk rules."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.models.customer import Customer
from backend.models.customer_contact_risk import CustomerContactRisk, CustomerContactRiskEvent
from backend.models.customer_identity import CustomerChannel

WINDOW_DAYS = 15
MAX_PROMOTIONAL_SENDS = 2
BLOCKING_STATUSES = {"blocked", "opted_out", "complaint_hold"}
EVENT_DEFAULTS = {
    "contact_reported": (80, True, "Contato denunciado pelo cliente."),
    "order_complaint": (30, False, None),
    "whatsapp_blocked": (100, True, "Cliente bloqueou o contato no WhatsApp."),
    "marketing_opt_out": (100, True, "Cliente revogou o consentimento de marketing."),
    "campaign_sent": (0, False, None), "manual_adjustment": (0, False, None),
    "manual_block": (100, True, "Contato bloqueado manualmente."),
    "contact_unblocked": (0, False, None),
}


def normalize_whatsapp_phone(value: str | None) -> str:
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if not digits.startswith("55") and len(digits) in {10, 11}:
        digits = f"55{digits}"
    return digits


@dataclass(frozen=True)
class ContactEligibility:
    allowed: bool
    reason: str | None
    code: str | None
    customer_id: str | None
    risk: CustomerContactRisk | None


class CustomerContactRiskService:
    def __init__(self, db: Session, tenant_id: str):
        self.db, self.tenant_id = db, tenant_id

    def get_or_create(self, customer_id: str, channel: str = "whatsapp", *, lock: bool = False) -> CustomerContactRisk:
        customer = self.db.query(Customer).filter(Customer.id == customer_id, Customer.tenant_id == self.tenant_id).first()
        if not customer:
            raise DomainError("Cliente nao encontrado neste estabelecimento.", code="CustomerNotFound")
        query = self.db.query(CustomerContactRisk).filter(
            CustomerContactRisk.tenant_id == self.tenant_id,
            CustomerContactRisk.customer_id == customer_id, CustomerContactRisk.channel == channel,
        )
        risk = (query.with_for_update() if lock else query).first()
        if risk:
            return risk
        risk = CustomerContactRisk(id=str(uuid.uuid4()), tenant_id=self.tenant_id, customer_id=customer_id,
            channel=channel, score=0, risk_level="low", is_blocked=False, campaign_deliveries_15d=0, version=1)
        self.db.add(risk)
        self.db.flush()
        return risk

    def _channel(self, customer_id: str, phone: str | None = None) -> CustomerChannel | None:
        query = self.db.query(CustomerChannel).filter(CustomerChannel.tenant_id == self.tenant_id,
            CustomerChannel.customer_id == customer_id, CustomerChannel.channel == "whatsapp")
        normalized = normalize_whatsapp_phone(phone)
        exact = query.filter(CustomerChannel.normalized_identifier == normalized).first() if normalized else None
        return exact or query.order_by(CustomerChannel.is_primary.desc(), CustomerChannel.created_at.asc()).first()

    def resolve_customer_id(self, phone: str) -> str | None:
        normalized = normalize_whatsapp_phone(phone)
        channel = self.db.query(CustomerChannel).filter(CustomerChannel.tenant_id == self.tenant_id,
            CustomerChannel.channel == "whatsapp", CustomerChannel.normalized_identifier == normalized).first()
        if channel:
            return channel.customer_id
        candidates = self.db.query(Customer).filter(Customer.tenant_id == self.tenant_id).all()
        return next((item.id for item in candidates if normalize_whatsapp_phone(item.phone) == normalized), None)

    def _campaign_count(self, customer_id: str, now: datetime | None = None) -> int:
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=WINDOW_DAYS)
        delivered = self.db.execute(text("""
            SELECT COUNT(DISTINCT COALESCE(campaign_id, whatsapp_message_id, id))
            FROM whatsapp_campaign_deliveries
            WHERE tenant_id = :tenant_id
              AND customer_id = :customer_id
              AND status IN ('sent', 'delivered', 'read')
              AND COALESCE(sent_at, created_at) >= :cutoff
        """), {"tenant_id": self.tenant_id, "customer_id": customer_id, "cutoff": cutoff}).scalar() or 0
        other_campaigns = self.db.query(CustomerContactRiskEvent).filter(CustomerContactRiskEvent.tenant_id == self.tenant_id,
            CustomerContactRiskEvent.customer_id == customer_id, CustomerContactRiskEvent.channel == "whatsapp",
            CustomerContactRiskEvent.event_type == "campaign_sent",
            CustomerContactRiskEvent.source_type != "whatsapp_campaign_delivery",
            CustomerContactRiskEvent.occurred_at >= cutoff).count()
        return int(delivered) + int(other_campaigns)

    def evaluate_whatsapp_marketing(self, *, customer_id: str | None, phone: str) -> ContactEligibility:
        resolved_id = customer_id or self.resolve_customer_id(phone)
        if not resolved_id:
            return ContactEligibility(False, "Destinatario sem cliente identificado e consentimento auditavel.", "WhatsAppCustomerRequired", None, None)
        risk = self.get_or_create(resolved_id, lock=True)
        customer = self.db.query(Customer).filter(Customer.id == resolved_id, Customer.tenant_id == self.tenant_id).first()
        channel, count = self._channel(resolved_id, phone), self._campaign_count(resolved_id)
        risk.campaign_deliveries_15d = count
        if risk.is_blocked:
            return ContactEligibility(False, risk.block_reason or "Contato bloqueado para marketing.", "WhatsAppContactRiskBlocked", resolved_id, risk)
        if channel and (channel.marketing_status or "active") in BLOCKING_STATUSES:
            return ContactEligibility(False, channel.marketing_block_reason or "Canal bloqueado para marketing.", "WhatsAppChannelBlocked", resolved_id, risk)
        if not bool(customer and customer.marketing_whatsapp_consent) or not bool(channel and channel.marketing_consent):
            return ContactEligibility(False, "Cliente sem consentimento ativo para marketing no WhatsApp.", "WhatsAppMarketingConsentRequired", resolved_id, risk)
        if count >= MAX_PROMOTIONAL_SENDS:
            return ContactEligibility(False, "Limite de 2 campanhas em 15 dias atingido para este cliente.", "WhatsAppCampaignFrequencyLimit", resolved_id, risk)
        return ContactEligibility(True, None, None, resolved_id, risk)

    def record_event(self, customer_id: str, event_type: str, *, points_delta: int | None = None,
        source_type: str, source_id: str | None = None, dedupe_key: str | None = None,
        occurred_at: datetime | None = None, reason: str | None = None,
        metadata: dict[str, Any] | None = None) -> CustomerContactRisk:
        if event_type not in EVENT_DEFAULTS:
            raise DomainError("Tipo de evento de risco invalido.", code="ContactRiskEventInvalid")
        if dedupe_key:
            existing = self.db.query(CustomerContactRiskEvent).filter(
                CustomerContactRiskEvent.tenant_id == self.tenant_id,
                CustomerContactRiskEvent.dedupe_key == dedupe_key).first()
            if existing:
                return self.get_or_create(customer_id)
        risk, channel = self.get_or_create(customer_id, lock=True), self._channel(customer_id)
        default_points, blocks_contact, default_reason = EVENT_DEFAULTS[event_type]
        delta = default_points if points_delta is None else points_delta
        before, now = int(risk.score or 0), occurred_at or datetime.now(timezone.utc)
        after = max(0, min(100, before + delta))
        if event_type == "contact_unblocked":
            risk.is_blocked, risk.block_reason, risk.blocked_at = False, None, None
            if channel:
                channel.marketing_status, channel.marketing_block_reason, channel.marketing_blocked_at = "active", None, None
                channel.marketing_status_updated_at = now
        elif blocks_contact:
            risk.is_blocked, risk.block_reason, risk.blocked_at = True, reason or default_reason, now
            if channel:
                channel.marketing_status = "opted_out" if event_type == "marketing_opt_out" else "blocked"
                channel.marketing_block_reason, channel.marketing_blocked_at = risk.block_reason, now
                channel.marketing_status_updated_at = now
                if event_type == "marketing_opt_out":
                    channel.marketing_consent = False
        risk.score, risk.last_event_at = after, now
        risk.risk_level = "blocked" if risk.is_blocked else ("high" if after >= 60 else "attention" if after >= 30 else "low")
        risk.version, risk.updated_at = int(risk.version or 0) + 1, now
        event = CustomerContactRiskEvent(id=str(uuid.uuid4()), tenant_id=self.tenant_id,
            customer_id=customer_id, customer_channel_id=channel.id if channel else None, risk_id=risk.id,
            channel="whatsapp", event_type=event_type, points_delta=delta, score_before=before,
            score_after=after, blocks_contact=blocks_contact, source_type=source_type, source_id=source_id,
            dedupe_key=dedupe_key, occurred_at=now,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False, default=str))
        self.db.add(event)
        self.db.flush()
        if event_type == "campaign_sent":
            risk.campaign_deliveries_15d = self._campaign_count(customer_id, now)
        return risk

    def record_campaign_sent(self, customer_id: str, *, source_type: str, source_id: str) -> CustomerContactRisk:
        count_before = self._campaign_count(customer_id)
        return self.record_event(customer_id, "campaign_sent", points_delta=0,
            source_type=source_type, source_id=source_id, dedupe_key=f"campaign_sent:{source_type}:{source_id}",
            metadata={"window_days": WINDOW_DAYS, "send_number_in_window": count_before + 1})

    def serialize(self, customer_id: str) -> dict[str, Any]:
        risk = self.get_or_create(customer_id)
        eligibility = self.evaluate_whatsapp_marketing(customer_id=customer_id, phone="")
        events = self.db.query(CustomerContactRiskEvent).filter(CustomerContactRiskEvent.tenant_id == self.tenant_id,
            CustomerContactRiskEvent.customer_id == customer_id, CustomerContactRiskEvent.channel == "whatsapp"
        ).order_by(CustomerContactRiskEvent.occurred_at.desc()).limit(100).all()
        return {"customer_id": customer_id, "channel": risk.channel, "score": risk.score,
            "risk_level": risk.risk_level, "is_blocked": risk.is_blocked, "block_reason": risk.block_reason,
            "blocked_at": risk.blocked_at, "campaign_deliveries_15d": risk.campaign_deliveries_15d,
            "last_event_at": risk.last_event_at, "eligible_for_marketing": eligibility.allowed,
            "eligibility_reason": eligibility.reason, "events": [{"id": event.id,
                "event_type": event.event_type, "points_delta": event.points_delta,
                "score_before": event.score_before, "score_after": event.score_after,
                "blocks_contact": event.blocks_contact, "source_type": event.source_type,
                "source_id": event.source_id, "occurred_at": event.occurred_at,
                "metadata": json.loads(event.metadata_json or "{}")} for event in events]}

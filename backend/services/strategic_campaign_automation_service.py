from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.models.strategic_campaign import StrategicCampaign, StrategicCampaignAutomation
from backend.schemas.strategic_campaign_automation import StrategicCampaignAutomationUpdate


class StrategicCampaignAutomationService:
    """Owns campaign-scoped definitions only; the transversal engine owns execution."""

    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def _campaign(self, campaign_id: str) -> StrategicCampaign:
        campaign = self.db.query(StrategicCampaign).filter(
            StrategicCampaign.tenant_id == self.tenant_id,
            StrategicCampaign.id == campaign_id,
        ).one_or_none()
        if campaign is None:
            raise DomainError("Campanha estratégica não encontrada.", code="StrategicCampaignNotFound")
        return campaign

    def list(self, campaign_id: str) -> list[StrategicCampaignAutomation]:
        self._campaign(campaign_id)
        return self.db.query(StrategicCampaignAutomation).filter(
            StrategicCampaignAutomation.tenant_id == self.tenant_id,
            StrategicCampaignAutomation.campaign_id == campaign_id,
        ).order_by(StrategicCampaignAutomation.automation_key).all()

    @staticmethod
    def _catalog(commercial_config: dict[str, Any]) -> list[dict[str, Any]]:
        catalog = [
            {
                "automation_key": "order_confirmation",
                "event_key": "strategic_campaign.order.created",
                "name": "Confirmação do pedido da campanha",
            },
            {
                "automation_key": "payment_confirmation",
                "event_key": "strategic_campaign.payment.confirmed",
                "name": "Confirmação do pagamento da campanha",
            },
        ]
        if commercial_config.get("require_scheduled_order"):
            catalog.extend([
                {
                    "automation_key": "schedule_confirmation",
                    "event_key": "strategic_campaign.schedule.confirmed",
                    "name": "Confirmação do agendamento da campanha",
                },
                {
                    "automation_key": "schedule_reminder",
                    "event_key": "strategic_campaign.schedule.reminder_due",
                    "name": "Lembrete do agendamento da campanha",
                },
            ])
        if commercial_config.get("sales_mode") in {"preorder", "hybrid"}:
            catalog.append({
                "automation_key": "reservation_created",
                "event_key": "strategic_campaign.reservation.created",
                "name": "Confirmação da reserva da campanha",
            })
        return catalog

    @staticmethod
    def _fingerprint(commercial_config: dict[str, Any]) -> str:
        payload = json.dumps(commercial_config, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode()).hexdigest()

    def generate(self, campaign_id: str) -> list[StrategicCampaignAutomation]:
        campaign = self._campaign(campaign_id)
        commercial_config = dict(campaign.commercial_config or {})
        fingerprint = self._fingerprint(commercial_config)
        existing = {
            row.automation_key: row
            for row in self.db.query(StrategicCampaignAutomation).filter(
                StrategicCampaignAutomation.tenant_id == self.tenant_id,
                StrategicCampaignAutomation.campaign_id == campaign_id,
            ).all()
        }
        desired = {item["automation_key"] for item in self._catalog(commercial_config)}
        for item in self._catalog(commercial_config):
            row = existing.get(item["automation_key"])
            if row is None:
                row = StrategicCampaignAutomation(
                    id=f"sca-{uuid.uuid4().hex[:12]}",
                    tenant_id=self.tenant_id,
                    campaign_id=campaign_id,
                    automation_key=item["automation_key"],
                    event_key=item["event_key"],
                    channel="whatsapp",
                    name=item["name"],
                    definition={"trigger": {"key": item["event_key"], "config": {}}, "conditions": [], "actions": []},
                    generated_from={"commercial_config_sha256": fingerprint},
                )
                self.db.add(row)
            else:
                row.event_key = item["event_key"]
                row.name = item["name"]
                row.generated_from = {"commercial_config_sha256": fingerprint}
        for key, row in existing.items():
            if key not in desired:
                row.enabled = False
        self.db.flush()
        return self.list(campaign_id)

    def update(self, campaign_id: str, automation_id: str, payload: StrategicCampaignAutomationUpdate) -> StrategicCampaignAutomation:
        self._campaign(campaign_id)
        row = self.db.query(StrategicCampaignAutomation).filter(
            StrategicCampaignAutomation.tenant_id == self.tenant_id,
            StrategicCampaignAutomation.campaign_id == campaign_id,
            StrategicCampaignAutomation.id == automation_id,
        ).one_or_none()
        if row is None:
            raise DomainError("Automação da campanha não encontrada.", code="StrategicCampaignAutomationNotFound")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        self.db.flush()
        return row

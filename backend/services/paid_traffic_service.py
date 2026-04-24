from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.order import Order
from backend.models.paid_traffic import (
    AdDailyMetric,
    AdPlatformIntegration,
    AdSyncLog,
    CampaignLink,
    CampaignSettings,
    TrackingEvent,
    TrackingSession,
    TrafficCampaign,
)
from backend.schemas.paid_traffic import (
    AdIntegrationIn,
    CampaignLinkCreate,
    CampaignSettingsIn,
    TrafficCampaignCreate,
    TrafficCampaignUpdate,
    TrackingEventIn,
)


def _slug(value: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
    return "_".join(part for part in normalized.split("_") if part)[:120] or "campanha"


def _fernet() -> Fernet:
    settings = get_settings()
    digest = hashlib.sha256(settings.JWT_SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt(value: str | None) -> str | None:
    if not value:
        return None
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


class PaidTrafficService:
    def __init__(self, db: Session):
        self._db = db

    # Campaigns
    def list_campaigns(self) -> list[TrafficCampaign]:
        return self._db.query(TrafficCampaign).order_by(TrafficCampaign.created_at.desc()).all()

    def get_campaign(self, campaign_id: str) -> TrafficCampaign:
        campaign = self._db.query(TrafficCampaign).filter(TrafficCampaign.id == campaign_id).first()
        if not campaign:
            raise HTTPException(404, "Campanha de trafego nao encontrada.")
        return campaign

    def create_campaign(self, body: TrafficCampaignCreate) -> TrafficCampaign:
        campaign = TrafficCampaign(id=f"tc-{uuid.uuid4().hex[:10]}", **body.model_dump())
        self._db.add(campaign)
        self._db.commit()
        self._db.refresh(campaign)
        return campaign

    def update_campaign(self, campaign_id: str, body: TrafficCampaignUpdate) -> TrafficCampaign:
        campaign = self.get_campaign(campaign_id)
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(campaign, key, value)
        self._db.commit()
        self._db.refresh(campaign)
        return campaign

    def delete_campaign(self, campaign_id: str) -> None:
        campaign = self.get_campaign(campaign_id)
        self._db.delete(campaign)
        self._db.commit()

    # Links
    def list_links(self, campaign_id: str | None = None) -> list[CampaignLink]:
        q = self._db.query(CampaignLink)
        if campaign_id:
            q = q.filter(CampaignLink.campaign_id == campaign_id)
        return q.order_by(CampaignLink.created_at.desc()).all()

    def create_link(self, body: CampaignLinkCreate) -> CampaignLink:
        campaign = self.get_campaign(body.campaign_id)
        destination_url = body.destination_url or campaign.destination_url or "/"
        utm_source = body.utm_source or campaign.platform
        utm_medium = body.utm_medium or "cpc"
        utm_campaign = body.utm_campaign or _slug(campaign.name)
        utm_content = body.utm_content or _slug(body.name or campaign.name)
        utm_term = body.utm_term or ""
        final_url = self._build_url(destination_url, {
            "utm_source": utm_source,
            "utm_medium": utm_medium,
            "utm_campaign": utm_campaign,
            "utm_content": utm_content,
            "utm_term": utm_term,
            "campaign_id": campaign.id,
        })
        link = CampaignLink(
            id=f"cl-{uuid.uuid4().hex[:10]}",
            campaign_id=campaign.id,
            name=body.name,
            destination_url=destination_url,
            final_url=final_url,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            utm_content=utm_content,
            utm_term=utm_term,
        )
        self._db.add(link)
        self._db.commit()
        self._db.refresh(link)
        return link

    def _build_url(self, url: str, params: dict[str, str]) -> str:
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query.update({k: v for k, v in params.items() if v})
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    # Tracking
    def record_event(self, body: TrackingEventIn) -> TrackingEvent:
        settings = self.get_settings()
        if not settings.tracking_enabled:
            raise HTTPException(202, "Tracking desativado.")

        campaign_id = body.campaign_id or self._find_campaign_id(body.utm_campaign)
        session = self._db.query(TrackingSession).filter(TrackingSession.id == body.session_id).first()
        now = datetime.now(timezone.utc)
        if not session:
            session = TrackingSession(
                id=body.session_id,
                campaign_id=campaign_id,
                utm_source=body.utm_source,
                utm_medium=body.utm_medium,
                utm_campaign=body.utm_campaign,
                utm_content=body.utm_content,
                utm_term=body.utm_term,
                landing_page=body.landing_page or body.path,
                referrer=body.referrer,
                first_seen_at=now,
                last_seen_at=now,
            )
            self._db.add(session)
        else:
            session.last_seen_at = now
            if campaign_id and not session.campaign_id:
                session.campaign_id = campaign_id

        event = TrackingEvent(
            id=f"te-{uuid.uuid4().hex[:12]}",
            session_id=body.session_id,
            campaign_id=campaign_id or session.campaign_id,
            event_type=body.event_type,
            value=body.value,
            path=body.path,
            utm_source=body.utm_source or session.utm_source,
            utm_medium=body.utm_medium or session.utm_medium,
            utm_campaign=body.utm_campaign or session.utm_campaign,
            utm_content=body.utm_content or session.utm_content,
            utm_term=body.utm_term or session.utm_term,
            raw_payload=json.dumps(body.model_dump(mode="json"), ensure_ascii=False),
        )
        self._db.add(event)
        self._db.commit()
        self._db.refresh(event)
        return event

    def _find_campaign_id(self, utm_campaign: str | None) -> str | None:
        if not utm_campaign:
            return None
        link = self._db.query(CampaignLink).filter(CampaignLink.utm_campaign == utm_campaign).first()
        return link.campaign_id if link else None

    # Integrations
    def list_integrations(self) -> list[AdPlatformIntegration]:
        return self._db.query(AdPlatformIntegration).order_by(AdPlatformIntegration.platform).all()

    def upsert_integration(self, body: AdIntegrationIn) -> AdPlatformIntegration:
        integration = self._db.query(AdPlatformIntegration).filter(AdPlatformIntegration.platform == body.platform).first()
        if not integration:
            integration = AdPlatformIntegration(id=f"ai-{uuid.uuid4().hex[:10]}", platform=body.platform)
            self._db.add(integration)
        if body.access_token is not None:
            integration.access_token_encrypted = _encrypt(body.access_token)
        if body.refresh_token is not None:
            integration.refresh_token_encrypted = _encrypt(body.refresh_token)
        if body.account_name is not None:
            integration.account_name = body.account_name
        integration.status = "connected" if integration.access_token_encrypted else "disconnected"
        integration.last_error = None
        self._db.commit()
        self._db.refresh(integration)
        return integration

    def disconnect_integration(self, platform: str) -> AdPlatformIntegration:
        integration = self._db.query(AdPlatformIntegration).filter(AdPlatformIntegration.platform == platform).first()
        if not integration:
            integration = AdPlatformIntegration(id=f"ai-{uuid.uuid4().hex[:10]}", platform=platform)
            self._db.add(integration)
        integration.status = "disconnected"
        integration.access_token_encrypted = None
        integration.refresh_token_encrypted = None
        self._db.commit()
        self._db.refresh(integration)
        return integration

    def sync_platform(self, platform: str) -> dict:
        integration = self._db.query(AdPlatformIntegration).filter(AdPlatformIntegration.platform == platform).first()
        log = AdSyncLog(id=f"sl-{uuid.uuid4().hex[:10]}", platform=platform, status="skipped")
        if not integration or integration.status != "connected":
            log.message = "Integracao nao conectada. Nenhuma metrica falsa foi criada."
        else:
            log.message = "Conector preparado. Configure credenciais OAuth/API para buscar metricas reais."
            integration.last_sync_at = datetime.now(timezone.utc)
        log.finished_at = datetime.now(timezone.utc)
        self._db.add(log)
        self._db.commit()
        return {"status": log.status, "message": log.message}

    # Settings
    def get_settings(self) -> CampaignSettings:
        settings = self._db.query(CampaignSettings).filter(CampaignSettings.id == "default").first()
        if not settings:
            settings = CampaignSettings(id="default")
            self._db.add(settings)
            self._db.commit()
            self._db.refresh(settings)
        return settings

    def update_settings(self, body: CampaignSettingsIn) -> CampaignSettings:
        settings = self.get_settings()
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(settings, key, value)
        self._db.commit()
        self._db.refresh(settings)
        return settings

    # Analytics
    def dashboard(self, date_from: date | None = None, date_to: date | None = None) -> dict:
        orders_q = self._db.query(Order)
        events_q = self._db.query(TrackingEvent)
        metrics_q = self._db.query(AdDailyMetric)
        if date_from:
            orders_q = orders_q.filter(func.date(Order.created_at) >= date_from)
            events_q = events_q.filter(func.date(TrackingEvent.created_at) >= date_from)
            metrics_q = metrics_q.filter(AdDailyMetric.metric_date >= date_from)
        if date_to:
            orders_q = orders_q.filter(func.date(Order.created_at) <= date_to)
            events_q = events_q.filter(func.date(TrackingEvent.created_at) <= date_to)
            metrics_q = metrics_q.filter(AdDailyMetric.metric_date <= date_to)

        paid_statuses = ("pago", "paid", "delivered", "preparing", "ready_for_pickup", "on_the_way")
        paid_orders = orders_q.filter(Order.status.in_(paid_statuses)).all()
        revenue = round(sum(o.total or 0 for o in paid_orders), 2)
        spend = round(sum(m.spend or 0 for m in metrics_q.all()), 2)
        visitors = events_q.filter(TrackingEvent.event_type == "page_view").count()
        carts = events_q.filter(TrackingEvent.event_type == "add_to_cart").count()
        paid_count = len(paid_orders)
        settings = self.get_settings()
        estimated_profit = round(revenue * settings.default_margin - spend, 2)

        by_campaign = []
        for campaign in self.list_campaigns():
            campaign_orders = [o for o in paid_orders if getattr(o, "campaign_id", None) == campaign.id]
            campaign_revenue = round(sum(o.total or 0 for o in campaign_orders), 2)
            campaign_spend = round(sum(m.spend or 0 for m in metrics_q.filter(AdDailyMetric.traffic_campaign_id == campaign.id).all()), 2)
            by_campaign.append({
                "campaign_id": campaign.id,
                "name": campaign.name,
                "platform": campaign.platform,
                "spend": campaign_spend,
                "revenue": campaign_revenue,
                "orders": len(campaign_orders),
                "roas": round(campaign_revenue / campaign_spend, 2) if campaign_spend > 0 else 0,
            })

        by_platform: dict[str, dict] = {}
        for row in by_campaign:
            item = by_platform.setdefault(row["platform"], {"platform": row["platform"], "spend": 0.0, "revenue": 0.0, "orders": 0})
            item["spend"] += row["spend"]
            item["revenue"] += row["revenue"]
            item["orders"] += row["orders"]

        return {
            "spend": spend,
            "revenue": revenue,
            "estimated_profit": estimated_profit,
            "roas": round(revenue / spend, 2) if spend > 0 else 0,
            "roi": round((revenue - spend) / spend, 2) if spend > 0 else 0,
            "cpa": round(spend / paid_count, 2) if paid_count > 0 else 0,
            "average_ticket": round(revenue / paid_count, 2) if paid_count > 0 else 0,
            "conversion_rate": round(paid_count / visitors, 4) if visitors > 0 else 0,
            "orders": orders_q.count(),
            "paid_orders": paid_count,
            "visitors": visitors,
            "carts": carts,
            "abandoned_carts": max(carts - paid_count, 0),
            "by_campaign": by_campaign,
            "by_platform": list(by_platform.values()),
            "by_day": [],
        }

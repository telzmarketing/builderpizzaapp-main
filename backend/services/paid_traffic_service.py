from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from cryptography.fernet import Fernet
from fastapi import HTTPException
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.order import Order
from backend.models.paid_traffic import (
    AdDailyMetric,
    AdPlatformIntegration,
    AdSyncLog,
    CampaignCreative,
    CampaignLink,
    CampaignSettings,
    TrackingEvent,
    TrackingSession,
    TrafficCampaign,
)
from backend.schemas.paid_traffic import (
    AdIntegrationIn,
    CampaignCreativeCreate,
    CampaignLinkCreate,
    CampaignSettingsIn,
    TrafficCampaignCreate,
    TrafficCampaignUpdate,
    TrackingEventIn,
    TrackingSessionIn,
)

INTERNAL_TRACKING_PREFIXES = ("/painel", "/motoboy")


def _public_tracking_sql(column: str) -> str:
    value = f"COALESCE({column}, '')"
    filters = []
    for prefix in INTERNAL_TRACKING_PREFIXES:
        filters.extend([
            f"{value} NOT LIKE '{prefix}%'",
            f"{value} NOT LIKE '%://%{prefix}%'",
        ])
    return f"({value} = '' OR ({' AND '.join(filters)}))"


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


def _public_store_url() -> str:
    settings = get_settings()
    configured = (settings.PUBLIC_STORE_URL or settings.VITE_PUBLIC_STORE_URL or "").strip().rstrip("/")
    if configured:
        return configured

    for origin in settings.ALLOWED_ORIGINS:
        normalized = str(origin).strip().rstrip("/")
        if normalized.startswith("http") and "localhost" not in normalized and "127.0.0.1" not in normalized:
            return normalized

    return "https://delivery.moschettieri.com.br"


def _normalize_destination_url(url: str | None) -> str:
    raw = (url or "").strip()
    base_url = _public_store_url()
    if not raw:
        return base_url
    if raw.startswith(("http://", "https://")):
        return raw
    if raw.startswith("/"):
        return f"{base_url}{raw}"
    return f"{base_url}/{raw}"


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

    # Criativos
    def list_creatives(self, campaign_id: str) -> list[CampaignCreative]:
        self.get_campaign(campaign_id)
        return (
            self._db.query(CampaignCreative)
            .filter(CampaignCreative.campaign_id == campaign_id)
            .order_by(CampaignCreative.created_at.desc())
            .all()
        )

    def add_creative(self, campaign_id: str, body: CampaignCreativeCreate) -> CampaignCreative:
        self.get_campaign(campaign_id)
        creative = CampaignCreative(
            id=f"cc-{uuid.uuid4().hex[:10]}",
            campaign_id=campaign_id,
            media_url=body.media_url,
            creative_type=body.creative_type,
            name=body.name,
        )
        self._db.add(creative)
        self._db.commit()
        self._db.refresh(creative)
        return creative

    def delete_creative(self, campaign_id: str, creative_id: str) -> None:
        creative = (
            self._db.query(CampaignCreative)
            .filter(CampaignCreative.id == creative_id, CampaignCreative.campaign_id == campaign_id)
            .first()
        )
        if not creative:
            raise HTTPException(404, "Criativo não encontrado.")
        self._db.delete(creative)
        self._db.commit()

    # Links
    def list_links(self, campaign_id: str | None = None) -> list[CampaignLink]:
        q = self._db.query(CampaignLink)
        if campaign_id:
            q = q.filter(CampaignLink.campaign_id == campaign_id)
        return q.order_by(CampaignLink.created_at.desc()).all()

    def create_link(self, body: CampaignLinkCreate) -> CampaignLink:
        campaign = self.get_campaign(body.campaign_id)
        destination_url = _normalize_destination_url(body.destination_url or campaign.destination_url)
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
    def record_session(self, body: TrackingSessionIn) -> TrackingSession:
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
                landing_page=body.landing_page,
                referrer=body.referrer,
                first_seen_at=now,
                last_seen_at=now,
            )
            self._db.add(session)
        else:
            session.last_seen_at = now
            if campaign_id and not session.campaign_id:
                session.campaign_id = campaign_id

        self._db.commit()
        self._db.refresh(session)
        return session

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
    def realtime(self, window_minutes: int = 15, limit: int = 60) -> dict:
        from backend.models.product import Product
        from backend.routes.marketing import MarketingSettings, VisitorEvent, VisitorProfile, VisitorSession

        now = datetime.now(timezone.utc)
        since = now - timedelta(minutes=window_minutes)
        settings = self._db.query(MarketingSettings).filter(MarketingSettings.id == "default").first()
        online_minutes = settings.online_visitor_minutes if settings and settings.online_visitor_minutes else 5
        online_since = now - timedelta(minutes=online_minutes)

        recent_events = (
            self._db.query(VisitorEvent, VisitorProfile, Product.name)
            .join(VisitorProfile, VisitorProfile.id == VisitorEvent.visitor_id)
            .outerjoin(Product, Product.id == VisitorEvent.product_id)
            .filter(VisitorEvent.created_at >= since)
            .filter(text(_public_tracking_sql("visitor_events.page")))
            .order_by(VisitorEvent.created_at.desc())
            .limit(limit)
            .all()
        )

        latest_by_visitor: dict[str, VisitorEvent] = {}
        for event, _visitor, _product_name in recent_events:
            latest_by_visitor.setdefault(event.visitor_id, event)

        visitors = (
            self._db.query(VisitorProfile)
            .join(VisitorEvent, VisitorEvent.visitor_id == VisitorProfile.id)
            .filter(VisitorEvent.created_at >= since)
            .filter(text(_public_tracking_sql("visitor_events.page")))
            .order_by(func.max(VisitorEvent.created_at).desc())
            .group_by(VisitorProfile.id)
            .limit(limit)
            .all()
        )

        event_counts = (
            self._db.query(VisitorEvent.event_type, func.count(VisitorEvent.id))
            .filter(VisitorEvent.created_at >= since)
            .filter(text(_public_tracking_sql("visitor_events.page")))
            .group_by(VisitorEvent.event_type)
            .order_by(func.count(VisitorEvent.id).desc())
            .limit(12)
            .all()
        )
        visitor_count = func.count(func.distinct(VisitorProfile.id))
        device_counts = (
            self._db.query(func.coalesce(VisitorProfile.device_type, "unknown"), visitor_count)
            .join(VisitorEvent, VisitorEvent.visitor_id == VisitorProfile.id)
            .filter(VisitorEvent.created_at >= since)
            .filter(text(_public_tracking_sql("visitor_events.page")))
            .group_by(func.coalesce(VisitorProfile.device_type, "unknown"))
            .order_by(visitor_count.desc())
            .all()
        )
        city_counts = (
            self._db.query(func.coalesce(VisitorProfile.city, "Sem cidade"), visitor_count)
            .join(VisitorEvent, VisitorEvent.visitor_id == VisitorProfile.id)
            .filter(VisitorEvent.created_at >= since)
            .filter(text(_public_tracking_sql("visitor_events.page")))
            .group_by(func.coalesce(VisitorProfile.city, "Sem cidade"))
            .order_by(visitor_count.desc())
            .limit(8)
            .all()
        )

        total_events = (
            self._db.query(func.count(VisitorEvent.id))
            .filter(VisitorEvent.created_at >= since)
            .filter(text(_public_tracking_sql("visitor_events.page")))
            .scalar()
            or 0
        )
        active_sessions = (
            self._db.query(func.count(VisitorSession.id))
            .filter(VisitorSession.started_at >= since)
            .filter(text(_public_tracking_sql("visitor_sessions.landing_page")))
            .scalar()
            or 0
        )
        online_visitors = (
            self._db.query(func.count(func.distinct(VisitorEvent.visitor_id)))
            .filter(VisitorEvent.created_at >= online_since)
            .filter(text(_public_tracking_sql("visitor_events.page")))
            .scalar()
            or 0
        )

        def metadata(raw: str | None) -> dict | None:
            if not raw:
                return None
            try:
                parsed = json.loads(raw)
                return parsed if isinstance(parsed, dict) else None
            except Exception:
                return None

        def is_online(value: datetime | None) -> bool:
            if not value:
                return False
            comparable = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return comparable >= online_since

        return {
            "generated_at": now,
            "window_minutes": window_minutes,
            "online_visitors": online_visitors,
            "active_sessions": active_sessions,
            "total_events": total_events,
            "last_event_at": recent_events[0][0].created_at if recent_events else None,
            "visitors": [
                {
                    "id": visitor.id,
                    "city": visitor.city,
                    "state": visitor.state,
                    "country": visitor.country,
                    "device": visitor.device_type,
                    "browser": visitor.browser,
                    "operating_system": visitor.os,
                    "sessions": visitor.total_sessions or 0,
                    "pageviews": visitor.total_pageviews or 0,
                    "orders": visitor.total_orders or 0,
                    "current_page": latest_by_visitor.get(visitor.id).page if visitor.id in latest_by_visitor else None,
                    "current_event": latest_by_visitor.get(visitor.id).event_type if visitor.id in latest_by_visitor else None,
                    "current_event_at": latest_by_visitor.get(visitor.id).created_at if visitor.id in latest_by_visitor else None,
                    "last_seen": visitor.last_seen_at,
                    "is_online": is_online(visitor.last_seen_at),
                    "latitude": visitor.latitude,
                    "longitude": visitor.longitude,
                    "location_accuracy_m": visitor.location_accuracy_m,
                }
                for visitor in visitors
            ],
            "events": [
                {
                    "id": event.id,
                    "visitor_id": visitor.id,
                    "session_id": event.session_id,
                    "event_type": event.event_type,
                    "page": event.page,
                    "product_id": event.product_id,
                    "product_name": product_name,
                    "metadata": metadata(event.metadata_json),
                    "city": visitor.city,
                    "device": visitor.device_type,
                    "browser": visitor.browser,
                    "created_at": event.created_at,
                }
                for event, visitor, product_name in recent_events
            ],
            "event_counts": [{"name": event_type, "count": count or 0} for event_type, count in event_counts],
            "devices": [{"name": device, "count": count or 0} for device, count in device_counts],
            "cities": [{"name": city, "count": count or 0} for city, count in city_counts],
        }

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

        campaign_utm_map: dict[str, set[str]] = {}
        for link in self._db.query(CampaignLink).all():
            if link.utm_campaign:
                campaign_utm_map.setdefault(link.campaign_id, set()).add(link.utm_campaign)

        by_campaign = []
        for campaign in self.list_campaigns():
            campaign_utms = campaign_utm_map.get(campaign.id, set())
            campaign_orders = [
                o for o in paid_orders
                if getattr(o, "campaign_id", None) == campaign.id
                or (getattr(o, "utm_campaign", None) and getattr(o, "utm_campaign", None) in campaign_utms)
            ]
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

        by_day_map: dict[str, dict] = {}
        for metric in metrics_q.all():
            key = metric.metric_date.isoformat()
            item = by_day_map.setdefault(key, {"date": key, "spend": 0.0, "revenue": 0.0, "orders": 0, "visitors": 0, "carts": 0})
            item["spend"] = round(item["spend"] + (metric.spend or 0), 2)
        for order in paid_orders:
            key = order.created_at.date().isoformat()
            item = by_day_map.setdefault(key, {"date": key, "spend": 0.0, "revenue": 0.0, "orders": 0, "visitors": 0, "carts": 0})
            item["revenue"] = round(item["revenue"] + (order.total or 0), 2)
            item["orders"] += 1
        for event in events_q.filter(TrackingEvent.event_type.in_(("page_view", "add_to_cart"))).all():
            key = event.created_at.date().isoformat()
            item = by_day_map.setdefault(key, {"date": key, "spend": 0.0, "revenue": 0.0, "orders": 0, "visitors": 0, "carts": 0})
            if event.event_type == "page_view":
                item["visitors"] += 1
            elif event.event_type == "add_to_cart":
                item["carts"] += 1

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
            "by_day": [by_day_map[key] for key in sorted(by_day_map)],
        }

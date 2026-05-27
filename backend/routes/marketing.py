"""Marketing — Campaigns, Visitor tracking, Tracking links, Settings."""
from __future__ import annotations
import hashlib
import json
import uuid
import requests
from datetime import date, datetime, timezone, timedelta
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy import Column, String, Boolean, Integer, Float, Text, DateTime, Date, ForeignKey, func, text
from sqlalchemy.orm import Session

from backend.core.local_time import local_period_bounds, local_today
from backend.database import get_db, Base
from backend.models.customer_event import CustomerEvent
from backend.models.paid_traffic import TrafficCampaign
from backend.routes.admin_auth import get_current_admin
from backend.routes.email_marketing import EmailCampaign
from backend.routes.whatsapp_marketing import WhatsAppCampaign
from backend.core.response import ok, created, err_msg

router = APIRouter(prefix="/marketing", tags=["marketing"])
public_router = APIRouter(prefix="/marketing", tags=["marketing-public"])


# ── ORM Models ────────────────────────────────────────────────────────────────

class MarketingCampaign(Base):
    __tablename__ = "marketing_campaigns"
    id = Column(String, primary_key=True)
    name = Column(String(300), nullable=False)
    campaign_type = Column(String(50), nullable=False)
    channel = Column(String(50))
    status = Column(String(30), default="draft")
    product_id = Column(String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    coupon_id = Column(String, ForeignKey("coupons.id", ondelete="SET NULL"), nullable=True)
    group_id = Column(String, ForeignKey("customer_groups.id", ondelete="SET NULL"), nullable=True)
    budget = Column(Float)
    spend = Column(Float, default=0)
    revenue = Column(Float, default=0)
    leads = Column(Integer, default=0)
    orders_count = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    impressions = Column(Integer, default=0)
    start_date = Column(Date)
    end_date = Column(Date)
    target_url = Column(Text)
    description = Column(Text)
    metadata_json = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class VisitorProfile(Base):
    __tablename__ = "visitor_profiles"
    id = Column(String, primary_key=True)
    fingerprint = Column(String(128), unique=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    ip_hash = Column(String(64))
    city = Column(String(100))
    state = Column(String(50))
    country = Column(String(50))
    neighborhood = Column(String(120))
    latitude = Column(Float)
    longitude = Column(Float)
    location_accuracy_m = Column(Float)
    location_captured_at = Column(DateTime(timezone=True))
    device_type = Column(String(30))
    browser = Column(String(80))
    os = Column(String(80))
    first_seen_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    total_sessions = Column(Integer, default=0)
    total_pageviews = Column(Integer, default=0)
    total_orders = Column(Integer, default=0)


class VisitorSession(Base):
    __tablename__ = "visitor_sessions"
    id = Column(String, primary_key=True)
    visitor_id = Column(String, ForeignKey("visitor_profiles.id", ondelete="CASCADE"), nullable=False)
    utm_source = Column(String(100))
    utm_medium = Column(String(100))
    utm_campaign = Column(String(200))
    utm_content = Column(String(200))
    utm_term = Column(String(200))
    landing_page = Column(Text)
    referrer = Column(Text)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime(timezone=True))
    pageviews = Column(Integer, default=0)


class VisitorEvent(Base):
    __tablename__ = "visitor_events"
    id = Column(String, primary_key=True)
    visitor_id = Column(String, ForeignKey("visitor_profiles.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(String, ForeignKey("visitor_sessions.id", ondelete="SET NULL"), nullable=True)
    event_type = Column(String(80), nullable=False)
    page = Column(Text)
    product_id = Column(String)
    metadata_json = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TrackingLink(Base):
    __tablename__ = "tracking_links"
    id = Column(String, primary_key=True)
    slug = Column(String(100), unique=True, nullable=False)
    destination_url = Column(Text, nullable=False)
    campaign_id = Column(String, ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), nullable=True)
    product_id = Column(String, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    coupon_id = Column(String, ForeignKey("coupons.id", ondelete="SET NULL"), nullable=True)
    utm_source = Column(String(100))
    utm_medium = Column(String(100))
    utm_campaign = Column(String(200))
    clicks = Column(Integer, default=0)
    unique_clicks = Column(Integer, default=0)
    orders_count = Column(Integer, default=0)
    revenue = Column(Float, default=0)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class MarketingSettings(Base):
    __tablename__ = "marketing_settings"
    id = Column(String, primary_key=True, default="default")
    tracking_enabled = Column(Boolean, default=True)
    ip_anonymization = Column(Boolean, default=True)
    online_visitor_minutes = Column(Integer, default=5)
    data_retention_days = Column(Integer, default=365)
    attribution_window_days = Column(Integer, default=30)
    default_utm_source = Column(String(100))
    default_utm_medium = Column(String(100))
    tracking_domain = Column(String(300))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class IntegrationConnection(Base):
    __tablename__ = "integration_connections"
    id = Column(String, primary_key=True)
    integration_type = Column(String(50), nullable=False, unique=True)
    status = Column(String(20), default="disconnected")
    credentials_json = Column(Text)
    last_sync_at = Column(DateTime(timezone=True))
    last_error = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


SECRET_KEYS = {
    "access_token",
    "client_secret",
    "app_secret",
    "password",
    "smtp_password",
    "api_key",
    "token",
    "evolution_api_key",
    "uazapi_token",
}
MASKED_SECRET = "********"
INTERNAL_TRACKING_PREFIXES = ("/painel", "/motoboy")
INTEGRATION_LABELS = {
    "meta_ads": "Meta Ads",
    "google_ads": "Google Ads",
    "tiktok_ads": "TikTok Ads",
    "whatsapp_cloud": "WhatsApp Cloud API",
    "whatsapp_qr": "WhatsApp QR Code",
    "whatsapp_unofficial": "API nao oficial",
    "smtp": "SMTP / E-mail",
}


def _load_credentials(conn: IntegrationConnection) -> dict:
    if not conn.credentials_json:
        return {}
    try:
        data = json.loads(conn.credentials_json)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _date_iso(value) -> str | None:
    return value.isoformat() if value else None


def _campaign_roas(revenue: float | None, spend: float | None) -> float:
    return round((revenue or 0) / spend, 2) if spend and spend > 0 else 0


def _marketing_campaign_to_dict(c: MarketingCampaign) -> dict:
    spend = c.spend or 0
    revenue = c.revenue or 0
    return {
        "id": c.id,
        "external_id": c.id,
        "source": "marketing",
        "source_label": "Central de Campanhas",
        "source_url": "/painel/marketing/campanhas",
        "read_only": False,
        "name": c.name,
        "campaign_type": c.campaign_type,
        "type": c.campaign_type,
        "channel": c.channel or "internal",
        "status": c.status,
        "budget": c.budget or 0,
        "spend": spend,
        "spent": spend,
        "revenue": revenue,
        "orders_count": c.orders_count or 0,
        "orders": c.orders_count or 0,
        "leads": c.leads or 0,
        "clicks": c.clicks or 0,
        "impressions": c.impressions or 0,
        "roas": _campaign_roas(revenue, spend),
        "start_date": _date_iso(c.start_date),
        "end_date": _date_iso(c.end_date),
        "description": c.description,
        "target_url": c.target_url,
        "destination_url": c.target_url,
        "created_at": _date_iso(c.created_at),
    }


def _traffic_campaign_to_marketing_dict(c: TrafficCampaign) -> dict:
    budget = c.total_budget if c.total_budget is not None else c.daily_budget
    return {
        "id": f"paid_traffic:{c.id}",
        "external_id": c.id,
        "source": "paid_traffic",
        "source_label": "Trafego Pago",
        "source_url": "/painel/trafego-pago",
        "read_only": True,
        "name": c.name,
        "campaign_type": "paid_traffic",
        "type": "paid_traffic",
        "channel": "paid_traffic",
        "status": c.status or "draft",
        "budget": budget or 0,
        "spend": 0,
        "spent": 0,
        "revenue": 0,
        "orders_count": 0,
        "orders": 0,
        "leads": 0,
        "clicks": 0,
        "impressions": 0,
        "roas": 0,
        "start_date": _date_iso(c.start_date),
        "end_date": _date_iso(c.end_date),
        "description": c.notes,
        "target_url": c.destination_url,
        "destination_url": c.destination_url,
        "created_at": _date_iso(c.created_at),
    }


def _whatsapp_campaign_to_marketing_dict(c: WhatsAppCampaign) -> dict:
    return {
        "id": f"whatsapp:{c.id}",
        "external_id": c.id,
        "source": "whatsapp",
        "source_label": "Disparador de WhatsApp",
        "source_url": "/painel/marketing/whatsapp",
        "read_only": True,
        "name": c.name,
        "campaign_type": "whatsapp",
        "type": "whatsapp",
        "channel": "whatsapp",
        "status": c.status or "draft",
        "budget": 0,
        "spend": 0,
        "spent": 0,
        "revenue": 0,
        "orders_count": 0,
        "orders": 0,
        "leads": c.sent_count or 0,
        "clicks": c.read_count or 0,
        "impressions": c.delivered_count or 0,
        "roas": 0,
        "start_date": _date_iso(c.scheduled_at),
        "end_date": None,
        "description": "Campanha criada no Disparador de WhatsApp.",
        "target_url": None,
        "destination_url": None,
        "created_at": _date_iso(c.created_at),
    }


def _email_campaign_to_marketing_dict(c: EmailCampaign) -> dict:
    return {
        "id": f"email:{c.id}",
        "external_id": c.id,
        "source": "email",
        "source_label": "Disparador de Email",
        "source_url": "/painel/marketing/email",
        "read_only": True,
        "name": c.name,
        "campaign_type": "email",
        "type": "email",
        "channel": "email",
        "status": c.status or "draft",
        "budget": 0,
        "spend": 0,
        "spent": 0,
        "revenue": 0,
        "orders_count": 0,
        "orders": 0,
        "leads": c.sent_count or 0,
        "clicks": c.click_count or 0,
        "impressions": c.delivered_count or 0,
        "roas": 0,
        "start_date": _date_iso(c.scheduled_at),
        "end_date": None,
        "description": "Campanha criada no Disparador de Email.",
        "target_url": None,
        "destination_url": None,
        "created_at": _date_iso(c.created_at),
    }


def _public_credentials(creds: dict) -> dict:
    public = {}
    for key, value in creds.items():
        public[key] = MASKED_SECRET if key in SECRET_KEYS and value else value
    return public


def _merge_credentials(current: dict, incoming: dict) -> dict:
    merged = dict(current)
    for key, value in (incoming or {}).items():
        if key in SECRET_KEYS and value == MASKED_SECRET:
            continue
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return merged


def _normalize_unofficial_whatsapp_provider(value: str | None) -> str:
    provider = (value or "evolution").strip().lower()
    if provider in {"uazapi", "uazapi_api", "uazapigo"}:
        return "uazapi"
    return "evolution"


def _sync_unofficial_whatsapp_config(db: Session, creds: dict, now: datetime) -> None:
    provider = _normalize_unofficial_whatsapp_provider(creds.get("provider"))
    db.execute(text("INSERT INTO whatsapp_config (id) VALUES ('default') ON CONFLICT DO NOTHING"))
    if provider == "uazapi":
        db.execute(
            text(
                """
                UPDATE whatsapp_config
                SET connection_type = 'uazapi',
                    uazapi_base_url = :base_url,
                    uazapi_token = :token,
                    uazapi_instance = :instance,
                    status = :status,
                    updated_at = :now
                WHERE id = 'default'
                """
            ),
            {
                "base_url": (creds.get("uazapi_base_url") or "").strip().rstrip("/"),
                "token": (creds.get("uazapi_token") or "").strip(),
                "instance": (creds.get("uazapi_instance") or "").strip(),
                "status": "connected" if creds.get("uazapi_base_url") and creds.get("uazapi_token") else "disconnected",
                "now": now,
            },
        )
        return

    db.execute(
        text(
            """
            UPDATE whatsapp_config
            SET connection_type = 'evolution',
                evolution_base_url = :base_url,
                evolution_api_key = :api_key,
                evolution_instance = :instance,
                status = :status,
                updated_at = :now
            WHERE id = 'default'
            """
        ),
        {
            "base_url": (creds.get("evolution_base_url") or "").strip().rstrip("/"),
            "api_key": (creds.get("evolution_api_key") or "").strip(),
            "instance": (creds.get("evolution_instance") or "").strip(),
            "status": "connected" if all([
                creds.get("evolution_base_url"),
                creds.get("evolution_api_key"),
                creds.get("evolution_instance"),
            ]) else "disconnected",
            "now": now,
        },
    )


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class CampaignCreate(BaseModel):
    name: str
    campaign_type: str
    channel: str | None = None
    status: str = "draft"
    product_id: str | None = None
    coupon_id: str | None = None
    group_id: str | None = None
    budget: float | None = None
    start_date: str | None = None
    end_date: str | None = None
    target_url: str | None = None
    description: str | None = None


class CampaignUpdate(BaseModel):
    name: str | None = None
    status: str | None = None
    budget: float | None = None
    spend: float | None = None
    revenue: float | None = None
    description: str | None = None
    target_url: str | None = None


class TrackingLinkCreate(BaseModel):
    slug: str
    destination_url: str
    campaign_id: str | None = None
    product_id: str | None = None
    coupon_id: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None


class VisitorEventIn(BaseModel):
    fingerprint: str
    session_id: str | None = None
    event_type: str
    page: str | None = None
    product_id: str | None = None
    metadata: dict = {}
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None
    referrer: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_accuracy_m: float | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_ip(ip: str | None, anonymize: bool = True) -> str:
    if not ip:
        return ""
    if anonymize:
        parts = ip.split(".")
        if len(parts) == 4:
            ip = ".".join(parts[:3] + ["0"])
    return hashlib.sha256(ip.encode()).hexdigest()[:32]


def _tracking_path(value: str | None) -> str:
    if not value:
        return ""
    try:
        if value.startswith(("http://", "https://")):
            return urlparse(value).path or ""
    except Exception:
        return value
    return value


def _is_internal_tracking_page(value: str | None) -> bool:
    path = _tracking_path(value)
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in INTERNAL_TRACKING_PREFIXES)


def _public_tracking_sql(column: str) -> str:
    value = f"COALESCE({column}, '')"
    filters = []
    for prefix in INTERNAL_TRACKING_PREFIXES:
        filters.extend([
            f"{value} NOT LIKE '{prefix}%'",
            f"{value} NOT LIKE '%://%{prefix}%'",
        ])
    return f"({value} = '' OR ({' AND '.join(filters)}))"


def _get_or_create_visitor(fingerprint: str, db: Session, ip_hash: str = "") -> VisitorProfile:
    visitor = db.query(VisitorProfile).filter(VisitorProfile.fingerprint == fingerprint).first()
    if not visitor:
        visitor = VisitorProfile(id=str(uuid.uuid4()), fingerprint=fingerprint, ip_hash=ip_hash)
        db.add(visitor)
        db.flush()
    visitor.last_seen_at = datetime.now(timezone.utc)
    return visitor


def _client_device(user_agent: str | None) -> tuple[str, str, str]:
    agent = (user_agent or "").lower()
    if "tablet" in agent or "ipad" in agent:
        device = "tablet"
    elif "mobile" in agent or "android" in agent or "iphone" in agent:
        device = "mobile"
    else:
        device = "desktop"

    if "edg/" in agent:
        browser = "Edge"
    elif "chrome/" in agent and "chromium" not in agent:
        browser = "Chrome"
    elif "firefox/" in agent:
        browser = "Firefox"
    elif "safari/" in agent and "chrome/" not in agent:
        browser = "Safari"
    else:
        browser = "Outro"

    if "windows" in agent:
        os_name = "Windows"
    elif "android" in agent:
        os_name = "Android"
    elif "iphone" in agent or "ipad" in agent or "ios" in agent:
        os_name = "iOS"
    elif "mac os" in agent or "macintosh" in agent:
        os_name = "macOS"
    elif "linux" in agent:
        os_name = "Linux"
    else:
        os_name = "Outro"

    return device, browser, os_name


def _reverse_geocode(latitude: float, longitude: float) -> dict:
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                "format": "jsonv2",
                "lat": latitude,
                "lon": longitude,
                "zoom": 16,
                "addressdetails": 1,
            },
            headers={"User-Agent": "MoschettieriSaaS/1.0 visitor-analytics"},
            timeout=3,
        )
        if resp.status_code != 200:
            return {}
        address = (resp.json() or {}).get("address") or {}
        neighborhood = (
            address.get("neighbourhood")
            or address.get("suburb")
            or address.get("quarter")
            or address.get("city_district")
            or address.get("district")
        )
        return {
            "neighborhood": neighborhood,
            "city": address.get("city") or address.get("town") or address.get("village") or address.get("municipality"),
            "state": address.get("state"),
            "country": address.get("country"),
        }
    except Exception:
        return {}


# ── Campaign routes ───────────────────────────────────────────────────────────

@router.get("/campaigns")
def list_campaigns(
    status: str | None = None, channel: str | None = None,
    db: Session = Depends(get_db), _=Depends(get_current_admin)
):
    q = db.query(MarketingCampaign)
    if status:
        q = q.filter(MarketingCampaign.status == status)
    if channel:
        q = q.filter(MarketingCampaign.channel == channel)
    campaigns = q.order_by(MarketingCampaign.created_at.desc()).all()
    return ok([_marketing_campaign_to_dict(c) for c in campaigns])


@router.get("/campaigns/aggregate")
def list_campaigns_aggregate(
    status: str | None = None, channel: str | None = None,
    db: Session = Depends(get_db), _=Depends(get_current_admin)
):
    campaigns = [
        *[_marketing_campaign_to_dict(c) for c in db.query(MarketingCampaign).all()],
        *[_traffic_campaign_to_marketing_dict(c) for c in db.query(TrafficCampaign).all()],
        *[_whatsapp_campaign_to_marketing_dict(c) for c in db.query(WhatsAppCampaign).all()],
        *[_email_campaign_to_marketing_dict(c) for c in db.query(EmailCampaign).all()],
    ]
    if status:
        campaigns = [c for c in campaigns if c["status"] == status]
    if channel:
        campaigns = [c for c in campaigns if c["channel"] == channel]
    campaigns.sort(key=lambda c: c.get("created_at") or "", reverse=True)
    return ok(campaigns)


@router.post("/campaigns")
def create_campaign(body: CampaignCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    from datetime import date
    c = MarketingCampaign(
        id=str(uuid.uuid4()), name=body.name, campaign_type=body.campaign_type,
        channel=body.channel, status=body.status, product_id=body.product_id,
        coupon_id=body.coupon_id, group_id=body.group_id, budget=body.budget,
        target_url=body.target_url, description=body.description,
        start_date=date.fromisoformat(body.start_date) if body.start_date else None,
        end_date=date.fromisoformat(body.end_date) if body.end_date else None,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return created({"id": c.id, "name": c.name, "status": c.status}, "Campanha criada.")


@router.patch("/campaigns/{campaign_id}")
def update_campaign(campaign_id: str, body: CampaignUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    c = db.query(MarketingCampaign).filter(MarketingCampaign.id == campaign_id).first()
    if not c:
        raise HTTPException(404, "Campanha não encontrada.")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(c, field, value)
    c.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ok({"id": c.id, "status": c.status})


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    c = db.query(MarketingCampaign).filter(MarketingCampaign.id == campaign_id).first()
    if not c:
        raise HTTPException(404, "Campanha não encontrada.")
    db.delete(c)
    db.commit()
    return ok(None, "Campanha removida.")


# ── Marketing Dashboard ───────────────────────────────────────────────────────

@router.get("/dashboard")
def marketing_dashboard(
    period: str = Query("7d", regex="^(today|yesterday|7d|30d|90d)$"),
    db: Session = Depends(get_db), _=Depends(get_current_admin)
):
    now = datetime.now(timezone.utc)
    today = local_today()
    if period == "today":
        start_date = today
        end_date = today
    elif period == "yesterday":
        start_date = today - timedelta(days=1)
        end_date = start_date
    elif period == "30d":
        start_date = today - timedelta(days=29)
        end_date = today
    elif period == "90d":
        start_date = today - timedelta(days=89)
        end_date = today
    else:
        start_date = today - timedelta(days=6)
        end_date = today
    since, period_end = local_period_bounds(start_date, end_date)

    total_campaigns = db.query(func.count(MarketingCampaign.id)).scalar() or 0
    active_campaigns = db.query(func.count(MarketingCampaign.id)).filter(MarketingCampaign.status == "active").scalar() or 0
    total_revenue = db.query(func.sum(MarketingCampaign.revenue)).scalar() or 0
    total_spend = db.query(func.sum(MarketingCampaign.spend)).scalar() or 0
    total_clicks = db.query(func.sum(MarketingCampaign.clicks)).scalar() or 0
    total_orders = db.query(func.sum(MarketingCampaign.orders_count)).scalar() or 0
    total_leads = db.query(func.sum(MarketingCampaign.leads)).scalar() or 0

    public_event_filter = _public_tracking_sql("page")
    visitors_period = db.execute(text(f"""
        SELECT COUNT(*)
        FROM (
            SELECT DISTINCT visitor_id
            FROM visitor_events
            WHERE created_at >= :since AND created_at <= :period_end
              AND {public_event_filter}
            UNION
            SELECT DISTINCT visitor_id
            FROM visitor_sessions
            WHERE started_at >= :since AND started_at <= :period_end
              AND {_public_tracking_sql("landing_page")}
        ) visitors
    """), {"since": since, "period_end": period_end}).scalar() or 0
    online_since = now - timedelta(minutes=5)
    visitors_online = db.execute(text(f"""
        SELECT COUNT(DISTINCT visitor_id)
        FROM visitor_events
        WHERE created_at >= :online_since
          AND {public_event_filter}
    """), {"online_since": online_since}).scalar() or 0

    tracking_links = db.query(func.count(TrackingLink.id)).filter(TrackingLink.active == True).scalar() or 0  # noqa: E712
    link_clicks = db.query(func.sum(TrackingLink.clicks)).scalar() or 0

    roas = round(total_revenue / total_spend, 2) if total_spend > 0 else None
    cpa = round(total_spend / total_orders, 2) if total_orders > 0 else None

    channels = db.execute(text("""
        SELECT channel, COUNT(id) as count, SUM(revenue) as rev, SUM(spend) as spend
        FROM marketing_campaigns WHERE channel IS NOT NULL
        GROUP BY channel ORDER BY rev DESC NULLS LAST
    """)).fetchall()
    recent_campaigns = (
        db.query(MarketingCampaign)
        .order_by(MarketingCampaign.created_at.desc())
        .limit(8)
        .all()
    )
    by_channel = [
        {"channel": r[0], "campaigns": r[1], "revenue": round(r[2] or 0, 2), "spend": round(r[3] or 0, 2)}
        for r in channels
    ]

    return ok({
        "period": period,
        "campaigns": {"total": total_campaigns, "active": active_campaigns},
        "financials": {
            "revenue": round(total_revenue, 2), "spend": round(total_spend, 2),
            "roas": roas, "cpa": cpa,
        },
        "engagement": {
            "clicks": total_clicks, "orders": total_orders, "leads": total_leads,
        },
        "visitors": {"period": visitors_period, "online": visitors_online},
        "tracking_links": {"active": tracking_links, "clicks": int(link_clicks or 0)},
        "by_channel": by_channel,
        "total_investment": round(total_spend, 2),
        "revenue_generated": round(total_revenue, 2),
        "roas": roas or 0,
        "roi": round((total_revenue - total_spend) / total_spend, 4) if total_spend > 0 else 0,
        "cpa": cpa or 0,
        "cac": cpa or 0,
        "visitors": visitors_period,
        "leads": int(total_leads or 0),
        "clients_generated": int(total_orders or 0),
        "active_campaigns": active_campaigns,
        "clicks": int(total_clicks or 0),
        "orders": int(total_orders or 0),
        "online_visitors": visitors_online,
        "revenue_by_channel": [{"channel": r["channel"], "revenue": r["revenue"]} for r in by_channel],
        "recent_campaigns": [{
            "id": c.id,
            "name": c.name,
            "channel": c.channel or "",
            "status": c.status,
            "investment": c.spend or c.budget or 0,
            "revenue": c.revenue or 0,
            "roas": round((c.revenue or 0) / (c.spend or 0), 2) if c.spend and c.spend > 0 else 0,
        } for c in recent_campaigns],
    })


# ── Tracking links ────────────────────────────────────────────────────────────

@router.get("/tracking-links")
def list_tracking_links(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    links = db.query(TrackingLink).filter(TrackingLink.active == True).order_by(TrackingLink.created_at.desc()).all()  # noqa: E712
    return ok([{
        "id": l.id, "slug": l.slug, "destination_url": l.destination_url,
        "clicks": l.clicks, "unique_clicks": l.unique_clicks, "orders_count": l.orders_count,
        "revenue": l.revenue, "utm_source": l.utm_source, "utm_medium": l.utm_medium,
        "utm_campaign": l.utm_campaign, "created_at": l.created_at.isoformat(),
    } for l in links])


@router.post("/tracking-links")
def create_tracking_link(body: TrackingLinkCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    slug = body.slug.lower().strip().replace(" ", "-")
    if db.query(TrackingLink).filter(TrackingLink.slug == slug).first():
        raise HTTPException(400, f"Slug '{slug}' já existe.")
    link = TrackingLink(
        id=str(uuid.uuid4()), slug=slug, destination_url=body.destination_url,
        campaign_id=body.campaign_id, product_id=body.product_id, coupon_id=body.coupon_id,
        utm_source=body.utm_source, utm_medium=body.utm_medium, utm_campaign=body.utm_campaign,
    )
    db.add(link)
    db.commit()
    return created({"id": link.id, "slug": link.slug}, "Link criado.")


@router.delete("/tracking-links/{link_id}")
def delete_tracking_link(link_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    link = db.query(TrackingLink).filter(TrackingLink.id == link_id).first()
    if not link:
        raise HTTPException(404, "Link não encontrado.")
    link.active = False
    db.commit()
    return ok(None, "Link desativado.")


# ── Visitor events (public — called from frontend tracking script) ─────────────

@public_router.post("/track")
async def track_event(body: VisitorEventIn, request: Request, db: Session = Depends(get_db)):
    if _is_internal_tracking_page(body.page):
        return {"ok": True, "ignored": True}

    settings = db.query(MarketingSettings).filter(MarketingSettings.id == "default").first()
    if settings and not settings.tracking_enabled:
        return {"ok": True}

    ip = request.client.host if request.client else None
    ip_hash = _hash_ip(ip, anonymize=settings.ip_anonymization if settings else True)

    visitor = _get_or_create_visitor(body.fingerprint, db, ip_hash)
    device, browser, os_name = _client_device(request.headers.get("user-agent"))
    visitor.device_type = visitor.device_type or device
    visitor.browser = visitor.browser or browser
    visitor.os = visitor.os or os_name
    if body.latitude is not None and body.longitude is not None:
        visitor.latitude = body.latitude
        visitor.longitude = body.longitude
        visitor.location_accuracy_m = body.location_accuracy_m
        visitor.location_captured_at = datetime.now(timezone.utc)
        if not visitor.city or not visitor.neighborhood:
            location = _reverse_geocode(body.latitude, body.longitude)
            visitor.neighborhood = location.get("neighborhood") or visitor.neighborhood
            visitor.city = location.get("city") or visitor.city
            visitor.state = location.get("state") or visitor.state
            visitor.country = location.get("country") or visitor.country

    # Create / reuse session
    session = None
    if body.session_id:
        session = db.query(VisitorSession).filter(VisitorSession.id == body.session_id).first()
    if not session and body.event_type == "page_view":
        session = VisitorSession(
            id=body.session_id or str(uuid.uuid4()), visitor_id=visitor.id,
            utm_source=body.utm_source, utm_medium=body.utm_medium,
            utm_campaign=body.utm_campaign, utm_content=body.utm_content,
            utm_term=body.utm_term, landing_page=body.page, referrer=body.referrer,
        )
        db.add(session)
        visitor.total_sessions = (visitor.total_sessions or 0) + 1
        db.flush()

    event = VisitorEvent(
        id=str(uuid.uuid4()), visitor_id=visitor.id,
        session_id=session.id if session else None,
        event_type=body.event_type, page=body.page, product_id=body.product_id,
        metadata_json=json.dumps(body.metadata) if body.metadata else None,
    )
    db.add(event)
    if body.event_type == "page_view":
        visitor.total_pageviews = (visitor.total_pageviews or 0) + 1
        if session:
            session.pageviews = (session.pageviews or 0) + 1
    if body.event_type == "order_created":
        visitor.total_orders = (visitor.total_orders or 0) + 1

    db.commit()
    return {"ok": True, "session_id": session.id if session else body.session_id, "visitor_id": visitor.id}


# ── Visitors admin ────────────────────────────────────────────────────────────

@router.get("/visitors")
def list_visitors(
    period: str = Query("today", regex="^(today|7d|30d|90d)$"),
    selected_date: date | None = Query(default=None, alias="date"),
    limit: int = 100,
    db: Session = Depends(get_db), _=Depends(get_current_admin)
):
    now = datetime.now(timezone.utc)
    if selected_date:
        start_date = selected_date
        end_date = selected_date
        start_dt, end_dt = local_period_bounds(start_date, end_date)
        period_label = "date"
    else:
        _period_days = {"today": 1, "7d": 7, "30d": 30, "90d": 90}
        days = _period_days.get(period, 1)
        end_date = local_today()
        start_date = end_date - timedelta(days=days - 1)
        start_dt, end_dt = local_period_bounds(start_date, end_date)
        period_label = period

    params = {"start_dt": start_dt, "end_dt": end_dt}
    public_event_filter = _public_tracking_sql("page")
    public_session_filter = _public_tracking_sql("landing_page")
    period_visitors_cte = """
        SELECT DISTINCT visitor_id
        FROM visitor_events
        WHERE created_at >= :start_dt AND created_at <= :end_dt
          AND {public_event_filter}
        UNION
        SELECT DISTINCT visitor_id
        FROM visitor_sessions
        WHERE started_at >= :start_dt AND started_at <= :end_dt
          AND {public_session_filter}
    """.format(public_event_filter=public_event_filter, public_session_filter=public_session_filter)

    total = db.execute(
        text(f"SELECT COUNT(*) FROM ({period_visitors_cte}) period_visitors"),
        params,
    ).scalar() or 0
    settings = db.query(MarketingSettings).filter(MarketingSettings.id == "default").first()
    online_minutes = settings.online_visitor_minutes if settings and settings.online_visitor_minutes else 5
    online_since = now - timedelta(minutes=online_minutes)
    online = db.execute(text(f"""
        SELECT COUNT(DISTINCT visitor_id)
        FROM visitor_events
        WHERE created_at >= :online_since
          AND {public_event_filter}
    """), {"online_since": online_since}).scalar() or 0
    online_registered_customers = db.query(func.count(func.distinct(CustomerEvent.customer_id))).filter(
        CustomerEvent.created_at >= online_since,
        CustomerEvent.customer_id.isnot(None),
    ).scalar() or 0

    recent_rows = db.execute(text(f"""
        WITH period_visitors AS ({period_visitors_cte}),
        period_sessions AS (
            SELECT visitor_id, COUNT(*) AS sessions, COALESCE(SUM(pageviews), 0) AS session_pageviews
            FROM visitor_sessions
            WHERE started_at >= :start_dt AND started_at <= :end_dt
              AND {public_session_filter}
            GROUP BY visitor_id
        ),
        period_events AS (
            SELECT
                visitor_id,
                COUNT(*) AS events,
                COUNT(*) FILTER (WHERE event_type = 'page_view') AS event_pageviews,
                MAX(created_at) AS last_event_at
            FROM visitor_events
            WHERE created_at >= :start_dt AND created_at <= :end_dt
              AND {public_event_filter}
            GROUP BY visitor_id
        )
        SELECT
            vp.id,
            vp.city,
            vp.neighborhood,
            vp.country,
            vp.device_type,
            vp.browser,
            vp.latitude,
            vp.longitude,
            vp.location_accuracy_m,
            vp.location_captured_at,
            vp.last_seen_at,
            COALESCE(ps.sessions, 0) AS sessions,
            GREATEST(COALESCE(ps.session_pageviews, 0), COALESCE(pe.event_pageviews, 0)) AS pageviews,
            COALESCE(pe.events, 0) AS events,
            COALESCE(pe.last_event_at, vp.last_seen_at) AS period_last_seen
        FROM visitor_profiles vp
        JOIN period_visitors pv ON pv.visitor_id = vp.id
        LEFT JOIN period_sessions ps ON ps.visitor_id = vp.id
        LEFT JOIN period_events pe ON pe.visitor_id = vp.id
        ORDER BY period_last_seen DESC
        LIMIT :limit
    """), {**params, "limit": limit}).fetchall()

    # Top events
    top_events = db.execute(text(f"""
        SELECT event_type, COUNT(*) as cnt
        FROM visitor_events
        WHERE created_at >= :start_dt AND created_at <= :end_dt
          AND {public_event_filter}
        GROUP BY event_type ORDER BY cnt DESC LIMIT 10
    """), params).fetchall()

    # UTM breakdown
    try:
        utm_rows = db.execute(text(f"""
            SELECT
                COALESCE(utm_source, 'direto') AS utm_source,
                utm_medium, utm_campaign,
                COUNT(*) AS sessions,
                COUNT(*) FILTER (WHERE total_orders > 0) AS conversions
            FROM visitor_sessions vs
            JOIN visitor_profiles vp ON vp.id = vs.visitor_id
            WHERE vs.started_at >= :start_dt AND vs.started_at <= :end_dt
              AND {_public_tracking_sql("vs.landing_page")}
            GROUP BY utm_source, utm_medium, utm_campaign
            ORDER BY sessions DESC
            LIMIT 20
        """), params).fetchall()
        utm_breakdown = [{
            "utm_source": r[0], "utm_medium": r[1], "utm_campaign": r[2],
            "sessions": r[3] or 0, "conversions": r[4] or 0,
            "conversion_rate": round((r[4] or 0) / (r[3] or 1) * 100, 2),
        } for r in utm_rows]
    except Exception:
        utm_breakdown = []

    # Device breakdown
    try:
        dev_rows = db.execute(text(f"""
            WITH period_visitors AS ({period_visitors_cte})
            SELECT COALESCE(device_type, 'unknown') AS device_type, COUNT(*) AS sessions
            FROM visitor_profiles vp
            JOIN period_visitors pv ON pv.visitor_id = vp.id
            GROUP BY device_type ORDER BY sessions DESC
        """), params).fetchall()
        total_dev = sum(r[1] for r in dev_rows) or 1
        devices = [{"device_type": r[0], "sessions": r[1] or 0,
                    "percentage": round((r[1] or 0) / total_dev * 100, 1)} for r in dev_rows]
    except Exception:
        devices = []

    # Top products viewed/ordered
    try:
        prod_rows = db.execute(text(f"""
            SELECT p.name,
                   COUNT(ve.id) FILTER (WHERE ve.event_type IN ('product_view', 'product_viewed')) AS views,
                   COUNT(ve.id) FILTER (WHERE ve.event_type IN ('add_to_cart', 'cart_item_added')) AS add_to_cart,
                   COUNT(ve.id) FILTER (WHERE ve.event_type = 'order_created') AS orders,
                   0 AS revenue
            FROM visitor_events ve
            JOIN products p ON p.id = ve.product_id
            WHERE ve.created_at >= :start_dt AND ve.created_at <= :end_dt AND ve.product_id IS NOT NULL
              AND {_public_tracking_sql("ve.page")}
            GROUP BY p.name ORDER BY views DESC LIMIT 10
        """), params).fetchall()
        top_products = [{"name": r[0], "views": r[1] or 0, "add_to_cart": r[2] or 0, "orders": r[3] or 0,
                         "revenue": float(r[4] or 0)} for r in prod_rows]
    except Exception:
        top_products = []

    # Conversion funnel
    try:
        funnel_data = db.execute(text(f"""
            SELECT
                COUNT(DISTINCT visitor_id) FILTER (WHERE event_type IN ('product_view', 'product_viewed', 'product_config_view')) AS product_views,
                COUNT(DISTINCT visitor_id) FILTER (WHERE event_type IN ('add_to_cart', 'cart_item_added', 'cart_opened')) AS carts,
                COUNT(DISTINCT visitor_id) FILTER (WHERE event_type IN ('checkout_start', 'checkout_started')) AS checkouts,
                COUNT(DISTINCT visitor_id) FILTER (WHERE event_type = 'order_created') AS orders
            FROM visitor_events
            WHERE created_at >= :start_dt AND created_at <= :end_dt
              AND {public_event_filter}
        """), params).fetchone()
        product_views = funnel_data[0] or 0
        carts = funnel_data[1] or 0
        checkouts = funnel_data[2] or 0
        orders = funnel_data[3] or 0
        funnel = [
            {"step": "Visitantes", "count": total},
            {"step": "Produtos vistos", "count": product_views},
            {"step": "Carrinho", "count": carts},
            {"step": "Checkout", "count": checkouts},
            {"step": "Pedido finalizado", "count": orders},
        ]
    except Exception:
        funnel = []

    # Count total sessions and events in period
    try:
        total_sessions = db.execute(
            text(f"SELECT COUNT(*) FROM visitor_sessions WHERE started_at >= :start_dt AND started_at <= :end_dt AND {public_session_filter}"),
            params,
        ).scalar() or 0
    except Exception:
        total_sessions = 0

    try:
        total_events = db.execute(
            text(f"SELECT COUNT(*) FROM visitor_events WHERE created_at >= :start_dt AND created_at <= :end_dt AND {public_event_filter}"),
            params,
        ).scalar() or 0
    except Exception:
        total_events = 0

    try:
        bounce_rows = db.execute(text(f"""
            SELECT
                COUNT(*) FILTER (WHERE COALESCE(pageviews, 0) <= 1) AS bounced,
                COUNT(*) AS total
            FROM visitor_sessions
            WHERE started_at >= :start_dt AND started_at <= :end_dt
              AND {public_session_filter}
        """), params).fetchone()
        bounced_sessions = bounce_rows[0] or 0
        sessions_for_bounce = bounce_rows[1] or 0
        bounce_rate = (bounced_sessions / sessions_for_bounce) if sessions_for_bounce else 0
    except Exception:
        bounce_rate = 0

    try:
        avg_session_duration = db.execute(text(f"""
            SELECT COALESCE(AVG(EXTRACT(EPOCH FROM (ended_at - started_at))), 0)
            FROM visitor_sessions
            WHERE started_at >= :start_dt
              AND started_at <= :end_dt
              AND ended_at IS NOT NULL
              AND {public_session_filter}
        """), params).scalar() or 0
    except Exception:
        avg_session_duration = 0

    # Normalize devices to match frontend {device_type, count, pct}
    normalized_devices = [{"device_type": d["device_type"], "count": d["sessions"], "pct": d["percentage"]}
                          for d in devices]

    # Normalize utm to match frontend {source, medium, campaign, sessions, conversions}
    normalized_utm = [{"source": u["utm_source"], "medium": u.get("utm_medium"), "campaign": u.get("utm_campaign"),
                       "sessions": u["sessions"], "conversions": u["conversions"]}
                      for u in utm_breakdown]

    # Normalize top_products to match frontend {product_name, views, add_to_cart, orders}
    normalized_products = [{"product_name": p["name"], "views": p["views"],
                            "add_to_cart": p.get("add_to_cart", 0), "orders": p.get("orders", 0)}
                           for p in top_products]

    # Normalize funnel to match frontend {label, value}
    normalized_funnel = [{"label": f["step"], "value": f["count"]} for f in funnel] if funnel else []

    return ok({
        # Flat fields expected by MarketingVisitantes
        "period": period_label,
        "date_from": start_date.isoformat(),
        "date_to": end_date.isoformat(),
        "visitors_today": total,
        "online_visitors": online,
        "online_registered_customers": online_registered_customers,
        "total_sessions": total_sessions,
        "total_events": total_events,
        "bounce_rate": bounce_rate,
        "avg_session_duration": int(avg_session_duration or 0),
        "recent_visitors": [{
            "id": v[0],
            "city": v[1] or "",
            "neighborhood": v[2] or "",
            "browser": v[5] or "",
            "device": v[4] or "desktop",
            "sessions": int(v[11] or 0),
            "pageviews": int(v[12] or 0),
            "last_seen": (v[14] or v[10]).isoformat() if (v[14] or v[10]) else None,
            "status": "online" if v[10] and v[10] >= online_since else "offline",
            "is_online": bool(v[10] and v[10] >= online_since),
            "latitude": v[6],
            "longitude": v[7],
            "location_accuracy_m": v[8],
            "location_captured_at": v[9].isoformat() if v[9] else None,
        } for v in recent_rows],
        "common_events": [{"name": r[0], "count": r[1]} for r in top_events],
        "utm_breakdown": normalized_utm,
        "devices": normalized_devices,
        "top_products": normalized_products,
        "funnel": normalized_funnel,
        # Legacy nested structure (kept for backward compatibility)
        "summary": {"total": total, "online": online, "online_registered_customers": online_registered_customers},
        "visitors": [{
            "id": v[0], "city": v[1], "neighborhood": v[2], "country": v[3], "device_type": v[4],
            "browser": v[5], "total_sessions": int(v[11] or 0),
            "total_pageviews": int(v[12] or 0), "total_orders": 0,
            "last_seen_at": (v[14] or v[10]).isoformat() if (v[14] or v[10]) else None,
            "status": "online" if v[10] and v[10] >= online_since else "offline",
            "is_online": bool(v[10] and v[10] >= online_since),
            "latitude": v[6],
            "longitude": v[7],
            "location_accuracy_m": v[8],
            "location_captured_at": v[9].isoformat() if v[9] else None,
        } for v in recent_rows],
        "top_events": [{"event": r[0], "count": r[1]} for r in top_events],
    })


# ── Integrations ──────────────────────────────────────────────────────────────

@router.get("/integrations")
def list_integrations(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    conns = db.query(IntegrationConnection).all()
    return ok([{
        "id": c.id,
        "name": INTEGRATION_LABELS.get(c.integration_type, c.integration_type),
        "type": c.integration_type,
        "integration_type": c.integration_type,
        "status": c.status,
        "connected": c.status == "connected",
        "config": _public_credentials(_load_credentials(c)),
        "last_sync_at": c.last_sync_at.isoformat() if c.last_sync_at else None,
        "last_error": c.last_error,
    } for c in conns])


@router.patch("/integrations/{integration_type}")
def update_integration(integration_type: str, body: dict, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    conn = db.query(IntegrationConnection).filter(IntegrationConnection.integration_type == integration_type).first()
    if not conn:
        raise HTTPException(404, "Integração não encontrada.")
    incoming_credentials = body.get("credentials")
    if incoming_credentials is None:
        incoming_credentials = body.get("config")
    if incoming_credentials is not None:
        creds = _merge_credentials(_load_credentials(conn), incoming_credentials)
        if integration_type == "whatsapp_unofficial":
            creds["provider"] = _normalize_unofficial_whatsapp_provider(creds.get("provider"))
        conn.credentials_json = json.dumps(creds, ensure_ascii=False)
        if integration_type == "whatsapp_unofficial":
            now = datetime.now(timezone.utc)
            if creds["provider"] == "uazapi":
                conn.status = "connected" if creds.get("uazapi_base_url") and creds.get("uazapi_token") else "disconnected"
            else:
                conn.status = "connected" if all([
                    creds.get("evolution_base_url"),
                    creds.get("evolution_api_key"),
                    creds.get("evolution_instance"),
                ]) else "disconnected"
            _sync_unofficial_whatsapp_config(db, creds, now)
        else:
            conn.status = "connected" if any(v for v in creds.values()) else "disconnected"
    if "status" in body:
        conn.status = body["status"]
    conn.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ok({
        "integration_type": conn.integration_type,
        "type": conn.integration_type,
        "status": conn.status,
        "connected": conn.status == "connected",
        "config": _public_credentials(_load_credentials(conn)),
    })


@router.post("/integrations/{integration_type}/test")
def test_integration(integration_type: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    conn = db.query(IntegrationConnection).filter(IntegrationConnection.integration_type == integration_type).first()
    if not conn:
        return err_msg("Integracao nao encontrada.", code="IntegrationNotFound", status_code=404)

    creds = _load_credentials(conn)
    now = datetime.now(timezone.utc)

    if integration_type == "whatsapp_cloud":
        phone_number_id = creds.get("phone_number_id")
        access_token = creds.get("access_token")
        if not phone_number_id or not access_token:
            conn.status = "disconnected"
            conn.last_error = "Informe phone_number_id e access_token."
            conn.updated_at = now
            db.commit()
            return err_msg(conn.last_error, code="WhatsAppConfigMissing")
        try:
            resp = requests.get(
                f"https://graph.facebook.com/v19.0/{phone_number_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"fields": "id,display_phone_number,verified_name"},
                timeout=15,
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("id"):
                conn.status = "connected"
                conn.last_error = None
                conn.last_sync_at = now
                conn.updated_at = now
                db.execute(text("INSERT INTO whatsapp_config (id) VALUES ('default') ON CONFLICT DO NOTHING"))
                db.execute(
                    text("UPDATE whatsapp_config SET status = 'connected', connection_type = 'official', updated_at = :now WHERE id = 'default'"),
                    {"now": now},
                )
                db.commit()
                return ok({"connected": True, "display_phone_number": data.get("display_phone_number")}, "WhatsApp Cloud API conectada.")
            message = data.get("error", {}).get("message", resp.text)
            conn.status = "disconnected"
            conn.last_error = message
            conn.updated_at = now
            db.execute(text("INSERT INTO whatsapp_config (id) VALUES ('default') ON CONFLICT DO NOTHING"))
            db.execute(text("UPDATE whatsapp_config SET status = 'disconnected', updated_at = :now WHERE id = 'default'"), {"now": now})
            db.commit()
            return err_msg(message, code="WhatsAppConnectionFailed")
        except Exception as exc:
            conn.status = "disconnected"
            conn.last_error = str(exc)
            conn.updated_at = now
            db.execute(text("INSERT INTO whatsapp_config (id) VALUES ('default') ON CONFLICT DO NOTHING"))
            db.execute(text("UPDATE whatsapp_config SET status = 'disconnected', updated_at = :now WHERE id = 'default'"), {"now": now})
            db.commit()
            return err_msg(str(exc), code="WhatsAppConnectionFailed")

    if integration_type == "whatsapp_qr":
        conn.status = "disconnected"
        conn.last_error = "WhatsApp via QR Code ainda nao possui servico de sessao implementado."
        conn.updated_at = now
        db.commit()
        return err_msg(conn.last_error, code="WhatsAppQrNotImplemented", status_code=501)

    if integration_type == "whatsapp_unofficial":
        provider = _normalize_unofficial_whatsapp_provider(creds.get("provider"))
        if provider == "uazapi":
            missing = []
            if not creds.get("uazapi_base_url"):
                missing.append("URL base")
            if not creds.get("uazapi_token"):
                missing.append("token da instancia")
            if missing:
                conn.status = "disconnected"
                conn.last_error = f"Uazapi incompleta. Informe {', '.join(missing)}."
                conn.updated_at = now
                db.commit()
                return err_msg(conn.last_error, code="UazapiConfigMissing")
            conn.status = "connected"
            conn.last_error = None
            conn.last_sync_at = now
            conn.updated_at = now
            _sync_unofficial_whatsapp_config(db, creds, now)
            db.commit()
            return ok({"connected": True, "provider": "uazapi"}, "Uazapi configurada como API nao oficial.")

        missing = []
        if not creds.get("evolution_base_url"):
            missing.append("URL base")
        if not creds.get("evolution_api_key"):
            missing.append("API Key")
        if not creds.get("evolution_instance"):
            missing.append("instancia")
        if missing:
            conn.status = "disconnected"
            conn.last_error = f"Evolution API incompleta. Informe {', '.join(missing)}."
            conn.updated_at = now
            db.commit()
            return err_msg(conn.last_error, code="EvolutionConfigMissing")
        conn.status = "connected"
        conn.last_error = None
        conn.last_sync_at = now
        conn.updated_at = now
        _sync_unofficial_whatsapp_config(db, creds, now)
        db.commit()
        return ok({"connected": True, "provider": "evolution"}, "Evolution API configurada como API nao oficial.")

    configured = bool(creds)
    conn.status = "connected" if configured else "disconnected"
    conn.last_error = None if configured else "Credenciais nao configuradas."
    conn.last_sync_at = now if configured else conn.last_sync_at
    conn.updated_at = now
    db.commit()
    if configured:
        return ok({"connected": True}, "Integracao configurada.")
    return err_msg(conn.last_error, code="IntegrationConfigMissing")


# ── Marketing settings ────────────────────────────────────────────────────────

@router.get("/settings")
def get_settings(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    s = db.query(MarketingSettings).filter(MarketingSettings.id == "default").first()
    if not s:
        s = MarketingSettings(id="default")
        db.add(s)
        db.commit()
    return ok({
        "tracking_enabled": s.tracking_enabled, "ip_anonymization": s.ip_anonymization,
        "online_visitor_minutes": s.online_visitor_minutes, "data_retention_days": s.data_retention_days,
        "attribution_window_days": s.attribution_window_days,
        "default_utm_source": s.default_utm_source, "default_utm_medium": s.default_utm_medium,
        "tracking_domain": s.tracking_domain,
    })


@router.put("/settings")
def update_settings(body: dict, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    s = db.query(MarketingSettings).filter(MarketingSettings.id == "default").first()
    if not s:
        s = MarketingSettings(id="default")
        db.add(s)
    for k, v in body.items():
        if hasattr(s, k):
            setattr(s, k, v)
    s.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ok({"tracking_enabled": s.tracking_enabled})

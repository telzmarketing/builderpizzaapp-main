"""Marketing — Campaigns, Visitor tracking, Tracking links, Settings."""
import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy import Column, String, Boolean, Integer, Float, Text, DateTime, Date, ForeignKey, func, text
from sqlalchemy.orm import Session

from backend.database import get_db, Base
from backend.routes.admin_auth import get_current_admin
from backend.core.response import ok, created

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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_ip(ip: str | None, anonymize: bool = True) -> str:
    if not ip:
        return ""
    if anonymize:
        parts = ip.split(".")
        if len(parts) == 4:
            ip = ".".join(parts[:3] + ["0"])
    return hashlib.sha256(ip.encode()).hexdigest()[:32]


def _get_or_create_visitor(fingerprint: str, db: Session, ip_hash: str = "") -> VisitorProfile:
    visitor = db.query(VisitorProfile).filter(VisitorProfile.fingerprint == fingerprint).first()
    if not visitor:
        visitor = VisitorProfile(id=str(uuid.uuid4()), fingerprint=fingerprint, ip_hash=ip_hash)
        db.add(visitor)
        db.flush()
    visitor.last_seen_at = datetime.now(timezone.utc)
    return visitor


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
    return ok([{
        "id": c.id, "name": c.name, "campaign_type": c.campaign_type, "channel": c.channel,
        "status": c.status, "budget": c.budget, "spend": c.spend, "revenue": c.revenue,
        "orders_count": c.orders_count, "leads": c.leads, "clicks": c.clicks,
        "roas": round(c.revenue / c.spend, 2) if c.spend and c.spend > 0 else None,
        "start_date": c.start_date.isoformat() if c.start_date else None,
        "end_date": c.end_date.isoformat() if c.end_date else None,
        "description": c.description, "target_url": c.target_url,
        "created_at": c.created_at.isoformat(),
    } for c in campaigns])


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
    period: str = Query("7d", regex="^(today|yesterday|7d|30d)$"),
    db: Session = Depends(get_db), _=Depends(get_current_admin)
):
    now = datetime.now(timezone.utc)
    if period == "today":
        since = now.replace(hour=0, minute=0, second=0)
    elif period == "yesterday":
        since = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0)
    elif period == "30d":
        since = now - timedelta(days=30)
    else:
        since = now - timedelta(days=7)

    total_campaigns = db.query(func.count(MarketingCampaign.id)).scalar() or 0
    active_campaigns = db.query(func.count(MarketingCampaign.id)).filter(MarketingCampaign.status == "active").scalar() or 0
    total_revenue = db.query(func.sum(MarketingCampaign.revenue)).scalar() or 0
    total_spend = db.query(func.sum(MarketingCampaign.spend)).scalar() or 0
    total_clicks = db.query(func.sum(MarketingCampaign.clicks)).scalar() or 0
    total_orders = db.query(func.sum(MarketingCampaign.orders_count)).scalar() or 0
    total_leads = db.query(func.sum(MarketingCampaign.leads)).scalar() or 0

    visitors_period = db.query(func.count(VisitorProfile.id)).filter(
        VisitorProfile.last_seen_at >= since
    ).scalar() or 0
    online_since = now - timedelta(minutes=5)
    visitors_online = db.query(func.count(VisitorProfile.id)).filter(
        VisitorProfile.last_seen_at >= online_since
    ).scalar() or 0

    tracking_links = db.query(func.count(TrackingLink.id)).filter(TrackingLink.active == True).scalar() or 0  # noqa: E712
    link_clicks = db.query(func.sum(TrackingLink.clicks)).scalar() or 0

    roas = round(total_revenue / total_spend, 2) if total_spend > 0 else None
    cpa = round(total_spend / total_orders, 2) if total_orders > 0 else None

    channels = db.execute(text("""
        SELECT channel, COUNT(id) as count, SUM(revenue) as rev, SUM(spend) as spend
        FROM marketing_campaigns WHERE channel IS NOT NULL
        GROUP BY channel ORDER BY rev DESC NULLS LAST
    """)).fetchall()

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
        "by_channel": [
            {"channel": r[0], "campaigns": r[1], "revenue": round(r[2] or 0, 2), "spend": round(r[3] or 0, 2)}
            for r in channels
        ],
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
    settings = db.query(MarketingSettings).filter(MarketingSettings.id == "default").first()
    if settings and not settings.tracking_enabled:
        return {"ok": True}

    ip = request.client.host if request.client else None
    ip_hash = _hash_ip(ip, anonymize=settings.ip_anonymization if settings else True)

    visitor = _get_or_create_visitor(body.fingerprint, db, ip_hash)

    # Create / reuse session
    session = None
    if body.session_id:
        session = db.query(VisitorSession).filter(VisitorSession.id == body.session_id).first()
    if not session and body.event_type == "page_view":
        session = VisitorSession(
            id=str(uuid.uuid4()), visitor_id=visitor.id,
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

    db.commit()
    return {"ok": True, "session_id": session.id if session else body.session_id, "visitor_id": visitor.id}


# ── Visitors admin ────────────────────────────────────────────────────────────

@router.get("/visitors")
def list_visitors(
    period: str = "7d", limit: int = 100,
    db: Session = Depends(get_db), _=Depends(get_current_admin)
):
    now = datetime.now(timezone.utc)
    _period_days = {"today": 1, "7d": 7, "30d": 30, "90d": 90}
    days = _period_days.get(period, 7)
    since = now - timedelta(days=days)

    total = db.query(func.count(VisitorProfile.id)).filter(VisitorProfile.last_seen_at >= since).scalar() or 0
    online_since = now - timedelta(minutes=5)
    online = db.query(func.count(VisitorProfile.id)).filter(VisitorProfile.last_seen_at >= online_since).scalar() or 0

    recent = (db.query(VisitorProfile)
              .filter(VisitorProfile.last_seen_at >= since)
              .order_by(VisitorProfile.last_seen_at.desc())
              .limit(limit).all())

    # Top events
    top_events = db.execute(text("""
        SELECT event_type, COUNT(*) as cnt
        FROM visitor_events
        WHERE created_at >= :since
        GROUP BY event_type ORDER BY cnt DESC LIMIT 10
    """), {"since": since}).fetchall()

    # UTM breakdown
    try:
        utm_rows = db.execute(text("""
            SELECT
                COALESCE(utm_source, 'direto') AS utm_source,
                utm_medium, utm_campaign,
                COUNT(*) AS sessions,
                COUNT(*) FILTER (WHERE total_orders > 0) AS conversions
            FROM visitor_sessions vs
            JOIN visitor_profiles vp ON vp.id = vs.visitor_id
            WHERE vs.started_at >= :since
            GROUP BY utm_source, utm_medium, utm_campaign
            ORDER BY sessions DESC
            LIMIT 20
        """), {"since": since}).fetchall()
        utm_breakdown = [{
            "utm_source": r[0], "utm_medium": r[1], "utm_campaign": r[2],
            "sessions": r[3] or 0, "conversions": r[4] or 0,
            "conversion_rate": round((r[4] or 0) / (r[3] or 1) * 100, 2),
        } for r in utm_rows]
    except Exception:
        utm_breakdown = []

    # Device breakdown
    try:
        dev_rows = db.execute(text("""
            SELECT COALESCE(device_type, 'unknown') AS device_type, COUNT(*) AS sessions
            FROM visitor_profiles
            WHERE last_seen_at >= :since
            GROUP BY device_type ORDER BY sessions DESC
        """), {"since": since}).fetchall()
        total_dev = sum(r[1] for r in dev_rows) or 1
        devices = [{"device_type": r[0], "sessions": r[1] or 0,
                    "percentage": round((r[1] or 0) / total_dev * 100, 1)} for r in dev_rows]
    except Exception:
        devices = []

    # Top products viewed/ordered
    try:
        prod_rows = db.execute(text("""
            SELECT p.name,
                   COUNT(ve.id) FILTER (WHERE ve.event_type = 'product_view') AS views,
                   COUNT(ve.id) FILTER (WHERE ve.event_type = 'add_to_cart') AS orders,
                   0 AS revenue
            FROM visitor_events ve
            JOIN products p ON p.id = ve.product_id
            WHERE ve.created_at >= :since AND ve.product_id IS NOT NULL
            GROUP BY p.name ORDER BY views DESC LIMIT 10
        """), {"since": since}).fetchall()
        top_products = [{"name": r[0], "views": r[1] or 0, "orders": r[2] or 0,
                         "revenue": float(r[3] or 0)} for r in prod_rows]
    except Exception:
        top_products = []

    # Conversion funnel
    try:
        funnel_data = db.execute(text("""
            SELECT
                COUNT(DISTINCT id) FILTER (WHERE total_sessions > 0) AS visited,
                COUNT(DISTINCT id) FILTER (WHERE total_pageviews > 1) AS engaged,
                COUNT(DISTINCT id) FILTER (WHERE total_orders > 0) AS converted
            FROM visitor_profiles
            WHERE last_seen_at >= :since
        """), {"since": since}).fetchone()
        visited = funnel_data[0] or 0
        engaged = funnel_data[1] or 0
        converted = funnel_data[2] or 0
        funnel = [
            {"step": "Visitantes", "count": visited,
             "drop_rate": 0},
            {"step": "Engajados", "count": engaged,
             "drop_rate": round((visited - engaged) / visited * 100, 1) if visited > 0 else 0},
            {"step": "Convertidos", "count": converted,
             "drop_rate": round((engaged - converted) / engaged * 100, 1) if engaged > 0 else 0},
        ]
    except Exception:
        funnel = []

    return ok({
        "summary": {"total": total, "online": online},
        "visitors": [{
            "id": v.id, "city": v.city, "country": v.country, "device_type": v.device_type,
            "browser": v.browser, "total_sessions": v.total_sessions,
            "total_pageviews": v.total_pageviews, "total_orders": v.total_orders,
            "last_seen_at": v.last_seen_at.isoformat(),
        } for v in recent],
        "top_events": [{"event": r[0], "count": r[1]} for r in top_events],
        "utm_breakdown": utm_breakdown,
        "devices": devices,
        "top_products": top_products,
        "funnel": funnel,
    })


# ── Integrations ──────────────────────────────────────────────────────────────

@router.get("/integrations")
def list_integrations(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    conns = db.query(IntegrationConnection).all()
    return ok([{
        "id": c.id, "integration_type": c.integration_type, "status": c.status,
        "last_sync_at": c.last_sync_at.isoformat() if c.last_sync_at else None,
        "last_error": c.last_error,
    } for c in conns])


@router.patch("/integrations/{integration_type}")
def update_integration(integration_type: str, body: dict, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    conn = db.query(IntegrationConnection).filter(IntegrationConnection.integration_type == integration_type).first()
    if not conn:
        raise HTTPException(404, "Integração não encontrada.")
    if "credentials" in body:
        conn.credentials_json = json.dumps(body["credentials"])
        conn.status = "connected"
    if "status" in body:
        conn.status = body["status"]
    conn.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ok({"integration_type": conn.integration_type, "status": conn.status})


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

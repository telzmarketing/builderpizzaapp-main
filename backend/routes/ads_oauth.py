"""Ads Integrations — OAuth + Insights sync para Meta Ads, Google Ads, TikTok Ads."""
from __future__ import annotations

import hashlib
import json
import urllib.parse
import uuid
from datetime import datetime, timezone
from typing import Optional

import requests
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import Column, String, Text, DateTime, Float, Integer, Boolean, text
from sqlalchemy.orm import Session

from backend.core.response import ok, created, err_msg
from backend.database import get_db, Base
from backend.routes.admin_auth import get_current_admin


# ── ORM Models ────────────────────────────────────────────────────────────────

class AdsOAuthState(Base):
    __tablename__ = "ads_oauth_states"
    id = Column(String, primary_key=True)           # estado aleatório CSRF
    platform = Column(String(30), nullable=False)
    redirect_uri = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AdsCampaign(Base):
    __tablename__ = "ads_campaigns"
    id = Column(String, primary_key=True)            # {platform}_{external_id}
    platform = Column(String(30), nullable=False)    # meta | google | tiktok
    external_id = Column(String(200), nullable=False)
    name = Column(String(300))
    status = Column(String(30))                      # ACTIVE | PAUSED | DELETED
    objective = Column(String(100))
    budget_daily = Column(Float)
    spend = Column(Float, default=0)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    revenue = Column(Float, default=0)
    ctr = Column(Float, default=0)
    cpc = Column(Float, default=0)
    cpa = Column(Float, default=0)
    roas = Column(Float, default=0)
    last_synced_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class AdsUtmLink(Base):
    __tablename__ = "ads_utm_links"
    id = Column(String, primary_key=True)
    name = Column(String(300), nullable=False)
    url = Column(Text, nullable=False)
    utm_source = Column(String(100), default="")
    utm_medium = Column(String(100), default="")
    utm_campaign = Column(String(200), default="")
    utm_term = Column(String(200), default="")
    utm_content = Column(String(200), default="")
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AdsPixel(Base):
    __tablename__ = "ads_pixels"
    id = Column(String, primary_key=True)
    platform = Column(String(30), nullable=False)
    pixel_id = Column(String(200), nullable=False)
    enabled = Column(Boolean, default=True)
    events_tracked = Column(String(500), default="PageView,Purchase,Lead")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


# ── Pydantic schemas (UTM + Pixel) ────────────────────────────────────────────

class UtmLinkCreate(BaseModel):
    name: str
    url: str
    utm_source: str = ""
    utm_medium: str = ""
    utm_campaign: str = ""
    utm_term: str = ""
    utm_content: str = ""


class PixelCreate(BaseModel):
    platform: str
    pixel_id: str
    events_tracked: str = "PageView,Purchase,Lead"


class PixelUpdate(BaseModel):
    enabled: Optional[bool] = None
    events_tracked: Optional[str] = None
    pixel_id: Optional[str] = None


# ── Helper: credentials CRUD ──────────────────────────────────────────────────

def _get_creds(platform: str, db: Session) -> dict | None:
    """Fetch credentials from integration_connections for the given platform."""
    try:
        row = db.execute(
            text("SELECT credentials_json FROM integration_connections WHERE integration_type = :p"),
            {"p": platform},
        ).fetchone()
        if row is None or not row[0]:
            return None
        return json.loads(row[0])
    except Exception:
        return None


def _save_creds(platform: str, creds: dict, db: Session) -> None:
    """Upsert credentials into integration_connections."""
    now = datetime.now(timezone.utc)
    creds_json = json.dumps(creds)
    try:
        existing = db.execute(
            text("SELECT id FROM integration_connections WHERE integration_type = :p"),
            {"p": platform},
        ).fetchone()
        if existing:
            db.execute(
                text(
                    "UPDATE integration_connections "
                    "SET credentials_json = :c, status = 'connected', updated_at = :u "
                    "WHERE integration_type = :p"
                ),
                {"c": creds_json, "u": now, "p": platform},
            )
        else:
            db.execute(
                text(
                    "INSERT INTO integration_connections (id, integration_type, status, credentials_json, updated_at) "
                    "VALUES (:id, :p, 'connected', :c, :u)"
                ),
                {"id": str(uuid.uuid4()), "p": platform, "c": creds_json, "u": now},
            )
        db.commit()
    except Exception:
        db.rollback()


# ── OAuth URL builders ────────────────────────────────────────────────────────

def _build_meta_auth_url(app_id: str, redirect_uri: str, state: str) -> str:
    return (
        f"https://www.facebook.com/v19.0/dialog/oauth"
        f"?client_id={app_id}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
        f"&scope=ads_read,ads_management,ads_insights"
        f"&response_type=code"
        f"&state={state}"
    )


def _build_google_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    scope = urllib.parse.quote("https://www.googleapis.com/auth/adwords")
    return (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={client_id}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
        f"&scope={scope}"
        f"&response_type=code"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state={state}"
    )


def _build_tiktok_auth_url(app_id: str, redirect_uri: str, state: str) -> str:
    return (
        f"https://business-api.tiktok.com/portal/auth"
        f"?app_id={app_id}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
        f"&state={state}"
        f"&scope=advertiser_management,ad_management"
    )


# ── Token exchange helpers ────────────────────────────────────────────────────

def _exchange_meta_token(code: str, app_id: str, app_secret: str, redirect_uri: str) -> dict:
    """Exchange Meta OAuth code for access token."""
    resp = requests.post(
        "https://graph.facebook.com/v19.0/oauth/access_token",
        data={
            "client_id": app_id,
            "client_secret": app_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()  # access_token, token_type, expires_in


def _exchange_google_token(code: str, client_id: str, client_secret: str, redirect_uri: str) -> dict:
    """Exchange Google OAuth code for access + refresh tokens."""
    resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()  # access_token, refresh_token, expires_in


def _exchange_tiktok_token(code: str, app_id: str, app_secret: str) -> dict:
    """Exchange TikTok OAuth code for access token."""
    resp = requests.post(
        "https://business-api.tiktok.com/open_api/v1.3/oauth2/access_token/",
        json={
            "app_id": app_id,
            "secret": app_secret,
            "auth_code": code,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", data)  # access_token, advertiser_ids


# ── Campaign sync helpers ─────────────────────────────────────────────────────

def _upsert_campaign(db: Session, campaign_id: str, platform: str, external_id: str, fields: dict) -> None:
    """Upsert a single campaign row into ads_campaigns."""
    now = datetime.now(timezone.utc)
    existing = db.query(AdsCampaign).filter(AdsCampaign.id == campaign_id).first()
    if existing:
        for k, v in fields.items():
            if hasattr(existing, k):
                setattr(existing, k, v)
        existing.last_synced_at = now
        existing.updated_at = now
    else:
        row = AdsCampaign(
            id=campaign_id,
            platform=platform,
            external_id=external_id,
            last_synced_at=now,
            **{k: v for k, v in fields.items() if hasattr(AdsCampaign, k)},
        )
        db.add(row)


def _sync_meta_campaigns(creds: dict, db: Session) -> int:
    """Fetch campaigns + insights from Meta Graph API and upsert into ads_campaigns."""
    try:
        token = creds.get("access_token", "")
        if not token:
            return 0

        url = (
            "https://graph.facebook.com/v19.0/me/adaccounts"
            "?fields=id,name,campaigns{id,name,status,objective,daily_budget,"
            "insights{spend,impressions,clicks,actions,action_values,ctr,cpc}}"
            f"&access_token={token}"
        )
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        count = 0
        accounts = payload.get("data", [])
        for account in accounts:
            campaigns_data = account.get("campaigns", {}).get("data", [])
            for camp in campaigns_data:
                ext_id = camp.get("id", "")
                if not ext_id:
                    continue

                insights_list = camp.get("insights", {}).get("data", [{}])
                ins = insights_list[0] if insights_list else {}

                spend = float(ins.get("spend", 0) or 0)
                impressions = int(ins.get("impressions", 0) or 0)
                clicks = int(ins.get("clicks", 0) or 0)
                ctr = float(ins.get("ctr", 0) or 0)
                cpc = float(ins.get("cpc", 0) or 0)

                # Conversions from actions
                conversions = 0
                revenue = 0.0
                for action in ins.get("actions", []):
                    if action.get("action_type") in ("purchase", "offsite_conversion.fb_pixel_purchase"):
                        conversions += int(action.get("value", 0) or 0)
                for av in ins.get("action_values", []):
                    if av.get("action_type") in ("purchase", "offsite_conversion.fb_pixel_purchase"):
                        revenue += float(av.get("value", 0) or 0)

                cpa = (spend / conversions) if conversions > 0 else 0.0
                roas = (revenue / spend) if spend > 0 else 0.0

                budget_daily_raw = camp.get("daily_budget")
                budget_daily = float(budget_daily_raw) / 100.0 if budget_daily_raw else None

                campaign_id = f"meta_{ext_id}"
                _upsert_campaign(db, campaign_id, "meta", ext_id, {
                    "name": camp.get("name"),
                    "status": camp.get("status"),
                    "objective": camp.get("objective"),
                    "budget_daily": budget_daily,
                    "spend": spend,
                    "impressions": impressions,
                    "clicks": clicks,
                    "conversions": conversions,
                    "revenue": revenue,
                    "ctr": ctr,
                    "cpc": cpc,
                    "cpa": cpa,
                    "roas": roas,
                })
                count += 1

        db.commit()
        return count
    except Exception:
        db.rollback()
        return 0


def _sync_google_campaigns(creds: dict, db: Session) -> int:
    """Fetch campaigns from Google Ads API and upsert into ads_campaigns."""
    try:
        access_token = creds.get("access_token", "")
        developer_token = creds.get("developer_token", "")
        customer_id = creds.get("customer_id", "")
        if not access_token or not customer_id:
            return 0

        clean_customer_id = customer_id.replace("-", "")
        url = f"https://googleads.googleapis.com/v14/customers/{clean_customer_id}/googleAds:search"
        query = (
            "SELECT campaign.id, campaign.name, campaign.status, "
            "metrics.cost_micros, metrics.impressions, metrics.clicks, metrics.conversions "
            "FROM campaign WHERE segments.date DURING LAST_30_DAYS"
        )
        headers = {
            "Authorization": f"Bearer {access_token}",
            "developer-token": developer_token,
            "Content-Type": "application/json",
        }
        resp = requests.post(url, json={"query": query}, headers=headers, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        count = 0
        for row in payload.get("results", []):
            camp = row.get("campaign", {})
            metrics = row.get("metrics", {})
            ext_id = str(camp.get("id", ""))
            if not ext_id:
                continue

            cost_micros = int(metrics.get("costMicros", 0) or 0)
            spend = cost_micros / 1_000_000.0
            impressions = int(metrics.get("impressions", 0) or 0)
            clicks = int(metrics.get("clicks", 0) or 0)
            conversions = int(float(metrics.get("conversions", 0) or 0))

            ctr = (clicks / impressions) if impressions > 0 else 0.0
            cpc = (spend / clicks) if clicks > 0 else 0.0
            cpa = (spend / conversions) if conversions > 0 else 0.0

            status_raw = camp.get("status", "UNKNOWN")
            campaign_id = f"google_{ext_id}"
            _upsert_campaign(db, campaign_id, "google", ext_id, {
                "name": camp.get("name"),
                "status": status_raw,
                "spend": spend,
                "impressions": impressions,
                "clicks": clicks,
                "conversions": conversions,
                "ctr": ctr,
                "cpc": cpc,
                "cpa": cpa,
            })
            count += 1

        db.commit()
        return count
    except Exception:
        db.rollback()
        return 0


def _sync_tiktok_campaigns(creds: dict, db: Session) -> int:
    """Fetch campaigns from TikTok Business API and upsert into ads_campaigns."""
    try:
        access_token = creds.get("access_token", "")
        advertiser_id = creds.get("advertiser_id") or (
            creds.get("advertiser_ids", [None])[0] if creds.get("advertiser_ids") else None
        )
        if not access_token or not advertiser_id:
            return 0

        url = "https://business-api.tiktok.com/open_api/v1.3/campaign/get/"
        headers = {"Access-Token": access_token}
        params = {"advertiser_id": advertiser_id, "page_size": 100}
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        count = 0
        campaigns_list = payload.get("data", {}).get("list", [])
        for camp in campaigns_list:
            ext_id = str(camp.get("campaign_id", ""))
            if not ext_id:
                continue

            budget_raw = camp.get("budget", 0)
            budget_daily = float(budget_raw) if budget_raw else None

            campaign_id = f"tiktok_{ext_id}"
            _upsert_campaign(db, campaign_id, "tiktok", ext_id, {
                "name": camp.get("campaign_name"),
                "status": camp.get("primary_status", camp.get("operation_status")),
                "objective": camp.get("objective_type"),
                "budget_daily": budget_daily,
            })
            count += 1

        db.commit()
        return count
    except Exception:
        db.rollback()
        return 0


# ── Meta CAPI ─────────────────────────────────────────────────────────────────

def _fire_meta_capi_event(
    event_name: str,
    value: float,
    currency: str,
    order_id: str,
    phone_hash: str | None,
    db: Session,
) -> None:
    """Send a server-side Conversions API event to Meta. Never raises."""
    try:
        creds = _get_creds("meta_ads", db)
        if not creds:
            return

        token = creds.get("access_token", "")
        pixel_id = creds.get("pixel_id", "")
        if not token or not pixel_id:
            return

        user_data: dict = {}
        if phone_hash:
            user_data["ph"] = [phone_hash]

        payload = {
            "data": [
                {
                    "event_name": event_name,
                    "event_time": int(datetime.now(timezone.utc).timestamp()),
                    "action_source": "website",
                    "user_data": user_data,
                    "custom_data": {
                        "value": value,
                        "currency": currency,
                        "order_id": order_id,
                    },
                }
            ]
        }

        requests.post(
            f"https://graph.facebook.com/v19.0/{pixel_id}/events",
            params={"access_token": token},
            json=payload,
            timeout=10,
        )
    except Exception:
        pass  # Never propagate — CAPI is best-effort


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class PlatformSettings(BaseModel):
    app_id: Optional[str] = None
    app_secret: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    developer_token: Optional[str] = None
    customer_id: Optional[str] = None
    pixel_id: Optional[str] = None
    ad_account_id: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    advertiser_id: Optional[str] = None


class OAuthCallbackBody(BaseModel):
    code: str
    state: str
    redirect_uri: str
    platform: str


class CapiEventBody(BaseModel):
    event_name: str
    value: float
    currency: str = "BRL"
    order_id: str
    phone: Optional[str] = None


# ── Router ────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/ads", tags=["ads-oauth"])

_SUPPORTED_PLATFORMS = {"meta", "google", "tiktok"}
_PLATFORM_KEY_MAP = {
    "meta": "meta_ads",
    "google": "google_ads",
    "tiktok": "tiktok_ads",
}


def _resolve_platform_key(platform: str) -> str:
    """Map short platform name to integration_connections integration_type key."""
    return _PLATFORM_KEY_MAP.get(platform, platform)


# ── Routes: OAuth ─────────────────────────────────────────────────────────────

@router.get("/{platform}/connect-url")
def get_connect_url(
    platform: str,
    redirect_uri: str = Query(...),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Generate OAuth authorization URL for the given platform."""
    if platform not in _SUPPORTED_PLATFORMS:
        return err_msg(f"Plataforma '{platform}' não suportada. Use: meta, google ou tiktok.")

    creds = _get_creds(_resolve_platform_key(platform), db)
    if not creds:
        return err_msg("Configure as credenciais da plataforma primeiro.", status_code=400)

    state_id = str(uuid.uuid4())
    state_row = AdsOAuthState(
        id=state_id,
        platform=platform,
        redirect_uri=redirect_uri,
    )
    db.add(state_row)
    db.commit()

    try:
        if platform == "meta":
            app_id = creds.get("app_id") or creds.get("client_id", "")
            if not app_id:
                return err_msg("Configure as credenciais da plataforma primeiro.", status_code=400)
            auth_url = _build_meta_auth_url(app_id, redirect_uri, state_id)

        elif platform == "google":
            client_id = creds.get("client_id", "")
            if not client_id:
                return err_msg("Configure as credenciais da plataforma primeiro.", status_code=400)
            auth_url = _build_google_auth_url(client_id, redirect_uri, state_id)

        else:  # tiktok
            app_id = creds.get("app_id") or creds.get("client_id", "")
            if not app_id:
                return err_msg("Configure as credenciais da plataforma primeiro.", status_code=400)
            auth_url = _build_tiktok_auth_url(app_id, redirect_uri, state_id)

    except Exception as exc:
        return err_msg(f"Erro ao gerar URL de autorização: {exc}", status_code=500)

    return ok({"url": auth_url, "state": state_id})


@router.post("/oauth/callback")
def oauth_callback(
    body: OAuthCallbackBody,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Exchange OAuth authorization code for tokens and persist credentials."""
    platform = body.platform
    if platform not in _SUPPORTED_PLATFORMS:
        return err_msg(f"Plataforma '{platform}' não suportada.", status_code=400)

    # Validate CSRF state
    state_row = db.query(AdsOAuthState).filter(AdsOAuthState.id == body.state).first()
    if not state_row:
        return err_msg("Estado OAuth inválido ou expirado.", status_code=400)

    creds = _get_creds(_resolve_platform_key(platform), db) or {}

    try:
        if platform == "meta":
            app_id = creds.get("app_id") or creds.get("client_id", "")
            app_secret = creds.get("app_secret") or creds.get("client_secret", "")
            token_data = _exchange_meta_token(body.code, app_id, app_secret, body.redirect_uri)
            creds.update({
                "access_token": token_data.get("access_token"),
                "token_type": token_data.get("token_type"),
                "expires_in": token_data.get("expires_in"),
            })

        elif platform == "google":
            client_id = creds.get("client_id", "")
            client_secret = creds.get("client_secret", "")
            token_data = _exchange_google_token(body.code, client_id, client_secret, body.redirect_uri)
            creds.update({
                "access_token": token_data.get("access_token"),
                "refresh_token": token_data.get("refresh_token"),
                "expires_in": token_data.get("expires_in"),
            })

        else:  # tiktok
            app_id = creds.get("app_id") or creds.get("client_id", "")
            app_secret = creds.get("app_secret") or creds.get("client_secret", "")
            token_data = _exchange_tiktok_token(body.code, app_id, app_secret)
            creds.update({
                "access_token": token_data.get("access_token"),
                "advertiser_ids": token_data.get("advertiser_ids", []),
            })

    except Exception as exc:
        return err_msg(f"Falha ao trocar código por token: {exc}", status_code=502)

    _save_creds(_resolve_platform_key(platform), creds, db)

    # Clean up used state
    try:
        db.delete(state_row)
        db.commit()
    except Exception:
        db.rollback()

    return ok({"connected": True, "platform": platform})


# ── Routes: Campaigns & Insights ──────────────────────────────────────────────

@router.get("/campaigns")
def list_campaigns(
    platform: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """List all synced campaigns, optionally filtered by platform, ordered by spend DESC."""
    query = db.query(AdsCampaign)
    if platform:
        query = query.filter(AdsCampaign.platform == platform)
    campaigns = query.order_by(AdsCampaign.spend.desc()).all()

    result = [
        {
            "id": c.id,
            "platform": c.platform,
            "external_id": c.external_id,
            "name": c.name,
            "status": c.status,
            "objective": c.objective,
            "budget_daily": c.budget_daily,
            "spend": c.spend,
            "impressions": c.impressions,
            "clicks": c.clicks,
            "conversions": c.conversions,
            "revenue": c.revenue,
            "ctr": c.ctr,
            "cpc": c.cpc,
            "cpa": c.cpa,
            "roas": c.roas,
            "last_synced_at": c.last_synced_at.isoformat() if c.last_synced_at else None,
        }
        for c in campaigns
    ]
    return ok(result)


@router.get("/insights")
def get_insights(
    period: str = Query(default="7d"),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Aggregate campaign metrics by platform and overall totals."""
    campaigns = db.query(AdsCampaign).all()

    by_platform: dict[str, dict] = {}
    totals = {
        "total_spend": 0.0,
        "total_impressions": 0,
        "total_clicks": 0,
        "total_conversions": 0,
        "total_revenue": 0.0,
    }

    for c in campaigns:
        p = c.platform
        if p not in by_platform:
            by_platform[p] = {
                "platform": p,
                "total_spend": 0.0,
                "total_impressions": 0,
                "total_clicks": 0,
                "total_conversions": 0,
                "total_revenue": 0.0,
                "avg_roas": 0.0,
                "campaign_count": 0,
            }
        by_platform[p]["total_spend"] += c.spend or 0.0
        by_platform[p]["total_impressions"] += c.impressions or 0
        by_platform[p]["total_clicks"] += c.clicks or 0
        by_platform[p]["total_conversions"] += c.conversions or 0
        by_platform[p]["total_revenue"] += c.revenue or 0.0
        by_platform[p]["campaign_count"] += 1

        totals["total_spend"] += c.spend or 0.0
        totals["total_impressions"] += c.impressions or 0
        totals["total_clicks"] += c.clicks or 0
        totals["total_conversions"] += c.conversions or 0
        totals["total_revenue"] += c.revenue or 0.0

    # Compute avg_roas per platform
    for p_data in by_platform.values():
        spend = p_data["total_spend"]
        revenue = p_data["total_revenue"]
        p_data["avg_roas"] = round(revenue / spend, 4) if spend > 0 else 0.0

    avg_roas_global = (
        round(totals["total_revenue"] / totals["total_spend"], 4)
        if totals["total_spend"] > 0 else 0.0
    )

    return ok({
        "period": period,
        "by_platform": list(by_platform.values()),
        "totals": {**totals, "avg_roas": avg_roas_global},
    })


# ── Routes: Sync ──────────────────────────────────────────────────────────────

@router.post("/{platform}/sync")
def sync_platform(
    platform: str,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Sync campaigns from a single platform."""
    if platform not in _SUPPORTED_PLATFORMS:
        return err_msg(f"Plataforma '{platform}' não suportada.", status_code=400)

    creds = _get_creds(_resolve_platform_key(platform), db)
    if not creds:
        return err_msg("Plataforma não configurada.", status_code=400)

    if platform == "meta":
        synced = _sync_meta_campaigns(creds, db)
    elif platform == "google":
        synced = _sync_google_campaigns(creds, db)
    else:
        synced = _sync_tiktok_campaigns(creds, db)

    return ok({"synced": synced, "platform": platform})


@router.post("/sync-all")
def sync_all(
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Sync campaigns from all platforms. Failures per platform are isolated."""
    results: dict[str, int] = {}

    for platform in ("meta", "google", "tiktok"):
        try:
            creds = _get_creds(_resolve_platform_key(platform), db)
            if not creds:
                results[platform] = 0
                continue
            if platform == "meta":
                results[platform] = _sync_meta_campaigns(creds, db)
            elif platform == "google":
                results[platform] = _sync_google_campaigns(creds, db)
            else:
                results[platform] = _sync_tiktok_campaigns(creds, db)
        except Exception:
            results[platform] = 0

    return ok(results)


# ── Routes: Status ────────────────────────────────────────────────────────────

@router.get("/{platform}/status")
def platform_status(
    platform: str,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Return connection status and token expiry info for a platform."""
    if platform not in _SUPPORTED_PLATFORMS:
        return err_msg(f"Plataforma '{platform}' não suportada.", status_code=400)

    creds = _get_creds(_resolve_platform_key(platform), db)
    connected = bool(creds and creds.get("access_token"))

    token_expires_at = None
    if creds and creds.get("expires_in"):
        try:
            # expires_in is seconds from token issuance — best-effort, no issuance time stored
            token_expires_at = creds.get("expires_in")
        except Exception:
            pass

    return ok({
        "platform": platform,
        "connected": connected,
        "token_expires_at": token_expires_at,
        "has_refresh_token": bool(creds and creds.get("refresh_token")) if creds else False,
    })


# ── Routes: Meta CAPI ─────────────────────────────────────────────────────────

@router.post("/meta/capi-event")
def fire_capi_event(
    body: CapiEventBody,
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    """Manually fire a Meta Conversions API event."""
    phone_hash: Optional[str] = None
    if body.phone:
        clean = "".join(c for c in body.phone if c.isdigit())
        phone_hash = hashlib.sha256(clean.encode()).hexdigest()

    _fire_meta_capi_event(
        event_name=body.event_name,
        value=body.value,
        currency=body.currency,
        order_id=body.order_id,
        phone_hash=phone_hash,
        db=db,
    )
    return ok({"fired": True})


# ── Routes: UTM Links ─────────────────────────────────────────────────────────

@router.get("/utms")
def list_utms(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    utms = db.query(AdsUtmLink).order_by(AdsUtmLink.created_at.desc()).all()
    return ok([{
        "id": u.id, "name": u.name, "url": u.url,
        "utm_source": u.utm_source, "utm_medium": u.utm_medium,
        "utm_campaign": u.utm_campaign, "utm_term": u.utm_term,
        "utm_content": u.utm_content, "clicks": u.clicks or 0,
        "conversions": u.conversions or 0,
        "created_at": u.created_at.isoformat(),
    } for u in utms])


@router.post("/utms")
def create_utm(body: UtmLinkCreate, db: Session = Depends(get_db),
               _=Depends(get_current_admin)):
    u = AdsUtmLink(
        id=str(uuid.uuid4()), name=body.name, url=body.url,
        utm_source=body.utm_source, utm_medium=body.utm_medium,
        utm_campaign=body.utm_campaign, utm_term=body.utm_term,
        utm_content=body.utm_content,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return created({"id": u.id, "name": u.name}, "Link UTM criado.")


@router.delete("/utms/{utm_id}")
def delete_utm(utm_id: str, db: Session = Depends(get_db),
               _=Depends(get_current_admin)):
    u = db.query(AdsUtmLink).filter(AdsUtmLink.id == utm_id).first()
    if not u:
        from fastapi import HTTPException
        raise HTTPException(404, "Link UTM não encontrado.")
    db.delete(u)
    db.commit()
    return ok(None, "Link UTM excluído.")


# ── Routes: Leads ─────────────────────────────────────────────────────────────

@router.get("/leads")
def list_leads(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    rows = db.execute(text("""
        SELECT
            c.id, c.name AS customer_name, c.phone, c.email,
            COALESCE(c.source, 'Desconhecida') AS source,
            c.utm_source, c.utm_campaign,
            NULL AS pipeline_stage,
            NULL AS value,
            c.created_at
        FROM customers c
        WHERE c.utm_source IS NOT NULL OR c.source IS NOT NULL
        ORDER BY c.created_at DESC
        LIMIT 200
    """)).fetchall()
    return ok([{
        "id": r[0], "customer_name": r[1], "phone": r[2], "email": r[3],
        "source": r[4], "utm_source": r[5], "utm_campaign": r[6],
        "pipeline_stage": r[7], "value": r[8],
        "created_at": r[9].isoformat() if r[9] else None,
    } for r in rows])


# ── Routes: Pixels ────────────────────────────────────────────────────────────

@router.get("/pixels")
def list_pixels(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    pixels = db.query(AdsPixel).order_by(AdsPixel.created_at.desc()).all()
    return ok([{
        "id": p.id, "platform": p.platform, "pixel_id": p.pixel_id,
        "enabled": p.enabled, "events_tracked": p.events_tracked,
        "created_at": p.created_at.isoformat(),
    } for p in pixels])


@router.post("/pixels")
def create_pixel(body: PixelCreate, db: Session = Depends(get_db),
                 _=Depends(get_current_admin)):
    p = AdsPixel(
        id=str(uuid.uuid4()), platform=body.platform,
        pixel_id=body.pixel_id, events_tracked=body.events_tracked,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return created({"id": p.id, "platform": p.platform, "pixel_id": p.pixel_id}, "Pixel salvo.")


@router.patch("/pixels/{pixel_id}")
def update_pixel(pixel_id: str, body: PixelUpdate,
                 db: Session = Depends(get_db), _=Depends(get_current_admin)):
    from fastapi import HTTPException
    p = db.query(AdsPixel).filter(AdsPixel.id == pixel_id).first()
    if not p:
        raise HTTPException(404, "Pixel não encontrado.")
    if body.enabled is not None:        p.enabled = body.enabled
    if body.events_tracked is not None: p.events_tracked = body.events_tracked
    if body.pixel_id is not None:       p.pixel_id = body.pixel_id
    p.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ok({"id": p.id, "enabled": p.enabled})


@router.delete("/pixels/{pixel_id}")
def delete_pixel(pixel_id: str, db: Session = Depends(get_db),
                 _=Depends(get_current_admin)):
    from fastapi import HTTPException
    p = db.query(AdsPixel).filter(AdsPixel.id == pixel_id).first()
    if not p:
        raise HTTPException(404, "Pixel não encontrado.")
    db.delete(p)
    db.commit()
    return ok(None, "Pixel removido.")


# ── Routes: ROI ───────────────────────────────────────────────────────────────

@router.get("/roi")
def get_roi(period: str = "30d", db: Session = Depends(get_db),
            _=Depends(get_current_admin)):
    from datetime import timedelta
    period_days = {"7d": 7, "30d": 30, "90d": 90}
    days = period_days.get(period, 30)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # Per-platform aggregation from ads_campaigns
    rows = db.execute(text("""
        SELECT
            platform,
            SUM(spend) AS spend,
            SUM(revenue) AS revenue,
            SUM(conversions) AS orders,
            SUM(clicks) AS leads
        FROM ads_campaigns
        GROUP BY platform
    """)).fetchall()

    # Orders & revenue attributed via utm_medium for last N days
    utm_rows = db.execute(text("""
        SELECT utm_medium, COUNT(*), COALESCE(SUM(total), 0)
        FROM orders
        WHERE utm_medium IS NOT NULL AND created_at >= :since
        GROUP BY utm_medium
    """), {"since": since}).fetchall()
    utm_map = {r[0]: {"orders": r[1], "revenue": float(r[2])} for r in utm_rows}

    result = []
    for r in rows:
        platform = r[0]
        spend = float(r[1] or 0)
        revenue = float(r[2] or 0)
        orders = int(r[3] or 0)
        leads = int(r[4] or 0)

        # Supplement with real order data if platform name matches utm_medium
        if platform in utm_map:
            orders = utm_map[platform]["orders"]
            revenue = utm_map[platform]["revenue"]

        roas = revenue / spend if spend > 0 else 0
        roi_pct = ((revenue - spend) / spend * 100) if spend > 0 else 0
        cpl = spend / leads if leads > 0 else 0
        cpo = spend / orders if orders > 0 else 0

        result.append({
            "period": period, "platform": platform,
            "spend": spend, "revenue": revenue,
            "roas": round(roas, 2), "roi_pct": round(roi_pct, 2),
            "leads": leads, "orders": orders,
            "cpl": round(cpl, 2), "cpo": round(cpo, 2),
        })

    return ok(result)

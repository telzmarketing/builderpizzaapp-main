"""WhatsApp Marketing — templates, campanhas, disparo, monitoramento, config."""
from __future__ import annotations
import json
import random
import time
import uuid
import requests
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey, Integer, Float, text
from sqlalchemy.orm import Session

from backend.database import get_db, Base
from backend.routes.admin_auth import get_current_admin
from backend.core.response import ok, created, err_msg

router = APIRouter(prefix="/whatsapp", tags=["whatsapp-marketing"])


# ── ORM Models ────────────────────────────────────────────────────────────────

class WhatsAppTemplate(Base):
    __tablename__ = "whatsapp_templates"
    id = Column(String, primary_key=True)
    name = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    category = Column(String(50), default="marketing")
    language = Column(String(10), default="pt_BR")
    provider = Column(String(30), default="official")
    media_type = Column(String(20), nullable=True)
    media_url = Column(Text, nullable=True)
    caption = Column(Text, nullable=True)
    mimetype = Column(String(120), nullable=True)
    file_name = Column(String(255), nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class WhatsAppContactList(Base):
    __tablename__ = "whatsapp_contact_lists"
    id = Column(String, primary_key=True)
    name = Column(String(200), nullable=False)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class WhatsAppContactListItem(Base):
    __tablename__ = "whatsapp_contact_list_items"
    id = Column(String, primary_key=True)
    list_id = Column(String, ForeignKey("whatsapp_contact_lists.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    phone = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"
    id = Column(String, primary_key=True)
    template_id = Column(String, ForeignKey("whatsapp_templates.id", ondelete="SET NULL"), nullable=True)
    campaign_id = Column(String, ForeignKey("whatsapp_campaigns.id", ondelete="SET NULL"), nullable=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    phone = Column(String(20), nullable=False)
    recipient_name = Column(String(200), nullable=True)
    body_sent = Column(Text)
    provider = Column(String(30), default="official")
    message_type = Column(String(30), default="text")
    media_type = Column(String(20), nullable=True)
    media_url = Column(Text, nullable=True)
    caption = Column(Text, nullable=True)
    status = Column(String(20), default="pending")
    wamid = Column(String(200))
    error = Column(Text)
    sent_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class WhatsAppCampaign(Base):
    __tablename__ = "whatsapp_campaigns"
    id = Column(String, primary_key=True)
    name = Column(String(300), nullable=False)
    status = Column(String(30), default="draft")
    template_id = Column(String, ForeignKey("whatsapp_templates.id", ondelete="SET NULL"), nullable=True)
    group_id = Column(String, nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    sent_count = Column(Integer, default=0)
    delivered_count = Column(Integer, default=0)
    read_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class WhatsAppConfig(Base):
    __tablename__ = "whatsapp_config"
    id = Column(String, primary_key=True, default="default")
    connection_type = Column(String(30), default="official")
    status = Column(String(20), default="disconnected")
    messages_per_minute = Column(Integer, default=10)
    interval_seconds = Column(Integer, default=3)
    interval_min_seconds = Column(Integer, default=3)
    interval_max_seconds = Column(Integer, default=8)
    daily_limit = Column(Integer, default=1000)
    webhook_url = Column(String(500), default="")
    evolution_base_url = Column(String(500), default="")
    evolution_api_key = Column(Text, default="")
    evolution_instance = Column(String(120), default="")
    uazapi_base_url = Column(String(500), default="")
    uazapi_token = Column(Text, default="")
    uazapi_instance = Column(String(120), default="")
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TemplateCreate(BaseModel):
    name: str
    body: str
    category: str = "marketing"
    language: str = "pt_BR"
    provider: str = "official"
    media_type: Optional[str] = None
    media_url: Optional[str] = None
    caption: Optional[str] = None
    mimetype: Optional[str] = None
    file_name: Optional[str] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    body: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None
    provider: Optional[str] = None
    media_type: Optional[str] = None
    media_url: Optional[str] = None
    caption: Optional[str] = None
    mimetype: Optional[str] = None
    file_name: Optional[str] = None
    active: Optional[bool] = None


class ContactListItemPayload(BaseModel):
    name: str
    phone: str


class ContactListCreate(BaseModel):
    name: str
    contacts: list[ContactListItemPayload] = []


class ContactListUpdate(BaseModel):
    name: Optional[str] = None
    contacts: Optional[list[ContactListItemPayload]] = None


class SendRequest(BaseModel):
    provider: Optional[str] = None
    # Modo template (antigo)
    template_id: Optional[str] = None
    customer_ids: list[str] = []
    group_id: Optional[str] = None
    contact_list_id: Optional[str] = None
    variables: list[str] = []
    # Modo texto livre
    free_text: Optional[str] = None
    # Telefones diretos (novo)
    phones: list[str] = []
    # Midia para WABA e APIs nao oficiais
    media_type: Optional[str] = None
    media_url: Optional[str] = None
    caption: Optional[str] = None
    mimetype: Optional[str] = None
    file_name: Optional[str] = None
    # Agendamento
    scheduled_at: Optional[str] = None


class CampaignCreate(BaseModel):
    name: str
    template_id: Optional[str] = None
    group_id: Optional[str] = None
    scheduled_at: Optional[str] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    template_id: Optional[str] = None
    group_id: Optional[str] = None
    scheduled_at: Optional[str] = None


class ConfigUpdate(BaseModel):
    connection_type: Optional[str] = None
    messages_per_minute: Optional[int] = None
    interval_seconds: Optional[int] = None
    interval_min_seconds: Optional[int] = None
    interval_max_seconds: Optional[int] = None
    daily_limit: Optional[int] = None
    webhook_url: Optional[str] = None
    evolution_base_url: Optional[str] = None
    evolution_api_key: Optional[str] = None
    evolution_instance: Optional[str] = None
    uazapi_base_url: Optional[str] = None
    uazapi_token: Optional[str] = None
    uazapi_instance: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _append_recipient(result: list[dict], seen: set[str], phone: str, *, customer_id: str | None = None, name: str | None = None) -> None:
    clean_phone = (phone or "").strip()
    if not clean_phone:
        return
    dedupe_key = "".join(c for c in clean_phone if c.isdigit()) or clean_phone
    if dedupe_key in seen:
        return
    seen.add(dedupe_key)
    result.append({"phone": clean_phone, "customer_id": customer_id, "name": name})


def _resolve_phones(body: SendRequest, db: Session) -> list[dict]:
    """Resolve lista de {phone, customer_id} a partir das diferentes fontes."""
    result = []
    seen: set[str] = set()

    # Lista simples do disparador
    if body.contact_list_id:
        rows = db.execute(
            text("""
                SELECT i.name, i.phone
                FROM whatsapp_contact_list_items i
                JOIN whatsapp_contact_lists l ON l.id = i.list_id
                WHERE i.list_id = :list_id AND l.active = TRUE
                ORDER BY i.created_at ASC
            """),
            {"list_id": body.contact_list_id},
        ).fetchall()
        for row in rows:
            _append_recipient(result, seen, row[1], name=row[0])

    # Telefones diretos
    if body.phones:
        for ph in body.phones:
            ph = ph.strip()
            if not ph:
                continue
            # Tenta encontrar cliente pelo telefone
            row = db.execute(
                text("SELECT id, name FROM customers WHERE phone = :ph LIMIT 1"),
                {"ph": ph},
            ).fetchone()
            _append_recipient(result, seen, ph, customer_id=row[0] if row else None, name=row[1] if row else None)

    # Grupo de clientes
    if body.group_id:
        rows = db.execute(
            text(
                "SELECT c.id, c.phone FROM customers c "
                "JOIN customer_group_members cgm ON cgm.customer_id = c.id "
                "WHERE cgm.group_id = :gid AND c.phone IS NOT NULL"
            ),
            {"gid": body.group_id},
        ).fetchall()
        for row in rows:
            _append_recipient(result, seen, row[1], customer_id=row[0])

    # customer_ids explícitos
    if body.customer_ids:
        for cid in body.customer_ids:
            row = db.execute(
                text("SELECT id, phone FROM customers WHERE id = :cid AND phone IS NOT NULL"),
                {"cid": cid},
            ).fetchone()
            if row:
                _append_recipient(result, seen, row[1], customer_id=row[0])

    return result


def _get_config(db: Session) -> WhatsAppConfig:
    cfg = db.query(WhatsAppConfig).filter(WhatsAppConfig.id == "default").first()
    if not cfg:
        cfg = WhatsAppConfig(id="default")
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def _cfg_to_dict(cfg: WhatsAppConfig) -> dict:
    return {
        "connection_type": cfg.connection_type,
        "status": cfg.status,
        "messages_per_minute": cfg.messages_per_minute,
        "interval_seconds": cfg.interval_seconds,
        "interval_min_seconds": cfg.interval_min_seconds if cfg.interval_min_seconds is not None else cfg.interval_seconds,
        "interval_max_seconds": cfg.interval_max_seconds if cfg.interval_max_seconds is not None else cfg.interval_seconds,
        "daily_limit": cfg.daily_limit,
        "webhook_url": cfg.webhook_url or "",
        "evolution_base_url": cfg.evolution_base_url or "",
        "evolution_api_key": cfg.evolution_api_key or "",
        "evolution_instance": cfg.evolution_instance or "",
        "uazapi_base_url": cfg.uazapi_base_url or "",
        "uazapi_token": cfg.uazapi_token or "",
        "uazapi_instance": cfg.uazapi_instance or "",
    }


def _campaign_to_dict(c: WhatsAppCampaign) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "status": c.status,
        "template_id": c.template_id,
        "group_id": c.group_id,
        "scheduled_at": c.scheduled_at.isoformat() if c.scheduled_at else None,
        "sent_count": c.sent_count or 0,
        "delivered_count": c.delivered_count or 0,
        "read_count": c.read_count or 0,
        "error_count": c.error_count or 0,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _contact_list_to_dict(item: WhatsAppContactList, db: Session, *, include_contacts: bool = False) -> dict:
    count = db.execute(
        text("SELECT COUNT(*) FROM whatsapp_contact_list_items WHERE list_id = :list_id"),
        {"list_id": item.id},
    ).scalar() or 0
    payload = {
        "id": item.id,
        "name": item.name,
        "active": item.active,
        "contact_count": int(count),
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }
    if include_contacts:
        rows = db.execute(
            text("""
                SELECT id, name, phone
                FROM whatsapp_contact_list_items
                WHERE list_id = :list_id
                ORDER BY created_at ASC
            """),
            {"list_id": item.id},
        ).fetchall()
        payload["contacts"] = [{"id": r[0], "name": r[1], "phone": r[2]} for r in rows]
    return payload


def _render_contact_variables(text_value: Optional[str], recipient: dict) -> str:
    rendered = text_value or ""
    name = recipient.get("name") or ""
    phone = recipient.get("phone") or ""
    first_name = name.split(" ", 1)[0] if name else ""
    return (
        rendered
        .replace("{{nome}}", name)
        .replace("{{primeiro_nome}}", first_name)
        .replace("{{telefone}}", phone)
    )


def _load_whatsapp_cloud_credentials(db: Session) -> tuple[dict, Optional[str]]:
    conn = db.execute(
        text("SELECT credentials_json FROM integration_connections WHERE integration_type = 'whatsapp_cloud'")
    ).fetchone()
    if not conn or not conn[0]:
        return {}, "WhatsApp Cloud API nao configurado."
    try:
        creds = json.loads(conn[0])
    except Exception:
        return {}, "Credenciais WhatsApp invalidas."
    if not creds.get("phone_number_id") or not creds.get("access_token"):
        return {}, "Credenciais incompletas (phone_number_id / access_token)."
    return creds, None


def _normalize_provider(provider: Optional[str]) -> str:
    value = (provider or "official").strip().lower()
    if value in {"waba", "meta", "cloud", "whatsapp_cloud"}:
        return "official"
    if value in {"evolution", "evolution_api"}:
        return "evolution"
    if value in {"uazapi", "uazapi_api", "uazapigo"}:
        return "uazapi"
    if value in {"baileys", "whatsapp_gateway"}:
        return "baileys"
    if value == "qr":
        return "qr"
    return value


def _normalize_media_type(media_type: Optional[str], media_url: Optional[str]) -> Optional[str]:
    if not media_url:
        return None
    value = (media_type or "").strip().lower()
    if value in {"image", "video"}:
        return value
    lower_url = media_url.lower().split("?")[0]
    if lower_url.endswith((".mp4", ".mov", ".m4v", ".webm")):
        return "video"
    return "image"


def _guess_mimetype(media_type: Optional[str], media_url: Optional[str], mimetype: Optional[str]) -> str:
    if mimetype:
        return mimetype
    lower_url = (media_url or "").lower().split("?")[0]
    if lower_url.endswith(".png"):
        return "image/png"
    if lower_url.endswith(".webp"):
        return "image/webp"
    if lower_url.endswith(".mov"):
        return "video/quicktime"
    if lower_url.endswith(".webm"):
        return "video/webm"
    if media_type == "video":
        return "video/mp4"
    return "image/jpeg"


def _evolution_credentials(cfg: WhatsAppConfig) -> tuple[dict, Optional[str]]:
    base_url = (cfg.evolution_base_url or "").strip().rstrip("/")
    api_key = (cfg.evolution_api_key or "").strip()
    instance = (cfg.evolution_instance or "").strip()
    if not base_url or not api_key or not instance:
        return {}, "Evolution API incompleta. Informe URL base, API Key e instancia."
    return {"base_url": base_url, "api_key": api_key, "instance": instance}, None


def _uazapi_credentials(cfg: WhatsAppConfig) -> tuple[dict, Optional[str]]:
    base_url = (cfg.uazapi_base_url or "").strip().rstrip("/")
    token = (cfg.uazapi_token or "").strip()
    instance = (cfg.uazapi_instance or "").strip()
    if not base_url or not token:
        return {}, "Uazapi incompleta. Informe URL base e token da instancia."
    return {"base_url": base_url, "token": token, "instance": instance}, None


def _load_whatsapp_verify_token(db: Session) -> Optional[str]:
    conn = db.execute(
        text("SELECT credentials_json FROM integration_connections WHERE integration_type = 'whatsapp_cloud'")
    ).fetchone()
    if not conn or not conn[0]:
        return None
    try:
        creds = json.loads(conn[0])
    except Exception:
        return None
    return creds.get("verify_token") or creds.get("webhook_verify_token")


def _render_template_preview(template_body: str, variables: list[str]) -> str:
    rendered = template_body
    for i, val in enumerate(variables, start=1):
        rendered = rendered.replace(f"{{{{{i}}}}}", val)
    return rendered


def _send_whatsapp_api(
    phone: str,
    body: str,
    db: Session,
    *,
    template_name: str | None = None,
    template_language: str = "pt_BR",
    template_variables: list[str] | None = None,
    media_type: str | None = None,
    media_url: str | None = None,
    caption: str | None = None,
) -> tuple[Optional[str], str, Optional[str]]:
    """Envia via WhatsApp Cloud API. Retorna (wamid, status, error)."""
    creds, error = _load_whatsapp_cloud_credentials(db)
    if error:
        return None, "failed", error

    clean_phone = "".join(c for c in phone if c.isdigit())
    normalized_media = _normalize_media_type(media_type, media_url)
    if template_name:
        template: dict = {
            "name": template_name,
            "language": {"code": template_language or "pt_BR"},
        }
        components = []
        if media_url and normalized_media:
            components.append({
                "type": "header",
                "parameters": [{
                    "type": normalized_media,
                    normalized_media: {"link": media_url},
                }],
            })
        variables = template_variables or []
        if variables:
            components.append({
                "type": "body",
                "parameters": [{"type": "text", "text": str(value)} for value in variables],
            })
        if components:
            template["components"] = components
        payload = {
            "messaging_product": "whatsapp",
            "to": clean_phone,
            "type": "template",
            "template": template,
        }
    elif media_url and normalized_media:
        payload = {
            "messaging_product": "whatsapp",
            "to": clean_phone,
            "type": normalized_media,
            normalized_media: {
                "link": media_url,
                "caption": caption or body or "",
            },
        }
    else:
        payload = {
            "messaging_product": "whatsapp",
            "to": clean_phone,
            "type": "text",
            "text": {"body": body},
        }

    try:
        resp = requests.post(
            f"https://graph.facebook.com/v19.0/{creds['phone_number_id']}/messages",
            headers={"Authorization": f"Bearer {creds['access_token']}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        data = resp.json()
        if resp.status_code == 200 and "messages" in data:
            return data["messages"][0].get("id"), "sent", None
        return None, "failed", data.get("error", {}).get("message", resp.text)
    except Exception as exc:
        return None, "failed", str(exc)


def _send_evolution_api(
    phone: str,
    body: str,
    cfg: WhatsAppConfig,
    *,
    media_type: str | None = None,
    media_url: str | None = None,
    caption: str | None = None,
    mimetype: str | None = None,
    file_name: str | None = None,
) -> tuple[Optional[str], str, Optional[str]]:
    """Envia via Evolution API. Retorna (message_id, status, error)."""
    creds, error = _evolution_credentials(cfg)
    if error:
        return None, "failed", error

    clean_phone = "".join(c for c in phone if c.isdigit())
    normalized_media = _normalize_media_type(media_type, media_url)
    headers = {"apikey": creds["api_key"], "Content-Type": "application/json"}

    if media_url and normalized_media:
        endpoint = f"{creds['base_url']}/message/sendMedia/{creds['instance']}"
        payload = {
            "number": clean_phone,
            "mediatype": normalized_media,
            "mimetype": _guess_mimetype(normalized_media, media_url, mimetype),
            "caption": caption or body or "",
            "media": media_url,
            "fileName": file_name or ("video.mp4" if normalized_media == "video" else "imagem.jpg"),
        }
    else:
        endpoint = f"{creds['base_url']}/message/sendText/{creds['instance']}"
        payload = {
            "number": clean_phone,
            "text": body,
            "linkPreview": True,
        }

    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=20)
        data = resp.json() if resp.content else {}
        if 200 <= resp.status_code < 300:
            msg_id = (
                data.get("key", {}).get("id")
                or data.get("message", {}).get("key", {}).get("id")
                or data.get("id")
            )
            return msg_id, "sent", None
        message = data.get("message") or data.get("error") or resp.text
        return None, "failed", str(message)
    except Exception as exc:
        return None, "failed", str(exc)


def _send_uazapi_api(
    phone: str,
    body: str,
    cfg: WhatsAppConfig,
    *,
    media_type: str | None = None,
    media_url: str | None = None,
    caption: str | None = None,
    mimetype: str | None = None,
    file_name: str | None = None,
) -> tuple[Optional[str], str, Optional[str]]:
    """Envia via Uazapi. Retorna (message_id, status, error)."""
    creds, error = _uazapi_credentials(cfg)
    if error:
        return None, "failed", error

    clean_phone = "".join(c for c in phone if c.isdigit())
    normalized_media = _normalize_media_type(media_type, media_url)
    headers = {"token": creds["token"], "Content-Type": "application/json"}

    if media_url and normalized_media:
        endpoint = f"{creds['base_url']}/send/media"
        payload = {
            "number": clean_phone,
            "type": normalized_media,
            "file": media_url,
            "text": caption or body or "",
        }
        if mimetype:
            payload["mimetype"] = mimetype
        if file_name:
            payload["docName"] = file_name
    else:
        endpoint = f"{creds['base_url']}/send/text"
        payload = {
            "number": clean_phone,
            "text": body,
            "linkPreview": True,
        }

    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=20)
        data = resp.json() if resp.content else {}
        if 200 <= resp.status_code < 300:
            msg_id = (
                data.get("messageid")
                or data.get("id")
                or data.get("key", {}).get("id")
                or data.get("response", {}).get("messageid")
                or data.get("response", {}).get("id")
            )
            return msg_id, "sent", None
        message = data.get("message_ptbr") or data.get("message") or data.get("error") or resp.text
        return None, "failed", str(message)
    except Exception as exc:
        return None, "failed", str(exc)


def _sent_today_count(db: Session) -> int:
    row = db.execute(
        text("SELECT COUNT(*) FROM whatsapp_messages WHERE status = 'sent' AND sent_at::date = CURRENT_DATE")
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def _send_delay_seconds(cfg: WhatsAppConfig) -> float:
    fallback = max(0, int(cfg.interval_seconds or 0))
    min_seconds = cfg.interval_min_seconds if cfg.interval_min_seconds is not None else fallback
    max_seconds = cfg.interval_max_seconds if cfg.interval_max_seconds is not None else fallback
    min_seconds = max(0, int(min_seconds or 0))
    max_seconds = max(0, int(max_seconds or 0))
    if max_seconds < min_seconds:
        min_seconds, max_seconds = max_seconds, min_seconds
    by_interval = random.uniform(float(min_seconds), float(max_seconds)) if max_seconds > min_seconds else float(min_seconds)
    return by_interval


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    def _q(sql: str, params: dict = {}) -> int:  # noqa: B006
        try:
            row = db.execute(text(sql), params).fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        except Exception:
            return 0

    def _qf(sql: str, params: dict = {}) -> float:  # noqa: B006
        try:
            row = db.execute(text(sql), params).fetchone()
            return float(row[0]) if row and row[0] is not None else 0.0
        except Exception:
            return 0.0

    sent       = _q("SELECT COUNT(*) FROM whatsapp_messages WHERE status IN ('sent','delivered','read')")
    delivered  = _q("SELECT COUNT(*) FROM whatsapp_messages WHERE status IN ('delivered','read')")
    read_      = _q("SELECT COUNT(*) FROM whatsapp_messages WHERE status = 'read'")
    errors     = _q("SELECT COUNT(*) FROM whatsapp_messages WHERE status = 'failed'")
    active_c   = _q("SELECT COUNT(*) FROM whatsapp_campaigns WHERE status = 'running'")
    sched_c    = _q("SELECT COUNT(*) FROM whatsapp_campaigns WHERE status = 'draft' AND scheduled_at IS NOT NULL")

    # responded: heurística — mensagens marcadas como 'responded' (se existir) ou 0
    responded  = _q("SELECT COUNT(*) FROM whatsapp_messages WHERE status = 'responded'")
    response_rate = (responded / sent) if sent > 0 else 0.0

    # Pedidos com utm_medium = 'whatsapp' como proxy de pedidos gerados
    orders_gen = _q("SELECT COUNT(*) FROM orders WHERE utm_medium = 'whatsapp'")
    revenue_gen = _qf("SELECT COALESCE(SUM(total),0) FROM orders WHERE utm_medium = 'whatsapp'")

    return ok({
        "sent": sent,
        "delivered": delivered,
        "read": read_,
        "responded": responded,
        "errors": errors,
        "active_campaigns": active_c,
        "scheduled_campaigns": sched_c,
        "response_rate": round(response_rate, 4),
        "orders_generated": orders_gen,
        "revenue_generated": round(revenue_gen, 2),
    })


# ── Webhook oficial Meta ──────────────────────────────────────────────────────

@router.get("/webhook", include_in_schema=False)
def verify_meta_webhook(request: Request, db: Session = Depends(get_db)):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    expected = _load_whatsapp_verify_token(db)

    if mode == "subscribe" and expected and token == expected and challenge:
        return PlainTextResponse(challenge)
    return PlainTextResponse("Forbidden", status_code=403)


@router.post("/webhook", include_in_schema=False)
async def receive_meta_webhook(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
    except Exception:
        return err_msg("Payload de webhook invalido.", code="WhatsAppWebhookInvalid")

    updated = 0
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value") or {}
            for item in value.get("statuses", []) or []:
                wamid = item.get("id")
                status = item.get("status")
                if not wamid or not status:
                    continue
                errors = item.get("errors") or []
                error_message = None
                if errors:
                    first_error = errors[0] or {}
                    error_message = first_error.get("message") or first_error.get("title")
                result = db.execute(
                    text("""
                        UPDATE whatsapp_messages
                        SET status = :status,
                            error = :error,
                            sent_at = COALESCE(sent_at, CASE WHEN :status = 'sent' THEN NOW() ELSE sent_at END)
                        WHERE wamid = :wamid
                    """),
                    {"status": status, "error": error_message, "wamid": wamid},
                )
                updated += int(result.rowcount or 0)

    db.commit()
    return ok({"updated": updated})


# ── Templates ─────────────────────────────────────────────────────────────────

@router.get("/templates")
def list_templates(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    templates = (
        db.query(WhatsAppTemplate)
        .filter(WhatsAppTemplate.active == True)  # noqa: E712
        .order_by(WhatsAppTemplate.created_at.desc())
        .all()
    )
    return ok([{
        "id": t.id, "name": t.name, "body": t.body, "category": t.category,
        "language": t.language, "provider": t.provider or "official",
        "media_type": t.media_type, "media_url": t.media_url, "caption": t.caption,
        "mimetype": t.mimetype, "file_name": t.file_name, "active": t.active,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    } for t in templates])


@router.post("/templates")
def create_template(body: TemplateCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    t = WhatsAppTemplate(
        id=str(uuid.uuid4()),
        name=body.name,
        body=body.body,
        category=body.category,
        language=body.language,
        provider=_normalize_provider(body.provider),
        media_type=_normalize_media_type(body.media_type, body.media_url),
        media_url=(body.media_url or "").strip() or None,
        caption=(body.caption or "").strip() or None,
        mimetype=(body.mimetype or "").strip() or None,
        file_name=(body.file_name or "").strip() or None,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return created({"id": t.id, "name": t.name, "category": t.category}, "Template criado.")


@router.patch("/templates/{template_id}")
def update_template(template_id: str, body: TemplateUpdate,
                    db: Session = Depends(get_db), _=Depends(get_current_admin)):
    t = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.id == template_id).first()
    if not t:
        raise HTTPException(404, "Template não encontrado.")
    if body.name is not None:
        t.name = body.name
    if body.body is not None:
        t.body = body.body
    if body.category is not None:
        t.category = body.category
    if body.language is not None:
        t.language = body.language
    if body.provider is not None:
        t.provider = _normalize_provider(body.provider)
    if body.media_url is not None or body.media_type is not None:
        media_url = (body.media_url if body.media_url is not None else t.media_url) or ""
        t.media_url = media_url.strip() or None
        t.media_type = _normalize_media_type(body.media_type if body.media_type is not None else t.media_type, t.media_url)
    if body.caption is not None:
        t.caption = body.caption.strip() or None
    if body.mimetype is not None:
        t.mimetype = body.mimetype.strip() or None
    if body.file_name is not None:
        t.file_name = body.file_name.strip() or None
    if body.active is not None:
        t.active = body.active
    t.updated_at = _now()
    db.commit()
    return ok({"id": t.id, "name": t.name, "active": t.active})


@router.delete("/templates/{template_id}")
def delete_template(template_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    t = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.id == template_id).first()
    if not t:
        raise HTTPException(404, "Template não encontrado.")
    t.active = False
    t.updated_at = _now()
    db.commit()
    return ok(None, "Template desativado.")


# ── Campanhas ─────────────────────────────────────────────────────────────────

# ── Listas de contatos ───────────────────────────────────────────────────────

@router.get("/contact-lists")
def list_contact_lists(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    items = (
        db.query(WhatsAppContactList)
        .filter(WhatsAppContactList.active == True)  # noqa: E712
        .order_by(WhatsAppContactList.created_at.desc())
        .all()
    )
    return ok([_contact_list_to_dict(item, db) for item in items])


@router.get("/contact-lists/{list_id}")
def get_contact_list(list_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    item = db.query(WhatsAppContactList).filter(
        WhatsAppContactList.id == list_id,
        WhatsAppContactList.active == True,  # noqa: E712
    ).first()
    if not item:
        raise HTTPException(404, "Lista de contatos nao encontrada.")
    return ok(_contact_list_to_dict(item, db, include_contacts=True))


@router.post("/contact-lists")
def create_contact_list(body: ContactListCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    clean_contacts = [
        {"name": c.name.strip(), "phone": c.phone.strip()}
        for c in body.contacts
        if c.name.strip() and c.phone.strip()
    ]
    if not body.name.strip():
        raise HTTPException(400, "Informe o nome da lista.")
    if not clean_contacts:
        raise HTTPException(400, "Inclua pelo menos um contato com nome e telefone.")

    item = WhatsAppContactList(id=str(uuid.uuid4()), name=body.name.strip())
    db.add(item)
    db.flush()
    for contact in clean_contacts:
        db.add(WhatsAppContactListItem(
            id=str(uuid.uuid4()),
            list_id=item.id,
            name=contact["name"],
            phone=contact["phone"],
        ))
    db.commit()
    db.refresh(item)
    return created(_contact_list_to_dict(item, db, include_contacts=True), "Lista de contatos criada.")


@router.patch("/contact-lists/{list_id}")
def update_contact_list(list_id: str, body: ContactListUpdate,
                        db: Session = Depends(get_db), _=Depends(get_current_admin)):
    item = db.query(WhatsAppContactList).filter(WhatsAppContactList.id == list_id).first()
    if not item or not item.active:
        raise HTTPException(404, "Lista de contatos nao encontrada.")
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(400, "Informe o nome da lista.")
        item.name = body.name.strip()
    if body.contacts is not None:
        clean_contacts = [
            {"name": c.name.strip(), "phone": c.phone.strip()}
            for c in body.contacts
            if c.name.strip() and c.phone.strip()
        ]
        if not clean_contacts:
            raise HTTPException(400, "Inclua pelo menos um contato com nome e telefone.")
        db.execute(text("DELETE FROM whatsapp_contact_list_items WHERE list_id = :list_id"), {"list_id": list_id})
        for contact in clean_contacts:
            db.add(WhatsAppContactListItem(
                id=str(uuid.uuid4()),
                list_id=item.id,
                name=contact["name"],
                phone=contact["phone"],
            ))
    item.updated_at = _now()
    db.commit()
    return ok(_contact_list_to_dict(item, db, include_contacts=True))


@router.delete("/contact-lists/{list_id}")
def delete_contact_list(list_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    item = db.query(WhatsAppContactList).filter(WhatsAppContactList.id == list_id).first()
    if not item:
        raise HTTPException(404, "Lista de contatos nao encontrada.")
    item.active = False
    item.updated_at = _now()
    db.commit()
    return ok(None, "Lista de contatos desativada.")


@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    campaigns = db.query(WhatsAppCampaign).order_by(WhatsAppCampaign.created_at.desc()).all()
    return ok([_campaign_to_dict(c) for c in campaigns])


@router.post("/campaigns")
def create_campaign(body: CampaignCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    scheduled = None
    if body.scheduled_at:
        try:
            scheduled = datetime.fromisoformat(body.scheduled_at)
        except ValueError:
            raise HTTPException(400, "scheduled_at inválido (use ISO 8601).")

    c = WhatsAppCampaign(
        id=str(uuid.uuid4()),
        name=body.name,
        status="draft",
        template_id=body.template_id or None,
        group_id=body.group_id or None,
        scheduled_at=scheduled,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return created(_campaign_to_dict(c), "Campanha criada.")


@router.patch("/campaigns/{campaign_id}")
def update_campaign(campaign_id: str, body: CampaignUpdate,
                    db: Session = Depends(get_db), _=Depends(get_current_admin)):
    c = db.query(WhatsAppCampaign).filter(WhatsAppCampaign.id == campaign_id).first()
    if not c:
        raise HTTPException(404, "Campanha não encontrada.")
    if body.name is not None:
        c.name = body.name
    if body.status is not None:
        c.status = body.status
    if body.template_id is not None:
        c.template_id = body.template_id or None
    if body.group_id is not None:
        c.group_id = body.group_id or None
    if body.scheduled_at is not None:
        try:
            c.scheduled_at = datetime.fromisoformat(body.scheduled_at) if body.scheduled_at else None
        except ValueError:
            raise HTTPException(400, "scheduled_at inválido.")
    c.updated_at = _now()
    db.commit()
    return ok(_campaign_to_dict(c))


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    c = db.query(WhatsAppCampaign).filter(WhatsAppCampaign.id == campaign_id).first()
    if not c:
        raise HTTPException(404, "Campanha não encontrada.")
    db.delete(c)
    db.commit()
    return ok(None, "Campanha excluída.")


# ── Disparo ───────────────────────────────────────────────────────────────────

@router.post("/send")
def send_messages(body: SendRequest, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    cfg = _get_config(db)
    provider = _normalize_provider(body.provider or cfg.connection_type)
    if provider == "qr":
        return err_msg(
            "WhatsApp QR Code ainda nao possui servico de sessao implementado. Use WABA, Evolution API ou Uazapi.",
            code="WhatsAppQrNotImplemented",
            status_code=501,
        )
    if provider not in {"official", "evolution", "uazapi"}:
        return err_msg("Provedor WhatsApp invalido. Use official, evolution ou uazapi.", code="WhatsAppProviderInvalid")
    if provider == "official":
        _, cloud_error = _load_whatsapp_cloud_credentials(db)
        if cloud_error:
            return err_msg(cloud_error, code="WhatsAppConfigMissing")
    if provider == "evolution":
        _, evolution_error = _evolution_credentials(cfg)
        if evolution_error:
            return err_msg(evolution_error, code="EvolutionConfigMissing")
    if provider == "uazapi":
        _, uazapi_error = _uazapi_credentials(cfg)
        if uazapi_error:
            return err_msg(uazapi_error, code="UazapiConfigMissing")
    if body.scheduled_at:
        return err_msg("Agendamento ainda nao possui worker ativo. Faca disparo imediato por enquanto.", code="WhatsAppScheduleUnavailable")

    # Resolve o body final (template ou texto livre)
    template = None
    final_body_template: Optional[str] = None
    media_url = (body.media_url or "").strip() or None
    media_type = _normalize_media_type(body.media_type, media_url)
    caption = (body.caption or "").strip() or None
    mimetype = body.mimetype
    file_name = body.file_name

    if body.template_id:
        template = db.query(WhatsAppTemplate).filter(
            WhatsAppTemplate.id == body.template_id,
            WhatsAppTemplate.active == True,  # noqa: E712
        ).first()
        if not template:
            raise HTTPException(404, "Template não encontrado ou inativo.")
        final_body_template = _render_template_preview(template.body, body.variables)
        media_url = media_url or template.media_url
        media_type = _normalize_media_type(media_type or template.media_type, media_url)
        caption = caption or template.caption
        mimetype = mimetype or template.mimetype
        file_name = file_name or template.file_name

    elif not body.free_text and not media_url:
        raise HTTPException(400, "Informe template_id, free_text ou uma midia.")

    if media_url and media_type not in {"image", "video"}:
        raise HTTPException(400, "media_type deve ser image ou video.")

    # Resolve destinatários
    recipients = _resolve_phones(body, db)
    if not recipients:
        raise HTTPException(400, "Nenhum destinatário encontrado.")

    sent_today = _sent_today_count(db)
    if cfg.daily_limit and sent_today >= cfg.daily_limit:
        return err_msg("Limite diario de mensagens atingido.", code="WhatsAppDailyLimitReached")

    sent_count = failed_count = 0
    results = []

    for index, rec in enumerate(recipients):
        if cfg.daily_limit and sent_today + sent_count >= cfg.daily_limit:
            failed_count += 1
            results.append({"phone": rec["phone"], "status": "failed", "wamid": None, "error": "Limite diario atingido."})
            continue

        phone = rec["phone"]
        msg_body = _render_contact_variables(final_body_template if template else (body.free_text or ""), rec)
        msg_caption = _render_contact_variables(caption, rec) if caption else None
        recipient_variables = [_render_contact_variables(str(value), rec) for value in body.variables]
        message_type = "template" if template else (media_type or "text")

        msg = WhatsAppMessage(
            id=str(uuid.uuid4()),
            template_id=template.id if template else None,
            customer_id=rec.get("customer_id"),
            phone=phone,
            recipient_name=rec.get("name"),
            body_sent=msg_body,
            provider=provider,
            message_type=message_type,
            media_type=media_type,
            media_url=media_url,
            caption=msg_caption,
            status="pending",
        )
        db.add(msg)
        db.flush()

        if provider == "evolution":
            wamid, status, error = _send_evolution_api(
                phone,
                msg_body,
                cfg,
                media_type=media_type,
                media_url=media_url,
                caption=msg_caption,
                mimetype=mimetype,
                file_name=file_name,
            )
        elif provider == "uazapi":
            wamid, status, error = _send_uazapi_api(
                phone,
                msg_body,
                cfg,
                media_type=media_type,
                media_url=media_url,
                caption=msg_caption,
                mimetype=mimetype,
                file_name=file_name,
            )
        else:
            wamid, status, error = _send_whatsapp_api(
                phone,
                msg_body,
                db,
                template_name=template.name if template else None,
                template_language=template.language if template else "pt_BR",
                template_variables=recipient_variables if template else None,
                media_type=media_type,
                media_url=media_url,
                caption=msg_caption,
            )

        msg.status = status
        msg.wamid = wamid
        msg.error = error
        if status == "sent":
            msg.sent_at = _now()
            sent_count += 1
        else:
            failed_count += 1

        results.append({
            "phone": phone,
            "provider": provider,
            "message_type": message_type,
            "media_type": media_type,
            "status": status,
            "wamid": wamid,
            "error": error,
        })
        if index < len(recipients) - 1:
            delay_seconds = _send_delay_seconds(cfg)
            if delay_seconds > 0:
                time.sleep(delay_seconds)

    db.commit()
    return ok({"sent": sent_count, "failed": failed_count, "messages": results})


# ── Monitoramento ─────────────────────────────────────────────────────────────

@router.get("/messages")
def list_messages(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    rows = db.execute(text("""
        SELECT
            wm.id, wm.template_id, wm.customer_id,
            c.name  AS customer_name,
            wt.name AS template_name,
            wm.phone, COALESCE(c.name, wm.recipient_name) AS recipient_name,
            wm.body_sent, wm.status, wm.wamid, wm.error,
            wm.sent_at, wm.created_at,
            COALESCE(wm.provider, 'official') AS provider,
            COALESCE(wm.message_type, 'text') AS message_type,
            wm.media_type, wm.media_url, wm.caption
        FROM whatsapp_messages wm
        LEFT JOIN customers c ON c.id = wm.customer_id
        LEFT JOIN whatsapp_templates wt ON wt.id = wm.template_id
        ORDER BY wm.created_at DESC
        LIMIT 200
    """)).fetchall()

    return ok([{
        "id": r[0],
        "template_id": r[1],
        "customer_id": r[2],
        "customer_name": r[6] or r[3],
        "template_name": r[4],
        "phone": r[5],
        "recipient_name": r[6],
        "body_sent": r[7],
        "status": r[8],
        "wamid": r[9],
        "error": r[10],
        "sent_at": r[11].isoformat() if r[11] else None,
        "created_at": r[12].isoformat() if r[12] else None,
        "provider": r[13],
        "message_type": r[14],
        "media_type": r[15],
        "media_url": r[16],
        "caption": r[17],
    } for r in rows])


# ── Configurações ─────────────────────────────────────────────────────────────

@router.get("/config")
def get_config(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return ok(_cfg_to_dict(_get_config(db)))


@router.patch("/config")
def update_config(body: ConfigUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    cfg = _get_config(db)
    if body.connection_type is not None:
        cfg.connection_type = _normalize_provider(body.connection_type)
        if cfg.connection_type == "qr":
            cfg.status = "disconnected"
    if body.messages_per_minute is not None:
        cfg.messages_per_minute = body.messages_per_minute
    if body.interval_seconds is not None:
        cfg.interval_seconds = body.interval_seconds
        if body.interval_min_seconds is None:
            cfg.interval_min_seconds = body.interval_seconds
        if body.interval_max_seconds is None:
            cfg.interval_max_seconds = body.interval_seconds
    if body.interval_min_seconds is not None:
        cfg.interval_min_seconds = body.interval_min_seconds
    if body.interval_max_seconds is not None:
        cfg.interval_max_seconds = body.interval_max_seconds
    if cfg.interval_min_seconds is not None and cfg.interval_max_seconds is not None and cfg.interval_min_seconds > cfg.interval_max_seconds:
        cfg.interval_min_seconds, cfg.interval_max_seconds = cfg.interval_max_seconds, cfg.interval_min_seconds
    if body.daily_limit is not None:
        cfg.daily_limit = body.daily_limit
    if body.webhook_url is not None:
        cfg.webhook_url = body.webhook_url
    if body.evolution_base_url is not None:
        cfg.evolution_base_url = body.evolution_base_url.strip()
    if body.evolution_api_key is not None:
        cfg.evolution_api_key = body.evolution_api_key.strip()
    if body.evolution_instance is not None:
        cfg.evolution_instance = body.evolution_instance.strip()
    if body.uazapi_base_url is not None:
        cfg.uazapi_base_url = body.uazapi_base_url.strip().rstrip("/")
    if body.uazapi_token is not None:
        cfg.uazapi_token = body.uazapi_token.strip()
    if body.uazapi_instance is not None:
        cfg.uazapi_instance = body.uazapi_instance.strip()
    if cfg.connection_type == "evolution":
        cfg.status = "connected" if all([
            cfg.evolution_base_url,
            cfg.evolution_api_key,
            cfg.evolution_instance,
        ]) else "disconnected"
    elif cfg.connection_type == "uazapi":
        cfg.status = "connected" if all([
            cfg.uazapi_base_url,
            cfg.uazapi_token,
        ]) else "disconnected"
    elif body.connection_type is not None and cfg.connection_type == "official":
        _, cloud_error = _load_whatsapp_cloud_credentials(db)
        cfg.status = "disconnected" if cloud_error else "connected"
    cfg.updated_at = _now()
    db.commit()
    return ok(_cfg_to_dict(cfg))

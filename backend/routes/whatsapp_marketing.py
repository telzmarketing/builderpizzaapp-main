"""WhatsApp Marketing — templates, campanhas, disparo, monitoramento, config."""
from __future__ import annotations
import json
import uuid
import requests
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey, Integer, Float, text
from sqlalchemy.orm import Session

from backend.database import get_db, Base
from backend.routes.admin_auth import get_current_admin
from backend.core.response import ok, created

router = APIRouter(prefix="/whatsapp", tags=["whatsapp-marketing"])


# ── ORM Models ────────────────────────────────────────────────────────────────

class WhatsAppTemplate(Base):
    __tablename__ = "whatsapp_templates"
    id = Column(String, primary_key=True)
    name = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    category = Column(String(50), default="marketing")
    language = Column(String(10), default="pt_BR")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"
    id = Column(String, primary_key=True)
    template_id = Column(String, ForeignKey("whatsapp_templates.id", ondelete="SET NULL"), nullable=True)
    campaign_id = Column(String, ForeignKey("whatsapp_campaigns.id", ondelete="SET NULL"), nullable=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    phone = Column(String(20), nullable=False)
    body_sent = Column(Text)
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
    daily_limit = Column(Integer, default=1000)
    webhook_url = Column(String(500), default="")
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TemplateCreate(BaseModel):
    name: str
    body: str
    category: str = "marketing"
    language: str = "pt_BR"


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    body: Optional[str] = None
    category: Optional[str] = None
    active: Optional[bool] = None


class SendRequest(BaseModel):
    # Modo template (antigo)
    template_id: Optional[str] = None
    customer_ids: list[str] = []
    group_id: Optional[str] = None
    variables: list[str] = []
    # Modo texto livre
    free_text: Optional[str] = None
    # Telefones diretos (novo)
    phones: list[str] = []
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
    daily_limit: Optional[int] = None
    webhook_url: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _send_whatsapp_api(phone: str, body: str, db: Session) -> tuple[Optional[str], str, Optional[str]]:
    """Envia via WhatsApp Cloud API. Retorna (wamid, status, error)."""
    conn = db.execute(
        text("SELECT credentials_json FROM integration_connections WHERE integration_type = 'whatsapp_cloud'")
    ).fetchone()

    if not conn or not conn[0]:
        return None, "failed", "WhatsApp Cloud API não configurado."

    try:
        creds = json.loads(conn[0])
    except Exception:
        return None, "failed", "Credenciais WhatsApp inválidas."

    phone_number_id = creds.get("phone_number_id")
    access_token = creds.get("access_token")
    if not phone_number_id or not access_token:
        return None, "failed", "Credenciais incompletas (phone_number_id / access_token)."

    clean_phone = "".join(c for c in phone if c.isdigit())
    payload = {
        "messaging_product": "whatsapp",
        "to": clean_phone,
        "type": "text",
        "text": {"body": body},
    }
    try:
        resp = requests.post(
            f"https://graph.facebook.com/v19.0/{phone_number_id}/messages",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        data = resp.json()
        if resp.status_code == 200 and "messages" in data:
            return data["messages"][0].get("id"), "sent", None
        return None, "failed", data.get("error", {}).get("message", resp.text)
    except Exception as exc:
        return None, "failed", str(exc)


def _resolve_phones(body: SendRequest, db: Session) -> list[dict]:
    """Resolve lista de {phone, customer_id} a partir das diferentes fontes."""
    result = []

    # Telefones diretos (modo novo)
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
            result.append({"phone": ph, "customer_id": row[0] if row else None})
        return result

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
        return [{"phone": r[1], "customer_id": r[0]} for r in rows]

    # customer_ids explícitos
    if body.customer_ids:
        for cid in body.customer_ids:
            row = db.execute(
                text("SELECT id, phone FROM customers WHERE id = :cid AND phone IS NOT NULL"),
                {"cid": cid},
            ).fetchone()
            if row:
                result.append({"phone": row[1], "customer_id": row[0]})

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
        "daily_limit": cfg.daily_limit,
        "webhook_url": cfg.webhook_url or "",
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
        "language": t.language, "active": t.active,
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
    # Resolve o body final (template ou texto livre)
    template = None
    final_body_template: Optional[str] = None

    if body.template_id:
        template = db.query(WhatsAppTemplate).filter(
            WhatsAppTemplate.id == body.template_id,
            WhatsAppTemplate.active == True,  # noqa: E712
        ).first()
        if not template:
            raise HTTPException(404, "Template não encontrado ou inativo.")
        final_body_template = template.body
        for i, val in enumerate(body.variables, start=1):
            final_body_template = final_body_template.replace(f"{{{{{i}}}}}", val)

    elif not body.free_text:
        raise HTTPException(400, "Informe template_id ou free_text.")

    # Resolve destinatários
    recipients = _resolve_phones(body, db)
    if not recipients:
        raise HTTPException(400, "Nenhum destinatário encontrado.")

    sent_count = failed_count = 0
    results = []

    for rec in recipients:
        phone = rec["phone"]
        msg_body = final_body_template if template else (body.free_text or "")

        msg = WhatsAppMessage(
            id=str(uuid.uuid4()),
            template_id=template.id if template else None,
            customer_id=rec.get("customer_id"),
            phone=phone,
            body_sent=msg_body,
            status="pending",
        )
        db.add(msg)
        db.flush()

        wamid, status, error = _send_whatsapp_api(phone, msg_body, db)

        msg.status = status
        msg.wamid = wamid
        msg.error = error
        if status == "sent":
            msg.sent_at = _now()
            sent_count += 1
        else:
            failed_count += 1

        results.append({"phone": phone, "status": status, "wamid": wamid, "error": error})

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
            wm.phone, wm.body_sent, wm.status, wm.wamid, wm.error,
            wm.sent_at, wm.created_at
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
        "customer_name": r[3],
        "template_name": r[4],
        "phone": r[5],
        "body_sent": r[6],
        "status": r[7],
        "wamid": r[8],
        "error": r[9],
        "sent_at": r[10].isoformat() if r[10] else None,
        "created_at": r[11].isoformat() if r[11] else None,
    } for r in rows])


# ── Configurações ─────────────────────────────────────────────────────────────

@router.get("/config")
def get_config(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return ok(_cfg_to_dict(_get_config(db)))


@router.patch("/config")
def update_config(body: ConfigUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    cfg = _get_config(db)
    if body.connection_type is not None:
        cfg.connection_type = body.connection_type
    if body.messages_per_minute is not None:
        cfg.messages_per_minute = body.messages_per_minute
    if body.interval_seconds is not None:
        cfg.interval_seconds = body.interval_seconds
    if body.daily_limit is not None:
        cfg.daily_limit = body.daily_limit
    if body.webhook_url is not None:
        cfg.webhook_url = body.webhook_url
    cfg.updated_at = _now()
    db.commit()
    return ok(_cfg_to_dict(cfg))

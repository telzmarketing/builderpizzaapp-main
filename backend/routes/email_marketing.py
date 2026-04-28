"""Email Marketing — templates HTML, campanhas, envio via SMTP, config, histórico."""
import json
import smtplib
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, String, Boolean, Text, DateTime, Integer, Float, ForeignKey, text
from sqlalchemy.orm import Session

from backend.database import get_db, Base
from backend.routes.admin_auth import get_current_admin
from backend.core.response import ok, created

router = APIRouter(prefix="/email", tags=["email-marketing"])


# ── ORM Models ────────────────────────────────────────────────────────────────

class EmailTemplate(Base):
    __tablename__ = "email_templates"
    id = Column(String, primary_key=True)
    name = Column(String(200), nullable=False)
    subject = Column(String(500), nullable=False)
    body_html = Column(Text, nullable=False)
    category = Column(String(50), default="marketing")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class EmailMessage(Base):
    __tablename__ = "email_messages"
    id = Column(String, primary_key=True)
    template_id = Column(String, ForeignKey("email_templates.id", ondelete="SET NULL"), nullable=True)
    campaign_id = Column(String, ForeignKey("email_campaigns.id", ondelete="SET NULL"), nullable=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    to_email = Column(String(300), nullable=False)
    subject_sent = Column(String(500))
    status = Column(String(20), default="pending")
    error = Column(Text)
    sent_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EmailCampaign(Base):
    __tablename__ = "email_campaigns"
    id = Column(String, primary_key=True)
    name = Column(String(300), nullable=False)
    status = Column(String(30), nullable=False, default="draft")
    template_id = Column(String, ForeignKey("email_templates.id", ondelete="SET NULL"), nullable=True)
    group_id = Column(String, nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True)
    sent_count = Column(Integer, default=0)
    delivered_count = Column(Integer, default=0)
    open_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    bounce_count = Column(Integer, default=0)
    unsubscribe_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class EmailConfig(Base):
    __tablename__ = "email_config"
    id = Column(String, primary_key=True, default="default")
    provider = Column(String(30), default="smtp")
    smtp_host = Column(String(200), default="")
    smtp_port = Column(Integer, default=587)
    smtp_user = Column(String(300), default="")
    smtp_password = Column(String(500), default="")
    from_name = Column(String(200), default="Moschettieri")
    from_email = Column(String(300), default="")
    reply_to = Column(String(300), default="")
    status = Column(String(20), default="disconnected")
    daily_limit = Column(Integer, default=5000)
    rate_per_hour = Column(Integer, default=500)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class EmailTemplateCreate(BaseModel):
    name: str
    subject: str
    body_html: str
    category: str = "marketing"


class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body_html: Optional[str] = None
    category: Optional[str] = None
    active: Optional[bool] = None


class EmailSendRequest(BaseModel):
    template_id: Optional[str] = None
    subject: Optional[str] = None
    body_html: Optional[str] = None
    customer_ids: list[str] = []
    group_id: Optional[str] = None
    emails: list[str] = []
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
    provider: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    from_name: Optional[str] = None
    from_email: Optional[str] = None
    reply_to: Optional[str] = None
    daily_limit: Optional[int] = None
    rate_per_hour: Optional[int] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_config(db: Session) -> EmailConfig:
    cfg = db.query(EmailConfig).filter(EmailConfig.id == "default").first()
    if not cfg:
        cfg = EmailConfig(id="default")
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def _cfg_to_dict(cfg: EmailConfig) -> dict:
    return {
        "provider": cfg.provider, "smtp_host": cfg.smtp_host, "smtp_port": cfg.smtp_port,
        "smtp_user": cfg.smtp_user, "smtp_password": cfg.smtp_password,
        "from_name": cfg.from_name, "from_email": cfg.from_email, "reply_to": cfg.reply_to,
        "status": cfg.status, "daily_limit": cfg.daily_limit, "rate_per_hour": cfg.rate_per_hour,
    }


def _campaign_to_dict(c: EmailCampaign) -> dict:
    return {
        "id": c.id, "name": c.name, "status": c.status,
        "template_id": c.template_id, "group_id": c.group_id,
        "scheduled_at": c.scheduled_at.isoformat() if c.scheduled_at else None,
        "sent_count": c.sent_count or 0, "delivered_count": c.delivered_count or 0,
        "open_count": c.open_count or 0, "click_count": c.click_count or 0,
        "bounce_count": c.bounce_count or 0, "unsubscribe_count": c.unsubscribe_count or 0,
        "created_at": c.created_at.isoformat(),
    }


def _send_email(to_email: str, subject: str, body_html: str, cfg: EmailConfig) -> tuple[bool, Optional[str]]:
    host = cfg.smtp_host or ""
    port = cfg.smtp_port or 587
    user = cfg.smtp_user or ""
    password = cfg.smtp_password or ""
    from_name = cfg.from_name or user
    from_email = cfg.from_email or user

    if not host or not user or not password:
        return False, "Configuração SMTP incompleta (host / user / password)."
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email
        if cfg.reply_to:
            msg["Reply-To"] = cfg.reply_to
        msg.attach(MIMEText(body_html, "html", "utf-8"))
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.login(user, password)
            server.sendmail(from_email, [to_email], msg.as_string())
        return True, None
    except Exception as exc:
        return False, str(exc)


def _resolve_recipients(customer_ids: list[str], group_id: Optional[str],
                         emails: list[str], db: Session) -> list[dict]:
    """Resolve recipients to list of {id?, name?, email}."""
    result: list[dict] = []
    if group_id:
        rows = db.execute(text(
            "SELECT c.id, c.name, c.email FROM customers c "
            "JOIN customer_group_members cgm ON cgm.customer_id = c.id "
            "WHERE cgm.group_id = :gid AND c.email IS NOT NULL AND c.email != ''"
        ), {"gid": group_id}).fetchall()
        result = [{"id": r[0], "name": r[1], "email": r[2]} for r in rows]
    elif customer_ids:
        for cid in customer_ids:
            row = db.execute(text(
                "SELECT id, name, email FROM customers WHERE id = :cid "
                "AND email IS NOT NULL AND email != ''"
            ), {"cid": cid}).fetchone()
            if row:
                result.append({"id": row[0], "name": row[1], "email": row[2]})
    elif emails:
        result = [{"id": None, "name": None, "email": e} for e in emails if e.strip()]
    return result


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    totals = db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE status IN ('sent','delivered','opened','clicked')) AS sent,
            COUNT(*) FILTER (WHERE status = 'delivered') AS delivered,
            COUNT(*) FILTER (WHERE status = 'opened') AS opened,
            COUNT(*) FILTER (WHERE status = 'clicked') AS clicked,
            COUNT(*) FILTER (WHERE status = 'bounced') AS bounced,
            COUNT(*) FILTER (WHERE status = 'unsubscribed') AS unsubscribed,
            COUNT(*) FILTER (WHERE status = 'failed') AS errors
        FROM email_messages
    """)).fetchone()

    camp_stats = db.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'running') AS active_campaigns,
            COUNT(*) FILTER (WHERE status = 'scheduled') AS scheduled_campaigns
        FROM email_campaigns
    """)).fetchone()

    orders = db.execute(text(
        "SELECT COUNT(*), COALESCE(SUM(total),0) FROM orders WHERE utm_medium = 'email'"
    )).fetchone()

    sent = totals[0] or 0
    delivered = totals[1] or 0
    opened = totals[2] or 0
    clicked = totals[3] or 0

    return ok({
        "sent": sent,
        "delivered": delivered,
        "opened": opened,
        "clicked": clicked,
        "bounced": totals[4] or 0,
        "unsubscribed": totals[5] or 0,
        "errors": totals[6] or 0,
        "active_campaigns": camp_stats[0] or 0,
        "scheduled_campaigns": camp_stats[1] or 0,
        "open_rate": round(opened / sent, 4) if sent > 0 else 0,
        "click_rate": round(clicked / sent, 4) if sent > 0 else 0,
        "orders_generated": orders[0] or 0,
        "revenue_generated": float(orders[1] or 0),
    })


# ── Templates ─────────────────────────────────────────────────────────────────

@router.get("/templates")
def list_templates(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    templates = (
        db.query(EmailTemplate)
        .filter(EmailTemplate.active == True)  # noqa: E712
        .order_by(EmailTemplate.created_at.desc())
        .all()
    )
    return ok([{
        "id": t.id, "name": t.name, "subject": t.subject,
        "body_html": t.body_html, "category": t.category or "marketing",
        "active": t.active, "created_at": t.created_at.isoformat(),
    } for t in templates])


@router.post("/templates")
def create_template(body: EmailTemplateCreate, db: Session = Depends(get_db),
                    _=Depends(get_current_admin)):
    t = EmailTemplate(
        id=str(uuid.uuid4()),
        name=body.name, subject=body.subject,
        body_html=body.body_html, category=body.category,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return created({"id": t.id, "name": t.name, "subject": t.subject}, "Template criado.")


@router.patch("/templates/{template_id}")
def update_template(template_id: str, body: EmailTemplateUpdate,
                    db: Session = Depends(get_db), _=Depends(get_current_admin)):
    t = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not t:
        raise HTTPException(404, "Template não encontrado.")
    if body.name is not None:      t.name = body.name
    if body.subject is not None:   t.subject = body.subject
    if body.body_html is not None: t.body_html = body.body_html
    if body.category is not None:  t.category = body.category
    if body.active is not None:    t.active = body.active
    t.updated_at = _now()
    db.commit()
    return ok({"id": t.id, "name": t.name, "active": t.active})


@router.delete("/templates/{template_id}")
def delete_template(template_id: str, db: Session = Depends(get_db),
                    _=Depends(get_current_admin)):
    t = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not t:
        raise HTTPException(404, "Template não encontrado.")
    t.active = False
    t.updated_at = _now()
    db.commit()
    return ok(None, "Template desativado.")


# ── Campaigns ─────────────────────────────────────────────────────────────────

@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    campaigns = db.query(EmailCampaign).order_by(EmailCampaign.created_at.desc()).all()
    return ok([_campaign_to_dict(c) for c in campaigns])


@router.post("/campaigns")
def create_campaign(body: CampaignCreate, db: Session = Depends(get_db),
                    _=Depends(get_current_admin)):
    sched = None
    if body.scheduled_at:
        try:
            sched = datetime.fromisoformat(body.scheduled_at.replace("Z", "+00:00"))
        except Exception:
            pass
    c = EmailCampaign(
        id=str(uuid.uuid4()), name=body.name,
        template_id=body.template_id or None,
        group_id=body.group_id or None,
        scheduled_at=sched,
        status="scheduled" if sched else "draft",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return created(_campaign_to_dict(c), "Campanha criada.")


@router.patch("/campaigns/{campaign_id}")
def update_campaign(campaign_id: str, body: CampaignUpdate,
                    db: Session = Depends(get_db), _=Depends(get_current_admin)):
    c = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not c:
        raise HTTPException(404, "Campanha não encontrada.")
    if body.name is not None:        c.name = body.name
    if body.status is not None:      c.status = body.status
    if body.template_id is not None: c.template_id = body.template_id or None
    if body.group_id is not None:    c.group_id = body.group_id or None
    if body.scheduled_at is not None:
        try:
            c.scheduled_at = datetime.fromisoformat(body.scheduled_at.replace("Z", "+00:00"))
        except Exception:
            c.scheduled_at = None
    c.updated_at = _now()
    db.commit()
    return ok(_campaign_to_dict(c))


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: str, db: Session = Depends(get_db),
                    _=Depends(get_current_admin)):
    c = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not c:
        raise HTTPException(404, "Campanha não encontrada.")
    db.delete(c)
    db.commit()
    return ok(None, "Campanha excluída.")


# ── Send ──────────────────────────────────────────────────────────────────────

@router.post("/send")
def send_emails(body: EmailSendRequest, db: Session = Depends(get_db),
                _=Depends(get_current_admin)):
    cfg = _get_config(db)

    # Resolve template or free-text
    subject: str
    html: str
    if body.template_id:
        template = db.query(EmailTemplate).filter(
            EmailTemplate.id == body.template_id,
            EmailTemplate.active == True,  # noqa: E712
        ).first()
        if not template:
            raise HTTPException(404, "Template não encontrado ou inativo.")
        subject = template.subject
        html = template.body_html
    elif body.subject and body.body_html:
        subject = body.subject
        html = body.body_html
    else:
        raise HTTPException(400, "Informe template_id ou subject + body_html.")

    recipients = _resolve_recipients(body.customer_ids, body.group_id, body.emails, db)
    if not recipients:
        raise HTTPException(400, "Nenhum destinatário com email encontrado.")

    sent_count = 0
    failed_count = 0

    for r in recipients:
        msg = EmailMessage(
            id=str(uuid.uuid4()),
            template_id=body.template_id or None,
            customer_id=r.get("id"),
            to_email=r["email"],
            subject_sent=subject,
            status="pending",
        )
        db.add(msg)
        db.flush()

        try:
            success, error = _send_email(r["email"], subject, html, cfg)
        except Exception as exc:
            success, error = False, str(exc)

        if success:
            msg.status = "sent"
            msg.sent_at = _now()
            sent_count += 1
        else:
            msg.status = "failed"
            msg.error = error
            failed_count += 1

    db.commit()
    skipped = max(0, len(body.customer_ids) - sent_count - failed_count) if body.customer_ids else 0
    return ok({"sent": sent_count, "failed": failed_count, "skipped": skipped})


# ── Messages (monitoring) ─────────────────────────────────────────────────────

@router.get("/messages")
def list_messages(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    rows = db.execute(text("""
        SELECT
            em.id, em.template_id, em.customer_id,
            c.name AS customer_name,
            et.name AS template_name,
            em.to_email, em.subject_sent, em.status, em.error,
            em.sent_at, em.created_at
        FROM email_messages em
        LEFT JOIN customers c ON c.id = em.customer_id
        LEFT JOIN email_templates et ON et.id = em.template_id
        ORDER BY em.created_at DESC
        LIMIT 200
    """)).fetchall()

    return ok([{
        "id": r[0], "template_id": r[1], "customer_id": r[2],
        "customer_name": r[3], "template_name": r[4],
        "to_email": r[5], "subject_sent": r[6], "status": r[7], "error": r[8],
        "sent_at": r[9].isoformat() if r[9] else None,
        "created_at": r[10].isoformat() if r[10] else None,
    } for r in rows])


# ── Config ────────────────────────────────────────────────────────────────────

@router.get("/config")
def get_config(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    return ok(_cfg_to_dict(_get_config(db)))


@router.patch("/config")
def update_config(body: ConfigUpdate, db: Session = Depends(get_db),
                  _=Depends(get_current_admin)):
    cfg = _get_config(db)
    if body.provider is not None:      cfg.provider = body.provider
    if body.smtp_host is not None:     cfg.smtp_host = body.smtp_host
    if body.smtp_port is not None:     cfg.smtp_port = body.smtp_port
    if body.smtp_user is not None:     cfg.smtp_user = body.smtp_user
    if body.smtp_password is not None: cfg.smtp_password = body.smtp_password
    if body.from_name is not None:     cfg.from_name = body.from_name
    if body.from_email is not None:    cfg.from_email = body.from_email
    if body.reply_to is not None:      cfg.reply_to = body.reply_to
    if body.daily_limit is not None:   cfg.daily_limit = body.daily_limit
    if body.rate_per_hour is not None: cfg.rate_per_hour = body.rate_per_hour
    cfg.updated_at = _now()
    db.commit()
    return ok(_cfg_to_dict(cfg))


# ── Test connection ───────────────────────────────────────────────────────────

@router.post("/test-connection")
def test_connection(body: ConfigUpdate, db: Session = Depends(get_db),
                    _=Depends(get_current_admin)):
    """Test SMTP connection using the provided (or saved) credentials."""
    cfg = _get_config(db)
    # Override with what the user submitted for testing
    test_cfg = EmailConfig(
        smtp_host=body.smtp_host or cfg.smtp_host,
        smtp_port=body.smtp_port or cfg.smtp_port or 587,
        smtp_user=body.smtp_user or cfg.smtp_user,
        smtp_password=body.smtp_password or cfg.smtp_password,
        from_name=body.from_name or cfg.from_name,
        from_email=body.from_email or cfg.from_email,
        reply_to=body.reply_to or cfg.reply_to,
    )
    host = test_cfg.smtp_host or ""
    port = test_cfg.smtp_port or 587
    user = test_cfg.smtp_user or ""
    password = test_cfg.smtp_password or ""

    if not host or not user or not password:
        return ok({"success": False, "error": "Preencha host, usuário e senha antes de testar."})

    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(user, password)
        # Mark as connected in DB
        cfg.status = "connected"
        cfg.updated_at = _now()
        db.commit()
        return ok({"success": True})
    except Exception as exc:
        cfg.status = "disconnected"
        cfg.updated_at = _now()
        db.commit()
        return ok({"success": False, "error": str(exc)})

"""Email Marketing — templates HTML, envio via SMTP, histórico."""
import json
import smtplib
import uuid
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey, text
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
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class EmailMessage(Base):
    __tablename__ = "email_messages"
    id = Column(String, primary_key=True)
    template_id = Column(String, ForeignKey("email_templates.id", ondelete="SET NULL"), nullable=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    to_email = Column(String(300), nullable=False)
    subject_sent = Column(String(500))
    status = Column(String(20), default="pending")
    error = Column(Text)
    sent_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class EmailTemplateCreate(BaseModel):
    name: str
    subject: str
    body_html: str


class EmailTemplateUpdate(BaseModel):
    name: str | None = None
    subject: str | None = None
    body_html: str | None = None
    active: bool | None = None


class EmailSendRequest(BaseModel):
    template_id: str
    customer_ids: list[str] = []
    group_id: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_smtp_config(db: Session) -> dict | None:
    """Fetch SMTP credentials from integration_connections."""
    row = db.execute(
        text("SELECT credentials_json FROM integration_connections WHERE integration_type = 'smtp'")
    ).fetchone()
    if not row or not row[0]:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def _send_email(to_email: str, subject: str, body_html: str,
                smtp_config: dict) -> tuple[bool, str | None]:
    """Send an HTML email via SMTP/STARTTLS.

    Returns (success, error_message).
    """
    host = smtp_config.get("host", "")
    port = int(smtp_config.get("port", 587))
    user = smtp_config.get("user", "")
    password = smtp_config.get("password", "")
    from_name = smtp_config.get("from_name", user)

    if not host or not user or not password:
        return False, "Configuração SMTP incompleta (host / user / password)."

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{user}>"
        msg["To"] = to_email

        part_html = MIMEText(body_html, "html", "utf-8")
        msg.attach(part_html)

        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.login(user, password)
            server.sendmail(user, [to_email], msg.as_string())

        return True, None
    except Exception as exc:
        return False, str(exc)


def _fetch_customers_for_request(customer_ids: list[str], group_id: str | None,
                                  db: Session) -> list[dict]:
    """Resolve lista de clientes (com email) a partir de customer_ids ou group_id."""
    customers = []
    if group_id:
        rows = db.execute(
            text(
                "SELECT c.id, c.name, c.email FROM customers c "
                "JOIN customer_group_members cgm ON cgm.customer_id = c.id "
                "WHERE cgm.group_id = :gid AND c.email IS NOT NULL AND c.email != ''"
            ),
            {"gid": group_id},
        ).fetchall()
        customers = [{"id": r[0], "name": r[1], "email": r[2]} for r in rows]
    elif customer_ids:
        for cid in customer_ids:
            row = db.execute(
                text("SELECT id, name, email FROM customers WHERE id = :cid "
                     "AND email IS NOT NULL AND email != ''"),
                {"cid": cid},
            ).fetchone()
            if row:
                customers.append({"id": row[0], "name": row[1], "email": row[2]})
    return customers


# ── Routes ────────────────────────────────────────────────────────────────────

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
        "body_html": t.body_html, "active": t.active,
        "created_at": t.created_at.isoformat(),
    } for t in templates])


@router.post("/templates")
def create_template(body: EmailTemplateCreate, db: Session = Depends(get_db),
                    _=Depends(get_current_admin)):
    t = EmailTemplate(
        id=str(uuid.uuid4()),
        name=body.name,
        subject=body.subject,
        body_html=body.body_html,
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
    if body.name is not None:
        t.name = body.name
    if body.subject is not None:
        t.subject = body.subject
    if body.body_html is not None:
        t.body_html = body.body_html
    if body.active is not None:
        t.active = body.active
    t.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ok({"id": t.id, "name": t.name, "active": t.active})


@router.delete("/templates/{template_id}")
def delete_template(template_id: str, db: Session = Depends(get_db),
                    _=Depends(get_current_admin)):
    t = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not t:
        raise HTTPException(404, "Template não encontrado.")
    t.active = False
    t.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ok(None, "Template desativado.")


@router.post("/send")
def send_emails(body: EmailSendRequest, db: Session = Depends(get_db),
                _=Depends(get_current_admin)):
    smtp_config = _get_smtp_config(db)
    if not smtp_config:
        raise HTTPException(400, "SMTP não configurado. Acesse Integrações para configurar.")

    template = db.query(EmailTemplate).filter(
        EmailTemplate.id == body.template_id,
        EmailTemplate.active == True,  # noqa: E712
    ).first()
    if not template:
        raise HTTPException(404, "Template não encontrado ou inativo.")

    customers = _fetch_customers_for_request(body.customer_ids, body.group_id, db)

    # Conta skipped: customer_ids fornecidos mas sem email
    skipped_count = 0
    if body.group_id:
        total_in_group = db.execute(
            text("SELECT COUNT(*) FROM customer_group_members WHERE group_id = :gid"),
            {"gid": body.group_id},
        ).scalar() or 0
        skipped_count = max(0, total_in_group - len(customers))
    elif body.customer_ids:
        skipped_count = max(0, len(body.customer_ids) - len(customers))

    if not customers:
        raise HTTPException(400, "Nenhum cliente com e-mail encontrado para o envio.")

    sent_count = 0
    failed_count = 0

    for customer in customers:
        to_email = customer["email"]

        msg = EmailMessage(
            id=str(uuid.uuid4()),
            template_id=template.id,
            customer_id=customer["id"],
            to_email=to_email,
            subject_sent=template.subject,
            status="pending",
        )
        db.add(msg)
        db.flush()

        try:
            success, error = _send_email(to_email, template.subject, template.body_html, smtp_config)
        except Exception as exc:
            success, error = False, str(exc)

        if success:
            msg.status = "sent"
            msg.sent_at = datetime.now(timezone.utc)
            sent_count += 1
        else:
            msg.status = "failed"
            msg.error = error
            failed_count += 1

    db.commit()
    return ok({"sent": sent_count, "failed": failed_count, "skipped": skipped_count})


@router.get("/messages")
def list_messages(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    rows = db.execute(text("""
        SELECT
            em.id, em.template_id, em.customer_id,
            c.name AS customer_name,
            em.to_email, em.subject_sent, em.status, em.error,
            em.sent_at, em.created_at
        FROM email_messages em
        LEFT JOIN customers c ON c.id = em.customer_id
        ORDER BY em.created_at DESC
        LIMIT 100
    """)).fetchall()

    return ok([{
        "id": r[0],
        "template_id": r[1],
        "customer_id": r[2],
        "customer_name": r[3],
        "to_email": r[4],
        "subject_sent": r[5],
        "status": r[6],
        "error": r[7],
        "sent_at": r[8].isoformat() if r[8] else None,
        "created_at": r[9].isoformat() if r[9] else None,
    } for r in rows])

"""WhatsApp Marketing — templates, envio via Cloud API, histórico."""
import json
import uuid
import requests
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey, text
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
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    phone = Column(String(20), nullable=False)
    body_sent = Column(Text)
    status = Column(String(20), default="pending")
    wamid = Column(String(200))
    error = Column(Text)
    sent_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TemplateCreate(BaseModel):
    name: str
    body: str
    category: str = "marketing"
    language: str = "pt_BR"


class TemplateUpdate(BaseModel):
    name: str | None = None
    body: str | None = None
    category: str | None = None
    active: bool | None = None


class SendRequest(BaseModel):
    template_id: str
    customer_ids: list[str] = []
    group_id: str | None = None
    variables: list[str] = []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _send_whatsapp(phone: str, body: str, variables: list[str], db: Session) -> tuple[str | None, str, str | None]:
    """Send a WhatsApp message via Cloud API.

    Returns (wamid, status, error_msg).
    """
    conn = db.execute(
        text("SELECT credentials_json FROM integration_connections WHERE integration_type = 'whatsapp_cloud'")
    ).fetchone()

    if not conn or not conn[0]:
        return None, "failed", "WhatsApp Cloud API não configurado."

    try:
        creds = json.loads(conn[0])
    except Exception:
        return None, "failed", "Credenciais WhatsApp inválidas (JSON malformado)."

    phone_number_id = creds.get("phone_number_id")
    access_token = creds.get("access_token")

    if not phone_number_id or not access_token:
        return None, "failed", "Credenciais WhatsApp incompletas (phone_number_id / access_token)."

    # Substitui {{1}}, {{2}} etc. pelas variáveis fornecidas
    final_body = body
    for i, val in enumerate(variables, start=1):
        final_body = final_body.replace(f"{{{{{i}}}}}", val)

    # Normaliza telefone: remove tudo que não é dígito
    clean_phone = "".join(c for c in phone if c.isdigit())

    payload = {
        "messaging_product": "whatsapp",
        "to": clean_phone,
        "type": "text",
        "text": {"body": final_body},
    }

    try:
        resp = requests.post(
            f"https://graph.facebook.com/v19.0/{phone_number_id}/messages",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        data = resp.json()
        if resp.status_code == 200 and "messages" in data:
            wamid = data["messages"][0].get("id")
            return wamid, "sent", None
        error_msg = data.get("error", {}).get("message", resp.text)
        return None, "failed", error_msg
    except Exception as exc:
        return None, "failed", str(exc)


def _fetch_customers_for_request(body: SendRequest, db: Session) -> list[dict]:
    """Resolve lista de clientes a partir de customer_ids ou group_id."""
    customers = []
    if body.group_id:
        rows = db.execute(
            text(
                "SELECT c.id, c.name, c.phone FROM customers c "
                "JOIN customer_group_members cgm ON cgm.customer_id = c.id "
                "WHERE cgm.group_id = :gid AND c.phone IS NOT NULL"
            ),
            {"gid": body.group_id},
        ).fetchall()
        customers = [{"id": r[0], "name": r[1], "phone": r[2]} for r in rows]
    elif body.customer_ids:
        for cid in body.customer_ids:
            row = db.execute(
                text("SELECT id, name, phone FROM customers WHERE id = :cid AND phone IS NOT NULL"),
                {"cid": cid},
            ).fetchone()
            if row:
                customers.append({"id": row[0], "name": row[1], "phone": row[2]})
    return customers


# ── Routes ────────────────────────────────────────────────────────────────────

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
        "created_at": t.created_at.isoformat(),
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
    t.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ok({"id": t.id, "name": t.name, "active": t.active})


@router.delete("/templates/{template_id}")
def delete_template(template_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    t = db.query(WhatsAppTemplate).filter(WhatsAppTemplate.id == template_id).first()
    if not t:
        raise HTTPException(404, "Template não encontrado.")
    t.active = False
    t.updated_at = datetime.now(timezone.utc)
    db.commit()
    return ok(None, "Template desativado.")


@router.post("/send")
def send_messages(body: SendRequest, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    template = db.query(WhatsAppTemplate).filter(
        WhatsAppTemplate.id == body.template_id,
        WhatsAppTemplate.active == True,  # noqa: E712
    ).first()
    if not template:
        raise HTTPException(404, "Template não encontrado ou inativo.")

    customers = _fetch_customers_for_request(body, db)
    if not customers:
        raise HTTPException(400, "Nenhum cliente com telefone encontrado para o envio.")

    sent_count = 0
    failed_count = 0
    results = []

    for customer in customers:
        phone = customer["phone"]

        # Monta body com variáveis substituídas
        final_body = template.body
        for i, val in enumerate(body.variables, start=1):
            final_body = final_body.replace(f"{{{{{i}}}}}", val)

        msg = WhatsAppMessage(
            id=str(uuid.uuid4()),
            template_id=template.id,
            customer_id=customer["id"],
            phone=phone,
            body_sent=final_body,
            status="pending",
        )
        db.add(msg)
        db.flush()

        try:
            wamid, status, error = _send_whatsapp(phone, template.body, body.variables, db)
        except Exception as exc:
            wamid, status, error = None, "failed", str(exc)

        msg.status = status
        msg.wamid = wamid
        msg.error = error
        if status == "sent":
            msg.sent_at = datetime.now(timezone.utc)
            sent_count += 1
        else:
            failed_count += 1

        results.append({
            "customer_id": customer["id"],
            "phone": phone,
            "status": status,
            "wamid": wamid,
            "error": error,
        })

    db.commit()
    return ok({"sent": sent_count, "failed": failed_count, "messages": results})


@router.get("/messages")
def list_messages(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    rows = db.execute(text("""
        SELECT
            wm.id, wm.template_id, wm.customer_id,
            c.name AS customer_name,
            wm.phone, wm.body_sent, wm.status, wm.wamid, wm.error,
            wm.sent_at, wm.created_at
        FROM whatsapp_messages wm
        LEFT JOIN customers c ON c.id = wm.customer_id
        ORDER BY wm.created_at DESC
        LIMIT 100
    """)).fetchall()

    return ok([{
        "id": r[0],
        "template_id": r[1],
        "customer_id": r[2],
        "customer_name": r[3],
        "phone": r[4],
        "body_sent": r[5],
        "status": r[6],
        "wamid": r[7],
        "error": r[8],
        "sent_at": r[9].isoformat() if r[9] else None,
        "created_at": r[10].isoformat() if r[10] else None,
    } for r in rows])

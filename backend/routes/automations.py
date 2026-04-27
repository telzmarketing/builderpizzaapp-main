"""Marketing Automations — regras de disparo automático (WhatsApp/Email)."""
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, ForeignKey, text
from sqlalchemy.orm import Session

from backend.database import get_db, Base
from backend.routes.admin_auth import get_current_admin
from backend.core.response import ok, created

router = APIRouter(prefix="/automations", tags=["automations"])


# ── ORM Models ────────────────────────────────────────────────────────────────

class MarketingAutomation(Base):
    __tablename__ = "marketing_automations"
    id = Column(String, primary_key=True)
    name = Column(String(200), nullable=False)
    trigger = Column(String(50), nullable=False)
    trigger_value = Column(String(100))
    channel = Column(String(20), nullable=False)
    template_id = Column(String)
    message_body = Column(Text)
    active = Column(Boolean, default=True)
    runs_total = Column(Integer, default=0)
    last_run_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class AutomationLog(Base):
    __tablename__ = "automation_logs"
    id = Column(String, primary_key=True)
    automation_id = Column(String, ForeignKey("marketing_automations.id", ondelete="CASCADE"),
                           nullable=False)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    channel = Column(String(20))
    status = Column(String(20))
    error = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class AutomationCreate(BaseModel):
    name: str
    trigger: str
    trigger_value: str | None = None
    channel: str
    template_id: str | None = None
    message_body: str | None = None


class AutomationUpdate(BaseModel):
    name: str | None = None
    trigger: str | None = None
    trigger_value: str | None = None
    channel: str | None = None
    template_id: str | None = None
    message_body: str | None = None
    active: bool | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _already_sent_today(automation_id: str, customer_id: str, db: Session) -> bool:
    """Verifica se já houve disparo para esse cliente hoje (evita duplicatas)."""
    today_start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    row = db.execute(
        text(
            "SELECT id FROM automation_logs "
            "WHERE automation_id = :aid AND customer_id = :cid "
            "AND created_at >= :since AND status = 'sent'"
        ),
        {"aid": automation_id, "cid": customer_id, "since": today_start},
    ).fetchone()
    return row is not None


def _get_eligible_customers(automation: MarketingAutomation, db: Session) -> list[dict]:
    """Retorna lista de clientes elegíveis para o trigger da automação."""
    now = _now()

    if automation.trigger == "reactivation":
        days = int(automation.trigger_value or "30")
        cutoff = now - timedelta(days=days)
        rows = db.execute(
            text(
                "SELECT id, name, phone, email FROM customers "
                "WHERE last_order_at IS NOT NULL AND last_order_at <= :cutoff"
            ),
            {"cutoff": cutoff},
        ).fetchall()

    elif automation.trigger == "birthday":
        today = now.date()
        rows = db.execute(
            text(
                "SELECT id, name, phone, email FROM customers "
                "WHERE birth_date IS NOT NULL "
                "AND EXTRACT(MONTH FROM birth_date) = :month "
                "AND EXTRACT(DAY FROM birth_date) = :day"
            ),
            {"month": today.month, "day": today.day},
        ).fetchall()

    elif automation.trigger == "first_order":
        rows = db.execute(
            text(
                "SELECT id, name, phone, email FROM customers "
                "WHERE total_orders = 1"
            )
        ).fetchall()

    elif automation.trigger == "new_customer":
        since = now - timedelta(hours=24)
        rows = db.execute(
            text(
                "SELECT id, name, phone, email FROM customers "
                "WHERE created_at >= :since"
            ),
            {"since": since},
        ).fetchall()

    elif automation.trigger == "abandoned_cart":
        days = int(automation.trigger_value or "1")
        since = now - timedelta(days=days)
        # Clientes que geraram evento add_to_cart mas não fizeram pedido no período
        rows = db.execute(
            text("""
                SELECT DISTINCT c.id, c.name, c.phone, c.email
                FROM customers c
                JOIN visitor_profiles vp ON vp.customer_id = c.id
                JOIN visitor_events ve ON ve.visitor_id = vp.id
                WHERE ve.event_type = 'add_to_cart'
                  AND ve.created_at >= :since
                  AND NOT EXISTS (
                      SELECT 1 FROM orders o
                      WHERE o.customer_id = c.id
                        AND o.created_at >= :since
                  )
            """),
            {"since": since},
        ).fetchall()

    else:
        rows = []

    return [{"id": r[0], "name": r[1], "phone": r[2], "email": r[3]} for r in rows]


def _run_automation(automation_id: str, db: Session) -> dict:
    """Executa uma automação e registra os logs. Retorna resumo."""
    automation = db.query(MarketingAutomation).filter(
        MarketingAutomation.id == automation_id
    ).first()
    if not automation:
        raise HTTPException(404, "Automação não encontrada.")

    customers = _get_eligible_customers(automation, db)

    sent_count = 0
    failed_count = 0
    skipped_count = 0

    for customer in customers:
        # Evita duplicatas no mesmo dia
        if _already_sent_today(automation_id, customer["id"], db):
            skipped_count += 1
            continue

        status = "failed"
        error_msg = None

        if automation.channel == "whatsapp":
            phone = customer.get("phone")
            if not phone:
                status = "skipped"
                error_msg = "Cliente sem telefone."
            else:
                body = automation.message_body or ""
                variables: list[str] = []

                # Se tem template_id, busca body do template WhatsApp
                if automation.template_id:
                    row = db.execute(
                        text("SELECT body FROM whatsapp_templates WHERE id = :tid AND active = TRUE"),
                        {"tid": automation.template_id},
                    ).fetchone()
                    if row:
                        body = row[0]

                if body:
                    try:
                        from backend.routes.whatsapp_marketing import _send_whatsapp
                        wamid, status, error_msg = _send_whatsapp(phone, body, variables, db)
                    except Exception as exc:
                        status = "failed"
                        error_msg = str(exc)
                else:
                    status = "failed"
                    error_msg = "Nenhum corpo de mensagem definido."

        elif automation.channel == "email":
            to_email = customer.get("email")
            if not to_email:
                status = "skipped"
                error_msg = "Cliente sem e-mail."
            else:
                subject = "Mensagem da Pizzaria"
                body_html = automation.message_body or ""

                # Se tem template_id, busca subject + body do template Email
                if automation.template_id:
                    row = db.execute(
                        text("SELECT subject, body_html FROM email_templates WHERE id = :tid AND active = TRUE"),
                        {"tid": automation.template_id},
                    ).fetchone()
                    if row:
                        subject = row[0]
                        body_html = row[1]

                if body_html:
                    try:
                        from backend.routes.email_marketing import _send_email, _get_smtp_config
                        smtp_config = _get_smtp_config(db)
                        if smtp_config:
                            success, error_msg = _send_email(to_email, subject, body_html, smtp_config)
                            status = "sent" if success else "failed"
                        else:
                            status = "failed"
                            error_msg = "SMTP não configurado."
                    except Exception as exc:
                        status = "failed"
                        error_msg = str(exc)
                else:
                    status = "failed"
                    error_msg = "Nenhum corpo de mensagem definido."

        else:
            status = "failed"
            error_msg = f"Canal '{automation.channel}' não suportado."

        # Registra log
        log = AutomationLog(
            id=str(uuid.uuid4()),
            automation_id=automation_id,
            customer_id=customer["id"],
            channel=automation.channel,
            status=status,
            error=error_msg,
        )
        db.add(log)

        if status == "sent":
            sent_count += 1
        elif status == "skipped":
            skipped_count += 1
        else:
            failed_count += 1

    # Atualiza totalizadores da automação
    automation.runs_total = (automation.runs_total or 0) + 1
    automation.last_run_at = _now()
    automation.updated_at = _now()

    db.commit()
    return {"sent": sent_count, "failed": failed_count, "skipped": skipped_count}


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("")
def list_automations(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    automations = (
        db.query(MarketingAutomation)
        .order_by(MarketingAutomation.created_at.desc())
        .all()
    )
    result = []
    for a in automations:
        log_count = db.execute(
            text("SELECT COUNT(*) FROM automation_logs WHERE automation_id = :aid"),
            {"aid": a.id},
        ).scalar() or 0
        result.append({
            "id": a.id,
            "name": a.name,
            "trigger": a.trigger,
            "trigger_value": a.trigger_value,
            "channel": a.channel,
            "template_id": a.template_id,
            "active": a.active,
            "runs_total": a.runs_total,
            "last_run_at": a.last_run_at.isoformat() if a.last_run_at else None,
            "total_logs": log_count,
            "created_at": a.created_at.isoformat(),
        })
    return ok(result)


@router.post("")
def create_automation(body: AutomationCreate, db: Session = Depends(get_db),
                      _=Depends(get_current_admin)):
    valid_triggers = {"abandoned_cart", "reactivation", "birthday", "first_order", "new_customer"}
    if body.trigger not in valid_triggers:
        raise HTTPException(400, f"Trigger inválido. Use: {', '.join(valid_triggers)}.")
    valid_channels = {"whatsapp", "email"}
    if body.channel not in valid_channels:
        raise HTTPException(400, f"Canal inválido. Use: {', '.join(valid_channels)}.")

    a = MarketingAutomation(
        id=str(uuid.uuid4()),
        name=body.name,
        trigger=body.trigger,
        trigger_value=body.trigger_value,
        channel=body.channel,
        template_id=body.template_id,
        message_body=body.message_body,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return created({"id": a.id, "name": a.name, "trigger": a.trigger, "active": a.active},
                   "Automação criada.")


@router.patch("/{automation_id}")
def update_automation(automation_id: str, body: AutomationUpdate,
                      db: Session = Depends(get_db), _=Depends(get_current_admin)):
    a = db.query(MarketingAutomation).filter(MarketingAutomation.id == automation_id).first()
    if not a:
        raise HTTPException(404, "Automação não encontrada.")
    if body.name is not None:
        a.name = body.name
    if body.trigger is not None:
        a.trigger = body.trigger
    if body.trigger_value is not None:
        a.trigger_value = body.trigger_value
    if body.channel is not None:
        a.channel = body.channel
    if body.template_id is not None:
        a.template_id = body.template_id
    if body.message_body is not None:
        a.message_body = body.message_body
    if body.active is not None:
        a.active = body.active
    a.updated_at = _now()
    db.commit()
    return ok({"id": a.id, "name": a.name, "active": a.active})


@router.delete("/{automation_id}")
def delete_automation(automation_id: str, db: Session = Depends(get_db),
                      _=Depends(get_current_admin)):
    a = db.query(MarketingAutomation).filter(MarketingAutomation.id == automation_id).first()
    if not a:
        raise HTTPException(404, "Automação não encontrada.")
    db.delete(a)
    db.commit()
    return ok(None, "Automação removida.")


@router.post("/{automation_id}/toggle")
def toggle_automation(automation_id: str, db: Session = Depends(get_db),
                       _=Depends(get_current_admin)):
    a = db.query(MarketingAutomation).filter(MarketingAutomation.id == automation_id).first()
    if not a:
        raise HTTPException(404, "Automação não encontrada.")
    a.active = not a.active
    a.updated_at = _now()
    db.commit()
    return ok({"id": a.id, "active": a.active})


@router.post("/{automation_id}/run")
def run_automation(automation_id: str, db: Session = Depends(get_db),
                   _=Depends(get_current_admin)):
    result = _run_automation(automation_id, db)
    return ok(result, "Automação executada.")


@router.get("/{automation_id}/logs")
def list_automation_logs(automation_id: str, db: Session = Depends(get_db),
                          _=Depends(get_current_admin)):
    a = db.query(MarketingAutomation).filter(MarketingAutomation.id == automation_id).first()
    if not a:
        raise HTTPException(404, "Automação não encontrada.")

    rows = db.execute(
        text("""
            SELECT al.id, al.customer_id, c.name AS customer_name,
                   al.channel, al.status, al.error, al.created_at
            FROM automation_logs al
            LEFT JOIN customers c ON c.id = al.customer_id
            WHERE al.automation_id = :aid
            ORDER BY al.created_at DESC
            LIMIT 50
        """),
        {"aid": automation_id},
    ).fetchall()

    return ok([{
        "id": r[0],
        "customer_id": r[1],
        "customer_name": r[2],
        "channel": r[3],
        "status": r[4],
        "error": r[5],
        "created_at": r[6].isoformat() if r[6] else None,
    } for r in rows])

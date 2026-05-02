"""Marketing Automations — regras de disparo automático (WhatsApp/Email)."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Column, String, Boolean, Integer, Text, DateTime, ForeignKey, text
from sqlalchemy.orm import Session

from backend.database import get_db, Base
from backend.routes.admin_auth import get_current_admin
from backend.core.response import ok, created

router = APIRouter(prefix="/automations", tags=["automations"])

VALID_TRIGGERS = {
    "new_customer", "first_order", "repeat_order", "order_completed",
    "order_cancelled", "abandoned_cart", "reactivation", "birthday",
    "birthday_week", "low_points", "level_up", "no_engagement",
    "coupon_unused", "vip_milestone", "product_back", "high_value_order",
    "days_after_last_order", "same_weekday_last_order", "preferred_purchase_time",
    "product_purchased", "category_purchased", "registered_no_order",
    "inactive_customer", "recurring_customer", "vip_customer", "tag_match",
    "group_match", "segment_match",
}
VALID_CHANNELS = {"whatsapp", "email"}


# ── ORM Models ────────────────────────────────────────────────────────────────

class MarketingAutomation(Base):
    __tablename__ = "marketing_automations"
    id = Column(String, primary_key=True)
    name = Column(String(200), nullable=False)
    trigger = Column(String(50), nullable=False)
    trigger_value = Column(String(100))
    trigger_delay_hours = Column(Integer, default=0)
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


class AutomationTemplate(Base):
    __tablename__ = "automation_templates"
    id = Column(String, primary_key=True)
    name = Column(String(200), nullable=False)
    channel = Column(String(20), nullable=False, default="whatsapp")
    subject = Column(String(500))
    body = Column(Text, nullable=False)
    variables = Column(String(500))
    category = Column(String(50), default="marketing")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class AutomationCreate(BaseModel):
    name: str
    trigger: str
    trigger_value: Optional[str] = None
    trigger_delay_hours: int = 0
    channel: str
    template_id: Optional[str] = None
    message_body: Optional[str] = None


class AutomationUpdate(BaseModel):
    name: Optional[str] = None
    trigger: Optional[str] = None
    trigger_value: Optional[str] = None
    trigger_delay_hours: Optional[int] = None
    channel: Optional[str] = None
    template_id: Optional[str] = None
    message_body: Optional[str] = None
    active: Optional[bool] = None


class AutomationTemplateCreate(BaseModel):
    name: str
    channel: str = "whatsapp"
    subject: Optional[str] = None
    body: str
    variables: Optional[str] = None
    category: str = "marketing"


class AutomationTemplateUpdate(BaseModel):
    name: Optional[str] = None
    channel: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    variables: Optional[str] = None
    category: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _already_sent_today(automation_id: str, customer_id: str, db: Session) -> bool:
    today_start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    row = db.execute(text(
        "SELECT id FROM automation_logs "
        "WHERE automation_id = :aid AND customer_id = :cid "
        "AND created_at >= :since AND status = 'sent'"
    ), {"aid": automation_id, "cid": customer_id, "since": today_start}).fetchone()
    return row is not None


def _get_eligible_customers(automation: MarketingAutomation, db: Session) -> list[dict]:
    now = _now()

    if automation.trigger == "reactivation":
        days = int(automation.trigger_value or "30")
        cutoff = now - timedelta(days=days)
        rows = db.execute(text(
            "SELECT id, name, phone, email FROM customers "
            "WHERE last_order_at IS NOT NULL AND last_order_at <= :cutoff"
        ), {"cutoff": cutoff}).fetchall()

    elif automation.trigger in ("birthday", "birthday_week"):
        today = now.date()
        rows = db.execute(text(
            "SELECT id, name, phone, email FROM customers "
            "WHERE birth_date IS NOT NULL "
            "AND EXTRACT(MONTH FROM birth_date) = :month "
            "AND EXTRACT(DAY FROM birth_date) = :day"
        ), {"month": today.month, "day": today.day}).fetchall()

    elif automation.trigger == "first_order":
        rows = db.execute(text(
            "SELECT id, name, phone, email FROM customers WHERE total_orders = 1"
        )).fetchall()

    elif automation.trigger == "new_customer":
        since = now - timedelta(hours=24)
        rows = db.execute(text(
            "SELECT id, name, phone, email FROM customers WHERE created_at >= :since"
        ), {"since": since}).fetchall()

    elif automation.trigger == "abandoned_cart":
        minutes = int(automation.trigger_value or "60")
        since = now - timedelta(minutes=minutes)
        rows = db.execute(text("""
            SELECT DISTINCT c.id, c.name, c.phone, c.email
            FROM customers c
            JOIN visitor_profiles vp ON vp.customer_id = c.id
            JOIN visitor_events ve ON ve.visitor_id = vp.id
            WHERE ve.event_type = 'add_to_cart'
              AND ve.created_at >= :since
              AND NOT EXISTS (
                  SELECT 1 FROM orders o
                  WHERE o.customer_id = c.id AND o.created_at >= :since
              )
        """), {"since": since}).fetchall()

    elif automation.trigger == "high_value_order":
        min_val = float(automation.trigger_value or "100")
        since = now - timedelta(hours=24)
        rows = db.execute(text(
            "SELECT DISTINCT c.id, c.name, c.phone, c.email FROM customers c "
            "JOIN orders o ON o.customer_id = c.id "
            "WHERE o.total >= :min_val AND o.created_at >= :since"
        ), {"min_val": min_val, "since": since}).fetchall()

    elif automation.trigger in ("order_completed", "repeat_order"):
        since = now - timedelta(hours=24)
        rows = db.execute(text(
            "SELECT DISTINCT c.id, c.name, c.phone, c.email FROM customers c "
            "JOIN orders o ON o.customer_id = c.id "
            "WHERE o.status = 'delivered' AND o.created_at >= :since"
        ), {"since": since}).fetchall()

    else:
        rows = []

    return [{"id": r[0], "name": r[1], "phone": r[2], "email": r[3]} for r in rows]


def _run_automation(automation_id: str, db: Session) -> dict:
    from backend.services.automation_service import run_automation_now

    return run_automation_now(db, automation_id)

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
                if automation.template_id:
                    row = db.execute(text(
                        "SELECT body FROM automation_templates WHERE id = :tid"
                    ), {"tid": automation.template_id}).fetchone()
                    if row:
                        body = row[0]
                    else:
                        # Fallback: whatsapp_templates
                        row = db.execute(text(
                            "SELECT body FROM whatsapp_templates WHERE id = :tid AND active = TRUE"
                        ), {"tid": automation.template_id}).fetchone()
                        if row:
                            body = row[0]

                if body:
                    try:
                        from backend.routes.whatsapp_marketing import _send_whatsapp_api
                        _wamid, status, error_msg = _send_whatsapp_api(phone, body, db)
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
                if automation.template_id:
                    row = db.execute(text(
                        "SELECT body, subject FROM automation_templates WHERE id = :tid"
                    ), {"tid": automation.template_id}).fetchone()
                    if row:
                        body_html = row[0]
                        if row[1]:
                            subject = row[1]
                    else:
                        row = db.execute(text(
                            "SELECT subject, body_html FROM email_templates WHERE id = :tid AND active = TRUE"
                        ), {"tid": automation.template_id}).fetchone()
                        if row:
                            subject = row[0]
                            body_html = row[1]

                if body_html:
                    try:
                        from backend.routes.email_marketing import _send_email, _get_config
                        cfg = _get_config(db)
                        success, error_msg = _send_email(to_email, subject, body_html, cfg)
                        status = "sent" if success else "failed"
                    except Exception as exc:
                        status = "failed"
                        error_msg = str(exc)
                else:
                    status = "failed"
                    error_msg = "Nenhum corpo de mensagem definido."
        else:
            status = "failed"
            error_msg = f"Canal '{automation.channel}' não suportado."

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

    automation.runs_total = (automation.runs_total or 0) + 1
    automation.last_run_at = _now()
    automation.updated_at = _now()
    db.commit()
    return {"sent": sent_count, "failed": failed_count, "skipped": skipped_count}


# ── Routes — Templates (must come before /{automation_id}) ───────────────────

@router.get("/templates")
def list_templates(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    templates = db.query(AutomationTemplate).order_by(AutomationTemplate.created_at.desc()).all()
    return ok([{
        "id": t.id, "name": t.name, "channel": t.channel, "subject": t.subject,
        "body": t.body, "variables": t.variables, "category": t.category,
        "created_at": t.created_at.isoformat(),
    } for t in templates])


@router.post("/templates")
def create_template(body: AutomationTemplateCreate, db: Session = Depends(get_db),
                    _=Depends(get_current_admin)):
    t = AutomationTemplate(
        id=str(uuid.uuid4()), name=body.name, channel=body.channel,
        subject=body.subject, body=body.body,
        variables=body.variables, category=body.category,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return created({"id": t.id, "name": t.name}, "Template criado.")


@router.patch("/templates/{template_id}")
def update_template(template_id: str, body: AutomationTemplateUpdate,
                    db: Session = Depends(get_db), _=Depends(get_current_admin)):
    t = db.query(AutomationTemplate).filter(AutomationTemplate.id == template_id).first()
    if not t:
        raise HTTPException(404, "Template não encontrado.")
    if body.name is not None:      t.name = body.name
    if body.channel is not None:   t.channel = body.channel
    if body.subject is not None:   t.subject = body.subject
    if body.body is not None:      t.body = body.body
    if body.variables is not None: t.variables = body.variables
    if body.category is not None:  t.category = body.category
    t.updated_at = _now()
    db.commit()
    return ok({"id": t.id, "name": t.name})


@router.delete("/templates/{template_id}")
def delete_template(template_id: str, db: Session = Depends(get_db),
                    _=Depends(get_current_admin)):
    t = db.query(AutomationTemplate).filter(AutomationTemplate.id == template_id).first()
    if not t:
        raise HTTPException(404, "Template não encontrado.")
    db.delete(t)
    db.commit()
    return ok(None, "Template excluído.")


# ── Routes — Global Logs ──────────────────────────────────────────────────────

@router.get("/logs")
def list_global_logs(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    rows = db.execute(text("""
        SELECT al.id, ma.name AS automation_name, al.customer_id,
               al.channel, al.status, al.error, al.created_at
        FROM automation_logs al
        JOIN marketing_automations ma ON ma.id = al.automation_id
        ORDER BY al.created_at DESC
        LIMIT 200
    """)).fetchall()
    return ok([{
        "id": r[0], "automation_name": r[1], "customer_id": r[2],
        "channel": r[3], "status": r[4], "error": r[5],
        "created_at": r[6].isoformat() if r[6] else None,
    } for r in rows])


# ── Routes — Events Stats ─────────────────────────────────────────────────────

@router.get("/events")
def list_events(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    rows = db.execute(text("""
        SELECT ma.trigger AS event_name,
               COUNT(al.id) AS count,
               COUNT(DISTINCT al.customer_id) AS unique_customers,
               MAX(al.created_at) AS last_triggered
        FROM automation_logs al
        JOIN marketing_automations ma ON ma.id = al.automation_id
        GROUP BY ma.trigger
        ORDER BY count DESC
    """)).fetchall()
    return ok([{
        "event_name": r[0], "count": r[1] or 0, "unique_customers": r[2] or 0,
        "last_triggered": r[3].isoformat() if r[3] else None,
    } for r in rows])


# ── Routes — Automations CRUD ─────────────────────────────────────────────────

@router.get("")
def list_automations(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    automations = (
        db.query(MarketingAutomation)
        .order_by(MarketingAutomation.created_at.desc())
        .all()
    )
    result = []
    for a in automations:
        log_count = db.execute(text(
            "SELECT COUNT(*) FROM automation_logs WHERE automation_id = :aid"
        ), {"aid": a.id}).scalar() or 0
        result.append({
            "id": a.id, "name": a.name, "trigger": a.trigger,
            "trigger_value": a.trigger_value,
            "trigger_delay_hours": a.trigger_delay_hours or 0,
            "channel": a.channel, "template_id": a.template_id,
            "message_body": a.message_body,
            "active": a.active, "runs_total": a.runs_total or 0,
            "last_run_at": a.last_run_at.isoformat() if a.last_run_at else None,
            "total_logs": log_count,
            "created_at": a.created_at.isoformat(),
        })
    return ok(result)


@router.post("/queue/enqueue-due")
def enqueue_due_automation_queue(
    limit: int = 50,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from backend.services.automation_service import enqueue_due_automations

    return ok(enqueue_due_automations(db, limit=limit), "Fila de automacoes atualizada.")


@router.post("/queue/process")
def process_automation_queue(
    limit: int = 100,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from backend.services.automation_service import process_pending_executions

    return ok(process_pending_executions(db, limit=limit), "Fila de automacoes processada.")


@router.post("/queue/run-due")
def run_due_automation_queue(
    automation_limit: int = 50,
    execution_limit: int = 100,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    from backend.services.automation_service import run_due_automation_worker

    return ok(
        run_due_automation_worker(db, automation_limit=automation_limit, execution_limit=execution_limit),
        "Worker de automacoes executado.",
    )


@router.post("")
def create_automation(body: AutomationCreate, db: Session = Depends(get_db),
                      _=Depends(get_current_admin)):
    if body.trigger not in VALID_TRIGGERS:
        raise HTTPException(400, f"Trigger inválido. Use: {', '.join(sorted(VALID_TRIGGERS))}.")
    if body.channel not in VALID_CHANNELS:
        raise HTTPException(400, f"Canal inválido. Use: {', '.join(VALID_CHANNELS)}.")

    a = MarketingAutomation(
        id=str(uuid.uuid4()), name=body.name,
        trigger=body.trigger, trigger_value=body.trigger_value,
        trigger_delay_hours=body.trigger_delay_hours,
        channel=body.channel, template_id=body.template_id,
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
    if body.name is not None:                 a.name = body.name
    if body.trigger is not None:              a.trigger = body.trigger
    if body.trigger_value is not None:        a.trigger_value = body.trigger_value
    if body.trigger_delay_hours is not None:  a.trigger_delay_hours = body.trigger_delay_hours
    if body.channel is not None:              a.channel = body.channel
    if body.template_id is not None:          a.template_id = body.template_id or None
    if body.message_body is not None:         a.message_body = body.message_body
    if body.active is not None:               a.active = body.active
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
    rows = db.execute(text("""
        SELECT al.id, al.customer_id, c.name AS customer_name,
               al.channel, al.status, al.error, al.created_at
        FROM automation_logs al
        LEFT JOIN customers c ON c.id = al.customer_id
        WHERE al.automation_id = :aid
        ORDER BY al.created_at DESC
        LIMIT 50
    """), {"aid": automation_id}).fetchall()
    return ok([{
        "id": r[0], "customer_id": r[1], "customer_name": r[2],
        "channel": r[3], "status": r[4], "error": r[5],
        "created_at": r[6].isoformat() if r[6] else None,
    } for r in rows])

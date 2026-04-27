"""CRM — Pipelines, Stages, Cards, Tasks, Customer Groups, Timeline."""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Column, String, Boolean, Integer, Float, Text, DateTime, Date, ForeignKey, text
from sqlalchemy.orm import Session

from backend.database import get_db, Base
from backend.routes.admin_auth import get_current_admin
from backend.core.response import ok, created

router = APIRouter(prefix="/crm", tags=["crm"])


# ── ORM Models ────────────────────────────────────────────────────────────────

class CrmPipeline(Base):
    __tablename__ = "crm_pipelines"
    id = Column(String, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    pipeline_type = Column(String(30), default="custom")
    active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class CrmStage(Base):
    __tablename__ = "crm_stages"
    id = Column(String, primary_key=True)
    pipeline_id = Column(String, ForeignKey("crm_pipelines.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    color = Column(String(20), default="#2d3d56")
    sort_order = Column(Integer, default=0)
    auto_move_rule = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CrmCard(Base):
    __tablename__ = "crm_cards"
    id = Column(String, primary_key=True)
    pipeline_id = Column(String, ForeignKey("crm_pipelines.id", ondelete="CASCADE"), nullable=False)
    stage_id = Column(String, ForeignKey("crm_stages.id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    value = Column(Float)
    source = Column(String(100))
    responsible = Column(String(200))
    tags = Column(Text, default="[]")
    last_interaction_at = Column(DateTime(timezone=True))
    next_follow_up_at = Column(DateTime(timezone=True))
    sort_order = Column(Integer, default=0)
    archived = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class CrmTask(Base):
    __tablename__ = "crm_tasks"
    id = Column(String, primary_key=True)
    card_id = Column(String, ForeignKey("crm_cards.id", ondelete="SET NULL"), nullable=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    task_type = Column(String(50), default="other")
    responsible = Column(String(200))
    due_date = Column(DateTime(timezone=True))
    priority = Column(String(20), default="medium")
    status = Column(String(20), default="pending")
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class CustomerGroup(Base):
    __tablename__ = "customer_groups"
    id = Column(String, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    group_type = Column(String(20), default="manual")
    color = Column(String(20), default="#f97316")
    icon = Column(String(50))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class CustomerTimeline(Base):
    __tablename__ = "customer_timeline"
    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(80), nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    metadata_json = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class PipelineCreate(BaseModel):
    name: str
    description: str | None = None
    pipeline_type: str = "custom"


class StageCreate(BaseModel):
    name: str
    description: str | None = None
    color: str = "#2d3d56"
    sort_order: int = 0


class CardCreate(BaseModel):
    stage_id: str
    customer_id: str | None = None
    title: str
    description: str | None = None
    value: float | None = None
    source: str | None = None
    responsible: str | None = None
    tags: list[str] = []


class CardMove(BaseModel):
    stage_id: str
    sort_order: int | None = None


class CardUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    value: float | None = None
    source: str | None = None
    responsible: str | None = None
    tags: list[str] | None = None
    next_follow_up_at: str | None = None


class TaskCreate(BaseModel):
    card_id: str | None = None
    customer_id: str | None = None
    title: str
    description: str | None = None
    task_type: str = "other"
    responsible: str | None = None
    due_date: str | None = None
    priority: str = "medium"


class GroupCreate(BaseModel):
    name: str
    description: str | None = None
    group_type: str = "manual"
    color: str = "#f97316"
    icon: str | None = None
    rules: list[dict] = []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _card_to_dict(card: CrmCard, db: Session) -> dict:
    customer = None
    if card.customer_id:
        from backend.models.customer import Customer
        c = db.query(Customer).filter(Customer.id == card.customer_id).first()
        if c:
            customer = {"id": c.id, "name": c.name, "email": c.email, "phone": c.phone}
    import json
    return {
        "id": card.id, "pipeline_id": card.pipeline_id, "stage_id": card.stage_id,
        "customer_id": card.customer_id, "customer": customer, "title": card.title,
        "description": card.description, "value": card.value, "source": card.source,
        "responsible": card.responsible, "tags": json.loads(card.tags or "[]"),
        "last_interaction_at": card.last_interaction_at.isoformat() if card.last_interaction_at else None,
        "next_follow_up_at": card.next_follow_up_at.isoformat() if card.next_follow_up_at else None,
        "sort_order": card.sort_order, "archived": card.archived,
        "created_at": card.created_at.isoformat(), "updated_at": card.updated_at.isoformat(),
    }


# ── Pipeline routes ───────────────────────────────────────────────────────────

@router.get("/pipelines")
def list_pipelines(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    pipelines = db.query(CrmPipeline).filter(CrmPipeline.active == True).order_by(CrmPipeline.sort_order).all()  # noqa: E712
    result = []
    for p in pipelines:
        stages = db.query(CrmStage).filter(CrmStage.pipeline_id == p.id).order_by(CrmStage.sort_order).all()
        result.append({
            "id": p.id, "name": p.name, "description": p.description,
            "pipeline_type": p.pipeline_type, "sort_order": p.sort_order,
            "stages": [{"id": s.id, "name": s.name, "color": s.color, "sort_order": s.sort_order, "description": s.description} for s in stages],
        })
    return ok(result)


@router.post("/pipelines")
def create_pipeline(body: PipelineCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    p = CrmPipeline(id=str(uuid.uuid4()), name=body.name, description=body.description, pipeline_type=body.pipeline_type)
    db.add(p)
    db.commit()
    db.refresh(p)
    return created({"id": p.id, "name": p.name, "stages": []}, "Pipeline criado.")


@router.post("/pipelines/{pipeline_id}/stages")
def create_stage(pipeline_id: str, body: StageCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    if not db.query(CrmPipeline).filter(CrmPipeline.id == pipeline_id).first():
        raise HTTPException(404, "Pipeline não encontrado.")
    s = CrmStage(id=str(uuid.uuid4()), pipeline_id=pipeline_id, name=body.name,
                 description=body.description, color=body.color, sort_order=body.sort_order)
    db.add(s)
    db.commit()
    db.refresh(s)
    return created({"id": s.id, "name": s.name, "color": s.color, "sort_order": s.sort_order})


@router.delete("/stages/{stage_id}")
def delete_stage(stage_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    s = db.query(CrmStage).filter(CrmStage.id == stage_id).first()
    if not s:
        raise HTTPException(404, "Etapa não encontrada.")
    db.delete(s)
    db.commit()
    return ok(None, "Etapa removida.")


# ── Card routes ───────────────────────────────────────────────────────────────

@router.get("/pipelines/{pipeline_id}/cards")
def list_cards(pipeline_id: str, archived: bool = False, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    cards = (db.query(CrmCard)
             .filter(CrmCard.pipeline_id == pipeline_id, CrmCard.archived == archived)
             .order_by(CrmCard.stage_id, CrmCard.sort_order)
             .all())
    return ok([_card_to_dict(c, db) for c in cards])


@router.post("/pipelines/{pipeline_id}/cards")
def create_card(pipeline_id: str, body: CardCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    import json
    card = CrmCard(
        id=str(uuid.uuid4()), pipeline_id=pipeline_id, stage_id=body.stage_id,
        customer_id=body.customer_id, title=body.title, description=body.description,
        value=body.value, source=body.source, responsible=body.responsible,
        tags=json.dumps(body.tags), last_interaction_at=_now(),
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return created(_card_to_dict(card, db), "Card criado.")


@router.patch("/cards/{card_id}/move")
def move_card(card_id: str, body: CardMove, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    card = db.query(CrmCard).filter(CrmCard.id == card_id).first()
    if not card:
        raise HTTPException(404, "Card não encontrado.")
    card.stage_id = body.stage_id
    if body.sort_order is not None:
        card.sort_order = body.sort_order
    card.last_interaction_at = _now()
    card.updated_at = _now()
    db.commit()
    return ok(_card_to_dict(card, db))


@router.patch("/cards/{card_id}")
def update_card(card_id: str, body: CardUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    import json
    card = db.query(CrmCard).filter(CrmCard.id == card_id).first()
    if not card:
        raise HTTPException(404, "Card não encontrado.")
    if body.title is not None:
        card.title = body.title
    if body.description is not None:
        card.description = body.description
    if body.value is not None:
        card.value = body.value
    if body.source is not None:
        card.source = body.source
    if body.responsible is not None:
        card.responsible = body.responsible
    if body.tags is not None:
        card.tags = json.dumps(body.tags)
    if body.next_follow_up_at is not None:
        card.next_follow_up_at = datetime.fromisoformat(body.next_follow_up_at)
    card.updated_at = _now()
    db.commit()
    return ok(_card_to_dict(card, db))


@router.delete("/cards/{card_id}")
def delete_card(card_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    card = db.query(CrmCard).filter(CrmCard.id == card_id).first()
    if not card:
        raise HTTPException(404, "Card não encontrado.")
    db.delete(card)
    db.commit()
    return ok(None, "Card removido.")


# ── Task routes ───────────────────────────────────────────────────────────────

@router.get("/tasks")
def list_tasks(customer_id: str | None = None, status: str | None = None,
               db: Session = Depends(get_db), _=Depends(get_current_admin)):
    q = db.query(CrmTask)
    if customer_id:
        q = q.filter(CrmTask.customer_id == customer_id)
    if status:
        q = q.filter(CrmTask.status == status)
    tasks = q.order_by(CrmTask.due_date).all()
    return ok([{
        "id": t.id, "card_id": t.card_id, "customer_id": t.customer_id, "title": t.title,
        "description": t.description, "task_type": t.task_type, "responsible": t.responsible,
        "due_date": t.due_date.isoformat() if t.due_date else None, "priority": t.priority,
        "status": t.status, "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "created_at": t.created_at.isoformat(),
    } for t in tasks])


@router.post("/tasks")
def create_task(body: TaskCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    task = CrmTask(
        id=str(uuid.uuid4()), card_id=body.card_id, customer_id=body.customer_id,
        title=body.title, description=body.description, task_type=body.task_type,
        responsible=body.responsible, priority=body.priority,
        due_date=datetime.fromisoformat(body.due_date) if body.due_date else None,
    )
    db.add(task)
    db.commit()
    return created({"id": task.id, "title": task.title, "status": task.status}, "Tarefa criada.")


@router.patch("/tasks/{task_id}/complete")
def complete_task(task_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    task = db.query(CrmTask).filter(CrmTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "Tarefa não encontrada.")
    task.status = "completed"
    task.completed_at = _now()
    db.commit()
    return ok({"id": task.id, "status": "completed"})


# ── Customer Groups ───────────────────────────────────────────────────────────

@router.get("/groups")
def list_groups(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    groups = db.query(CustomerGroup).filter(CustomerGroup.active == True).all()  # noqa: E712
    result = []
    for g in groups:
        count = db.execute(
            text("SELECT COUNT(*) FROM customer_group_members WHERE group_id = :gid"),
            {"gid": g.id}
        ).scalar()
        result.append({
            "id": g.id, "name": g.name, "description": g.description,
            "group_type": g.group_type, "color": g.color, "icon": g.icon,
            "member_count": count, "created_at": g.created_at.isoformat(),
        })
    return ok(result)


@router.post("/groups")
def create_group(body: GroupCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    import json
    g = CustomerGroup(
        id=str(uuid.uuid4()), name=body.name, description=body.description,
        group_type=body.group_type, color=body.color, icon=body.icon,
    )
    db.add(g)
    db.flush()
    for rule in body.rules:
        db.execute(text(
            "INSERT INTO customer_group_rules (id, group_id, field, operator, value) VALUES (:id, :gid, :field, :op, :val)"
        ), {"id": str(uuid.uuid4()), "gid": g.id, "field": rule["field"], "op": rule["operator"], "val": str(rule["value"])})
    db.commit()
    return created({"id": g.id, "name": g.name}, "Grupo criado.")


@router.post("/groups/{group_id}/members/{customer_id}")
def add_member(group_id: str, customer_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    try:
        db.execute(text(
            "INSERT INTO customer_group_members (id, group_id, customer_id) VALUES (:id, :gid, :cid) ON CONFLICT DO NOTHING"
        ), {"id": str(uuid.uuid4()), "gid": group_id, "cid": customer_id})
        db.commit()
    except Exception:
        db.rollback()
    return ok(None, "Membro adicionado.")


@router.delete("/groups/{group_id}/members/{customer_id}")
def remove_member(group_id: str, customer_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    db.execute(text("DELETE FROM customer_group_members WHERE group_id=:gid AND customer_id=:cid"),
               {"gid": group_id, "cid": customer_id})
    db.commit()
    return ok(None, "Membro removido.")


# ── Customer Timeline ─────────────────────────────────────────────────────────

@router.get("/timeline/{customer_id}")
def customer_timeline(customer_id: str, limit: int = 50, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    events = (db.query(CustomerTimeline)
              .filter(CustomerTimeline.customer_id == customer_id)
              .order_by(CustomerTimeline.created_at.desc())
              .limit(limit).all())
    return ok([{
        "id": e.id, "event_type": e.event_type, "title": e.title,
        "description": e.description, "created_at": e.created_at.isoformat(),
    } for e in events])


@router.post("/timeline/{customer_id}")
def add_timeline_event(customer_id: str, body: dict, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    event = CustomerTimeline(
        id=str(uuid.uuid4()), customer_id=customer_id,
        event_type=body.get("event_type", "note"),
        title=body.get("title", "Observação"),
        description=body.get("description"),
    )
    db.add(event)
    db.commit()
    return created({"id": event.id}, "Evento adicionado.")


# ── CRM Dashboard ─────────────────────────────────────────────────────────────

@router.get("/dashboard")
def crm_dashboard(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    from sqlalchemy import func, text as sql_text
    from backend.models.customer import Customer
    total = db.query(func.count(Customer.id)).scalar() or 0
    active_cards = db.query(func.count(CrmCard.id)).filter(CrmCard.archived == False).scalar() or 0  # noqa: E712
    tasks_pending = db.query(func.count(CrmTask.id)).filter(CrmTask.status == "pending").scalar() or 0
    groups_count = db.query(func.count(CustomerGroup.id)).filter(CustomerGroup.active == True).scalar() or 0  # noqa: E712
    by_stage = db.execute(sql_text("""
        SELECT cs.name, COUNT(cc.id) as cards
        FROM crm_stages cs
        LEFT JOIN crm_cards cc ON cc.stage_id = cs.id AND cc.archived = FALSE
        WHERE cs.pipeline_id = 'delivery'
        GROUP BY cs.id, cs.name, cs.sort_order
        ORDER BY cs.sort_order
    """)).fetchall()
    return ok({
        "total_customers": total,
        "active_cards": active_cards,
        "tasks_pending": tasks_pending,
        "groups": groups_count,
        "pipeline_delivery": [{"stage": r[0], "cards": r[1]} for r in by_stage],
    })

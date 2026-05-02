"""CRM — Pipelines, Stages, Cards, Tasks, Customer Groups, Timeline."""
from __future__ import annotations
import json
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Column, String, Boolean, Integer, Float, Text, DateTime, Date, ForeignKey, func, text
from sqlalchemy.orm import Session

from backend.database import get_db, Base
from backend.models.crm import CustomerSegment, CustomerTag, CustomerTagAssignment
from backend.routes.admin_auth import get_current_admin
from backend.core.response import ok, created
from backend.services.customer_ai_service import (
    create_customer_ai_analysis_job,
    get_customer_ai_analysis_status,
    run_customer_ai_analysis_job,
)

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


class CrmCardNote(Base):
    __tablename__ = "crm_card_notes"
    id = Column(String, primary_key=True)
    card_id = Column(String, ForeignKey("crm_cards.id", ondelete="CASCADE"), nullable=False)
    author = Column(String(200), default="Admin")
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class CrmCardHistory(Base):
    __tablename__ = "crm_card_history"
    id = Column(String, primary_key=True)
    card_id = Column(String, ForeignKey("crm_cards.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(80), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class PipelineCreate(BaseModel):
    name: str
    description: str | None = None
    pipeline_type: str = "custom"


class PipelineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    pipeline_type: str | None = None


class StageCreate(BaseModel):
    name: str
    description: str | None = None
    color: str = "#2d3d56"
    sort_order: int = 0


class StageUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    sort_order: int | None = None
    order: int | None = None  # alias used by frontend
    description: str | None = None


class CardNoteCreate(BaseModel):
    body: str
    author: str = "Admin"


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
    pipeline_card_id: str | None = None  # alias for card_id used by the frontend
    customer_id: str | None = None
    title: str
    description: str | None = None
    task_type: str = "other"
    responsible: str | None = None
    due_date: str | None = None
    priority: str = "medium"
    status: str = "pending"


class GroupCreate(BaseModel):
    name: str
    description: str | None = None
    group_type: str = "manual"
    color: str = "#f97316"
    icon: str | None = None
    rules: list[dict] = []


class TagCreate(BaseModel):
    name: str
    description: str | None = None
    color: str = "#f97316"
    source: str = "manual"


class TagUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    status: str | None = None


class SegmentCreate(BaseModel):
    name: str
    description: str | None = None
    rules: list[dict] = []
    source: str = "manual"


class SegmentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    rules: list[dict] | None = None
    status: str | None = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now():
    return datetime.now(timezone.utc)


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return slug or uuid.uuid4().hex[:12]


def _tag_to_dict(tag: CustomerTag, member_count: int | None = None) -> dict:
    data = {
        "id": tag.id,
        "tenant_id": tag.tenant_id,
        "name": tag.name,
        "slug": tag.slug,
        "description": tag.description,
        "color": tag.color,
        "status": tag.status,
        "source": tag.source,
        "created_by": tag.created_by,
        "created_at": tag.created_at.isoformat() if tag.created_at else None,
        "updated_at": tag.updated_at.isoformat() if tag.updated_at else None,
    }
    if member_count is not None:
        data["member_count"] = member_count
    return data


def _segment_to_dict(segment: CustomerSegment) -> dict:
    try:
        rules = json.loads(segment.rules_json or "[]")
    except json.JSONDecodeError:
        rules = []
    return {
        "id": segment.id,
        "tenant_id": segment.tenant_id,
        "name": segment.name,
        "slug": segment.slug,
        "description": segment.description,
        "rules": rules,
        "status": segment.status,
        "source": segment.source,
        "created_by": segment.created_by,
        "created_at": segment.created_at.isoformat() if segment.created_at else None,
        "updated_at": segment.updated_at.isoformat() if segment.updated_at else None,
    }


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
            "stages": [{"id": s.id, "name": s.name, "color": s.color, "order": s.sort_order, "pipeline_id": p.id, "description": s.description} for s in stages],
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
    return created({"id": s.id, "name": s.name, "color": s.color, "order": s.sort_order, "pipeline_id": pipeline_id})


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


@router.post("/cards")
def create_card_shorthand(body: CardCreate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    """Shorthand — looks up pipeline_id from the stage."""
    stage = db.query(CrmStage).filter(CrmStage.id == body.stage_id).first()
    if not stage:
        raise HTTPException(404, "Etapa não encontrada.")
    return create_card(stage.pipeline_id, body, db, None)


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
    resolved_card_id = body.card_id or body.pipeline_card_id or None
    task = CrmTask(
        id=str(uuid.uuid4()), card_id=resolved_card_id, customer_id=body.customer_id,
        title=body.title, description=body.description, task_type=body.task_type,
        responsible=body.responsible, priority=body.priority,
        status=body.status or "pending",
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


class TaskUpdate(BaseModel):
    status: str | None = None
    title: str | None = None
    priority: str | None = None
    responsible: str | None = None
    description: str | None = None


@router.patch("/tasks/{task_id}")
def update_task(task_id: str, body: TaskUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    task = db.query(CrmTask).filter(CrmTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "Tarefa não encontrada.")
    if body.status is not None:
        task.status = body.status
        if body.status == "completed":
            task.completed_at = _now()
        else:
            task.completed_at = None
    if body.title is not None:
        task.title = body.title
    if body.priority is not None:
        task.priority = body.priority
    if body.responsible is not None:
        task.responsible = body.responsible
    if body.description is not None:
        task.description = body.description
    task.updated_at = _now()
    db.commit()
    return ok({"id": task.id, "status": task.status})


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    task = db.query(CrmTask).filter(CrmTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "Tarefa não encontrada.")
    db.delete(task)
    db.commit()
    return ok(None, "Tarefa removida.")


# ── Tags ──────────────────────────────────────────────────────────────────────

@router.get("/tags")
def list_tags(
    status: str | None = Query(default="active"),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    q = db.query(CustomerTag)
    if status:
        q = q.filter(CustomerTag.status == status)
    if search:
        term = f"%{search.strip().lower()}%"
        q = q.filter(func.lower(CustomerTag.name).like(term))
    tags = q.order_by(CustomerTag.name.asc()).all()

    counts = dict(
        db.query(CustomerTagAssignment.tag_id, func.count(CustomerTagAssignment.id))
        .group_by(CustomerTagAssignment.tag_id)
        .all()
    )
    return ok([_tag_to_dict(tag, int(counts.get(tag.id, 0))) for tag in tags])


@router.post("/tags")
def create_tag(body: TagCreate, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Nome da tag é obrigatório.")

    slug = _slugify(name)
    exists = (
        db.query(CustomerTag)
        .filter(CustomerTag.tenant_id == "default", CustomerTag.slug == slug)
        .first()
    )
    if exists:
        raise HTTPException(409, "Já existe uma tag com esse nome.")

    tag = CustomerTag(
        id=f"tag-{uuid.uuid4().hex[:10]}",
        tenant_id="default",
        name=name,
        slug=slug,
        description=body.description,
        color=body.color or "#f97316",
        source=body.source or "manual",
        created_by=getattr(admin, "name", None) or getattr(admin, "email", None),
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return created(_tag_to_dict(tag, 0), "Tag criada.")


@router.patch("/tags/{tag_id}")
def update_tag(tag_id: str, body: TagUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    tag = db.query(CustomerTag).filter(CustomerTag.id == tag_id).first()
    if not tag:
        raise HTTPException(404, "Tag não encontrada.")

    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(400, "Nome da tag é obrigatório.")
        slug = _slugify(name)
        exists = (
            db.query(CustomerTag)
            .filter(CustomerTag.tenant_id == tag.tenant_id, CustomerTag.slug == slug, CustomerTag.id != tag.id)
            .first()
        )
        if exists:
            raise HTTPException(409, "Já existe uma tag com esse nome.")
        tag.name = name
        tag.slug = slug
    if body.description is not None:
        tag.description = body.description
    if body.color is not None:
        tag.color = body.color
    if body.status is not None:
        tag.status = body.status
    tag.updated_at = _now()
    db.commit()
    return ok(_tag_to_dict(tag), "Tag atualizada.")


@router.delete("/tags/{tag_id}")
def inactive_tag(tag_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    tag = db.query(CustomerTag).filter(CustomerTag.id == tag_id).first()
    if not tag:
        raise HTTPException(404, "Tag não encontrada.")
    tag.status = "inactive"
    tag.updated_at = _now()
    db.commit()
    return ok(None, "Tag inativada.")


@router.get("/customers/{customer_id}/tags")
def list_customer_tags(customer_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    rows = (
        db.query(CustomerTag, CustomerTagAssignment)
        .join(CustomerTagAssignment, CustomerTagAssignment.tag_id == CustomerTag.id)
        .filter(CustomerTagAssignment.customer_id == customer_id)
        .order_by(CustomerTag.name.asc())
        .all()
    )
    return ok([
        {
            **_tag_to_dict(tag),
            "assignment_id": assignment.id,
            "assignment_source": assignment.source,
            "assigned_at": assignment.created_at.isoformat() if assignment.created_at else None,
        }
        for tag, assignment in rows
    ])


@router.post("/customers/{customer_id}/tags/{tag_id}")
def assign_tag(customer_id: str, tag_id: str, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    tag = db.query(CustomerTag).filter(CustomerTag.id == tag_id, CustomerTag.status == "active").first()
    if not tag:
        raise HTTPException(404, "Tag ativa não encontrada.")

    customer_exists = db.execute(text("SELECT 1 FROM customers WHERE id = :id"), {"id": customer_id}).first()
    if not customer_exists:
        raise HTTPException(404, "Cliente não encontrado.")

    assignment = CustomerTagAssignment(
        id=f"cta-{uuid.uuid4().hex[:12]}",
        tenant_id=tag.tenant_id,
        customer_id=customer_id,
        tag_id=tag.id,
        source="manual",
        created_by=getattr(admin, "name", None) or getattr(admin, "email", None),
    )
    db.add(assignment)
    try:
        db.flush()
        db.add(CustomerTimeline(
            id=str(uuid.uuid4()),
            customer_id=customer_id,
            event_type="tag_added",
            title=f"Tag adicionada: {tag.name}",
            description=f"Tag adicionada manualmente no CRM.",
            metadata_json=json.dumps({"tag_id": tag.id, "tag_name": tag.name}, ensure_ascii=False),
        ))
        db.commit()
    except Exception:
        db.rollback()
        return ok(_tag_to_dict(tag), "Cliente já possui esta tag.")

    return created(_tag_to_dict(tag), "Tag adicionada ao cliente.")


@router.delete("/customers/{customer_id}/tags/{tag_id}")
def remove_customer_tag(customer_id: str, tag_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    tag = db.query(CustomerTag).filter(CustomerTag.id == tag_id).first()
    deleted = (
        db.query(CustomerTagAssignment)
        .filter(CustomerTagAssignment.customer_id == customer_id, CustomerTagAssignment.tag_id == tag_id)
        .delete()
    )
    if deleted and tag:
        db.add(CustomerTimeline(
            id=str(uuid.uuid4()),
            customer_id=customer_id,
            event_type="tag_removed",
            title=f"Tag removida: {tag.name}",
            description="Tag removida manualmente no CRM.",
            metadata_json=json.dumps({"tag_id": tag.id, "tag_name": tag.name}, ensure_ascii=False),
        ))
    db.commit()
    return ok(None, "Tag removida do cliente.")


# ── Segments ─────────────────────────────────────────────────────────────────

@router.get("/segments")
def list_segments(
    status: str | None = Query(default="active"),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    q = db.query(CustomerSegment)
    if status:
        q = q.filter(CustomerSegment.status == status)
    return ok([_segment_to_dict(segment) for segment in q.order_by(CustomerSegment.name.asc()).all()])


@router.post("/segments")
def create_segment(body: SegmentCreate, db: Session = Depends(get_db), admin=Depends(get_current_admin)):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Nome do segmento é obrigatório.")
    slug = _slugify(name)
    exists = (
        db.query(CustomerSegment)
        .filter(CustomerSegment.tenant_id == "default", CustomerSegment.slug == slug)
        .first()
    )
    if exists:
        raise HTTPException(409, "Já existe um segmento com esse nome.")

    segment = CustomerSegment(
        id=f"seg-{uuid.uuid4().hex[:10]}",
        tenant_id="default",
        name=name,
        slug=slug,
        description=body.description,
        rules_json=json.dumps(body.rules or [], ensure_ascii=False),
        source=body.source or "manual",
        created_by=getattr(admin, "name", None) or getattr(admin, "email", None),
    )
    db.add(segment)
    db.commit()
    db.refresh(segment)
    return created(_segment_to_dict(segment), "Segmento criado.")


@router.patch("/segments/{segment_id}")
def update_segment(segment_id: str, body: SegmentUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    segment = db.query(CustomerSegment).filter(CustomerSegment.id == segment_id).first()
    if not segment:
        raise HTTPException(404, "Segmento não encontrado.")

    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(400, "Nome do segmento é obrigatório.")
        slug = _slugify(name)
        exists = (
            db.query(CustomerSegment)
            .filter(CustomerSegment.tenant_id == segment.tenant_id, CustomerSegment.slug == slug, CustomerSegment.id != segment.id)
            .first()
        )
        if exists:
            raise HTTPException(409, "Já existe um segmento com esse nome.")
        segment.name = name
        segment.slug = slug
    if body.description is not None:
        segment.description = body.description
    if body.rules is not None:
        segment.rules_json = json.dumps(body.rules, ensure_ascii=False)
    if body.status is not None:
        segment.status = body.status
    segment.updated_at = _now()
    db.commit()
    return ok(_segment_to_dict(segment), "Segmento atualizado.")


@router.delete("/segments/{segment_id}")
def inactive_segment(segment_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    segment = db.query(CustomerSegment).filter(CustomerSegment.id == segment_id).first()
    if not segment:
        raise HTTPException(404, "Segmento não encontrado.")
    segment.status = "inactive"
    segment.updated_at = _now()
    db.commit()
    return ok(None, "Segmento inativado.")


@router.post("/segments/{segment_id}/preview")
def preview_segment(segment_id: str, limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db), _=Depends(get_current_admin)):
    segment = db.query(CustomerSegment).filter(CustomerSegment.id == segment_id).first()
    if not segment:
        raise HTTPException(404, "Segmento não encontrado.")
    try:
        rules = json.loads(segment.rules_json or "[]")
    except json.JSONDecodeError:
        rules = []
    normalized_rules = [(rule.get("field"), rule.get("operator"), str(rule.get("value", ""))) for rule in rules]
    where_clause, valid = _build_evaluate_sql(normalized_rules)
    if not valid:
        return ok({"total": 0, "customers": [], "message": "Nenhuma condição válida para avaliar."})

    total = db.execute(text(f"SELECT COUNT(*) FROM customers WHERE {where_clause}")).scalar() or 0  # noqa: S608
    rows = db.execute(text(f"""
        SELECT id, name, email, phone, crm_status, total_orders, total_spent, avg_ticket, last_order_at
        FROM customers
        WHERE {where_clause}
        ORDER BY total_spent DESC NULLS LAST, name ASC
        LIMIT :limit
    """), {"limit": limit}).fetchall()  # noqa: S608

    return ok({
        "total": total,
        "customers": [
            {
                "id": row[0],
                "name": row[1],
                "email": row[2],
                "phone": row[3],
                "crm_status": row[4],
                "total_orders": row[5],
                "total_spent": row[6],
                "avg_ticket": row[7],
                "last_order_at": row[8],
            }
            for row in rows
        ],
    })


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
        rules = db.execute(
            text("SELECT field, operator, value FROM customer_group_rules WHERE group_id = :gid ORDER BY created_at"),
            {"gid": g.id}
        ).fetchall()
        result.append({
            "id": g.id, "name": g.name, "description": g.description,
            "group_type": g.group_type, "color": g.color, "icon": g.icon,
            "member_count": count, "created_at": g.created_at.isoformat(),
            "rules": [{"field": r[0], "operator": r[1], "value": r[2]} for r in rules],
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


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    color: str | None = None
    icon: str | None = None
    group_type: str | None = None
    rules: list[dict] | None = None


@router.patch("/groups/{group_id}")
def update_group(group_id: str, body: GroupUpdate, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    g = db.query(CustomerGroup).filter(CustomerGroup.id == group_id).first()
    if not g:
        raise HTTPException(404, "Grupo não encontrado.")
    if body.name is not None:
        g.name = body.name
    if body.description is not None:
        g.description = body.description
    if body.color is not None:
        g.color = body.color
    if body.icon is not None:
        g.icon = body.icon
    if body.group_type is not None:
        g.group_type = body.group_type
    if body.rules is not None:
        db.execute(text("DELETE FROM customer_group_rules WHERE group_id = :gid"), {"gid": group_id})
        for rule in body.rules:
            db.execute(text(
                "INSERT INTO customer_group_rules (id, group_id, field, operator, value) VALUES (:id, :gid, :field, :op, :val)"
            ), {"id": str(uuid.uuid4()), "gid": group_id, "field": rule["field"], "op": rule["operator"], "val": str(rule["value"])})
    g.updated_at = _now()
    db.commit()
    return ok({"id": g.id, "name": g.name})


@router.delete("/groups/{group_id}")
def delete_group(group_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    g = db.query(CustomerGroup).filter(CustomerGroup.id == group_id).first()
    if not g:
        raise HTTPException(404, "Grupo não encontrado.")
    g.active = False
    g.updated_at = _now()
    db.commit()
    return ok(None, "Grupo removido.")


@router.get("/customers/{customer_id}/groups")
def list_customer_groups(customer_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    rows = db.execute(
        text(
            """
            SELECT g.id, g.name, g.description, g.group_type, g.color, g.icon,
                   g.created_at, m.id AS member_id, m.source, m.added_at
            FROM customer_group_members m
            JOIN customer_groups g ON g.id = m.group_id
            WHERE m.customer_id = :customer_id AND g.active = TRUE
            ORDER BY g.name ASC
            """
        ),
        {"customer_id": customer_id},
    ).fetchall()
    return ok([
        {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "group_type": row[3],
            "color": row[4],
            "icon": row[5],
            "member_count": None,
            "created_at": row[6].isoformat() if row[6] else None,
            "member_id": row[7],
            "member_source": row[8],
            "added_at": row[9].isoformat() if row[9] else None,
        }
        for row in rows
    ])


# Numeric operators safe for dynamic SQL (value cast to float)
_NUMERIC_OPS = {">": ">", "<": "<", "=": "=", "!=": "!=", ">=": ">=", "<=": "<="}
# Safe column expressions mapped from rule field names
_FIELD_EXPRS = {
    "total_orders":      "COALESCE(total_orders, 0)",
    "total_spent":       "COALESCE(total_spent, 0.0)",
    "avg_ticket":        "COALESCE(avg_ticket, 0.0)",
    "last_order_days":   "COALESCE(EXTRACT(DAY FROM (NOW() - last_order_at))::int, 9999)",
    "days_without_order":"COALESCE(EXTRACT(DAY FROM (NOW() - last_order_at))::int, 9999)",
    "birth_month":       "EXTRACT(MONTH FROM birth_date)::int",
}
_TEXT_FIELDS = {"city", "neighborhood", "loyalty_tier", "customer_status",
                "payment_method", "product_ordered", "category_ordered",
                "coupon_used", "campaign_origin"}


def _build_evaluate_sql(rules: list) -> tuple[str, bool]:
    """Return (WHERE clause, is_valid). Uses only safe parameterized expressions."""
    clauses = []
    for field, operator, value in rules:
        if field in _FIELD_EXPRS:
            expr = _FIELD_EXPRS[field]
            if operator in _NUMERIC_OPS:
                try:
                    float(value)
                except (ValueError, TypeError):
                    continue
                clauses.append(f"({expr}) {_NUMERIC_OPS[operator]} {float(value)}")
        elif field in _TEXT_FIELDS:
            safe_val = value.replace("'", "''")
            if operator == "=":
                clauses.append(f"LOWER(COALESCE({field}, '')) = LOWER('{safe_val}')")
            elif operator == "!=":
                clauses.append(f"LOWER(COALESCE({field}, '')) != LOWER('{safe_val}')")
            elif operator == "contains":
                clauses.append(f"LOWER(COALESCE({field}, '')) LIKE '%{safe_val.lower()}%'")
    if not clauses:
        return "", False
    return " AND ".join(clauses), True


@router.post("/groups/{group_id}/evaluate")
def evaluate_group(group_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    """Re-evaluate dynamic rules and populate customer_group_members."""
    g = db.query(CustomerGroup).filter(CustomerGroup.id == group_id).first()
    if not g:
        raise HTTPException(404, "Grupo não encontrado.")
    if g.group_type != "dynamic":
        raise HTTPException(400, "Apenas grupos dinâmicos podem ser avaliados automaticamente.")

    rules = db.execute(
        text("SELECT field, operator, value FROM customer_group_rules WHERE group_id = :gid"),
        {"gid": group_id}
    ).fetchall()

    if not rules:
        return ok({"added": 0, "message": "Nenhuma regra definida."})

    where_clause, valid = _build_evaluate_sql(rules)
    if not valid:
        return ok({"added": 0, "message": "Nenhuma condição válida para avaliar."})

    customer_ids = db.execute(text(f"SELECT id FROM customers WHERE {where_clause}")).fetchall()  # noqa: S608

    added = 0
    for (cid,) in customer_ids:
        try:
            db.execute(text(
                "INSERT INTO customer_group_members (id, group_id, customer_id) VALUES (:id, :gid, :cid) ON CONFLICT DO NOTHING"
            ), {"id": str(uuid.uuid4()), "gid": group_id, "cid": cid})
            added += 1
        except Exception:
            pass
    db.commit()
    return ok({"added": added, "total": len(customer_ids), "message": f"{added} clientes adicionados ao grupo."})


@router.post("/groups/{group_id}/members/{customer_id}")
def add_member(group_id: str, customer_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    group = db.query(CustomerGroup).filter(CustomerGroup.id == group_id, CustomerGroup.active == True).first()  # noqa: E712
    if not group:
        raise HTTPException(404, "Grupo nao encontrado.")
    customer_exists = db.execute(text("SELECT 1 FROM customers WHERE id = :id"), {"id": customer_id}).first()
    if not customer_exists:
        raise HTTPException(404, "Cliente nao encontrado.")

    existing = db.execute(
        text("SELECT 1 FROM customer_group_members WHERE group_id = :gid AND customer_id = :cid"),
        {"gid": group_id, "cid": customer_id},
    ).first()
    if not existing:
        db.execute(text(
            "INSERT INTO customer_group_members (id, group_id, customer_id, source) VALUES (:id, :gid, :cid, 'manual') ON CONFLICT DO NOTHING"
        ), {"id": str(uuid.uuid4()), "gid": group_id, "cid": customer_id})
        db.add(CustomerTimeline(
            id=str(uuid.uuid4()),
            customer_id=customer_id,
            event_type="group_added",
            title=f"Grupo adicionado: {group.name}",
            description="Cliente adicionado manualmente ao grupo.",
            metadata_json=json.dumps({"group_id": group.id, "group_name": group.name}, ensure_ascii=False),
        ))
    db.commit()
    return ok(None, "Membro adicionado.")


@router.delete("/groups/{group_id}/members/{customer_id}")
def remove_member(group_id: str, customer_id: str, db: Session = Depends(get_db), _=Depends(get_current_admin)):
    group = db.query(CustomerGroup).filter(CustomerGroup.id == group_id).first()
    deleted = db.execute(text("DELETE FROM customer_group_members WHERE group_id=:gid AND customer_id=:cid"),
                         {"gid": group_id, "cid": customer_id}).rowcount
    if deleted and group:
        db.add(CustomerTimeline(
            id=str(uuid.uuid4()),
            customer_id=customer_id,
            event_type="group_removed",
            title=f"Grupo removido: {group.name}",
            description="Cliente removido manualmente do grupo.",
            metadata_json=json.dumps({"group_id": group.id, "group_name": group.name}, ensure_ascii=False),
        ))
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
def crm_dashboard(period: str = "30d", db: Session = Depends(get_db), _=Depends(get_current_admin)):
    from sqlalchemy import func, text as sql_text
    from backend.models.customer import Customer
    from datetime import datetime, timezone, timedelta

    # Period window
    _period_days = {"today": 1, "7d": 7, "30d": 30, "90d": 90}
    days = _period_days.get(period, 30)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    total = db.query(func.count(Customer.id)).scalar() or 0

    # New clients in period
    try:
        new_clients = db.execute(
            sql_text("SELECT COUNT(*) FROM customers WHERE created_at >= :since"),
            {"since": since},
        ).scalar() or 0
    except Exception:
        new_clients = 0

    # Recurring clients (more than 1 order)
    try:
        recurring = db.execute(
            sql_text("SELECT COUNT(*) FROM customers WHERE total_orders > 1"),
        ).scalar() or 0
    except Exception:
        recurring = 0

    # Inactive clients (no order in 60+ days)
    try:
        inactive_since = datetime.now(timezone.utc) - timedelta(days=60)
        inactive = db.execute(
            sql_text("SELECT COUNT(*) FROM customers WHERE last_order_at < :s OR last_order_at IS NULL"),
            {"s": inactive_since},
        ).scalar() or 0
    except Exception:
        inactive = 0

    # Birthday clients this month
    try:
        birthday = db.execute(
            sql_text("SELECT COUNT(*) FROM customers WHERE birth_date IS NOT NULL AND EXTRACT(MONTH FROM birth_date) = EXTRACT(MONTH FROM CURRENT_DATE)"),
        ).scalar() or 0
    except Exception:
        birthday = 0

    # Avg ticket
    try:
        avg_ticket = db.execute(
            sql_text("SELECT COALESCE(AVG(avg_ticket), 0) FROM customers WHERE avg_ticket > 0"),
        ).scalar() or 0.0
    except Exception:
        avg_ticket = 0.0

    # Revenue per client
    try:
        rev_per_client = db.execute(
            sql_text("SELECT COALESCE(AVG(total_spent), 0) FROM customers WHERE total_spent > 0"),
        ).scalar() or 0.0
    except Exception:
        rev_per_client = 0.0

    active_cards = db.query(func.count(CrmCard.id)).filter(CrmCard.archived == False).scalar() or 0  # noqa: E712

    # Open opportunities (cards with value > 0)
    try:
        open_opps = db.execute(
            sql_text("SELECT COUNT(*) FROM crm_cards WHERE archived = FALSE AND value > 0"),
        ).scalar() or 0
    except Exception:
        open_opps = 0

    tasks_pending = db.query(func.count(CrmTask.id)).filter(CrmTask.status == "pending").scalar() or 0

    # Overdue tasks
    try:
        overdue = db.execute(
            sql_text("SELECT COUNT(*) FROM crm_tasks WHERE status = 'pending' AND due_date < NOW()"),
        ).scalar() or 0
    except Exception:
        overdue = 0

    groups_count = db.query(func.count(CustomerGroup.id)).filter(CustomerGroup.active == True).scalar() or 0  # noqa: E712

    # Funnel
    first_pipeline = db.query(CrmPipeline).filter(CrmPipeline.active == True).order_by(CrmPipeline.sort_order).first()  # noqa: E712
    funnel_rows = []
    if first_pipeline:
        funnel_rows = db.execute(sql_text("""
            SELECT cs.name, COUNT(cc.id) as cards
            FROM crm_stages cs
            LEFT JOIN crm_cards cc ON cc.stage_id = cs.id AND cc.archived = FALSE
            WHERE cs.pipeline_id = :pid
            GROUP BY cs.id, cs.name, cs.sort_order
            ORDER BY cs.sort_order
        """), {"pid": first_pipeline.id}).fetchall()

    # Clients by neighborhood
    try:
        nbh_rows = db.execute(
            sql_text("""
                SELECT a.neighborhood as name, COUNT(DISTINCT c.id) as count
                FROM customers c
                JOIN addresses a ON a.customer_id = c.id
                WHERE a.neighborhood IS NOT NULL AND a.neighborhood <> ''
                GROUP BY a.neighborhood
                ORDER BY count DESC
                LIMIT 10
            """),
        ).fetchall()
        clients_by_neighborhood = [{"name": r[0], "count": r[1]} for r in nbh_rows]
    except Exception:
        clients_by_neighborhood = []

    # Clients by origin
    try:
        origin_rows = db.execute(
            sql_text("""
                SELECT COALESCE(source, 'Desconhecida') as name, COUNT(*) as count
                FROM customers
                GROUP BY source
                ORDER BY count DESC
                LIMIT 8
            """),
        ).fetchall()
        clients_by_origin = [{"name": r[0], "count": r[1]} for r in origin_rows]
    except Exception:
        clients_by_origin = []

    return ok({
        "total_clients": total,
        "new_clients": new_clients,
        "recurring_clients": recurring,
        "inactive_clients": inactive,
        "birthday_clients": birthday,
        "avg_ticket": float(avg_ticket),
        "revenue_per_client": float(rev_per_client),
        "pipeline_cards": active_cards,
        "open_opportunities": open_opps,
        "pending_tasks": tasks_pending,
        "overdue_tasks": overdue,
        "groups": groups_count,
        "funnel": [{"name": r[0], "count": r[1]} for r in funnel_rows],
        "clients_by_neighborhood": clients_by_neighborhood,
        "clients_by_origin": clients_by_origin,
    })


# ── Customer Intelligence ─────────────────────────────────────────────────────

@router.post("/analyze-all")
def analyze_all_customers(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    admin_name = getattr(admin, "name", None) or getattr(admin, "email", None)
    job, created_job = create_customer_ai_analysis_job(db, created_by=admin_name)
    if created_job:
        background_tasks.add_task(run_customer_ai_analysis_job, job["id"])
        return ok(job, "Analise em massa iniciada.")
    return ok(job, "Ja existe uma analise em massa em andamento.")


@router.get("/analysis/status")
def customer_intelligence_status(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _admin=Depends(get_current_admin),
):
    return ok(get_customer_ai_analysis_status(db, limit=limit))


# ── Pipeline PATCH / DELETE ───────────────────────────────────────────────────

@router.patch("/pipelines/{pipeline_id}")
def update_pipeline(pipeline_id: str, body: PipelineUpdate,
                    db: Session = Depends(get_db), _=Depends(get_current_admin)):
    p = db.query(CrmPipeline).filter(CrmPipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(404, "Pipeline não encontrado.")
    if body.name is not None:          p.name = body.name
    if body.description is not None:   p.description = body.description
    if body.pipeline_type is not None: p.pipeline_type = body.pipeline_type
    p.updated_at = _now()
    db.commit()
    return ok({"id": p.id, "name": p.name})


@router.delete("/pipelines/{pipeline_id}")
def delete_pipeline(pipeline_id: str, db: Session = Depends(get_db),
                    _=Depends(get_current_admin)):
    p = db.query(CrmPipeline).filter(CrmPipeline.id == pipeline_id).first()
    if not p:
        raise HTTPException(404, "Pipeline não encontrado.")
    p.active = False
    p.updated_at = _now()
    db.commit()
    return ok(None, "Pipeline removido.")


# ── Stage PATCH ───────────────────────────────────────────────────────────────

@router.patch("/stages/{stage_id}")
def update_stage(stage_id: str, body: StageUpdate,
                 db: Session = Depends(get_db), _=Depends(get_current_admin)):
    s = db.query(CrmStage).filter(CrmStage.id == stage_id).first()
    if not s:
        raise HTTPException(404, "Etapa não encontrada.")
    if body.name is not None:        s.name = body.name
    if body.color is not None:       s.color = body.color
    effective_order = body.order if body.order is not None else body.sort_order
    if effective_order is not None:  s.sort_order = effective_order
    if body.description is not None: s.description = body.description
    db.commit()
    return ok({"id": s.id, "name": s.name, "color": s.color, "order": s.sort_order, "pipeline_id": s.pipeline_id})


# ── Card Notes ────────────────────────────────────────────────────────────────

@router.get("/cards/{card_id}/notes")
def list_card_notes(card_id: str, db: Session = Depends(get_db),
                    _=Depends(get_current_admin)):
    notes = (
        db.query(CrmCardNote)
        .filter(CrmCardNote.card_id == card_id)
        .order_by(CrmCardNote.created_at.desc())
        .all()
    )
    return ok([{
        "id": n.id, "author": n.author, "body": n.body,
        "created_at": n.created_at.isoformat(),
    } for n in notes])


@router.post("/cards/{card_id}/notes")
def create_card_note(card_id: str, body: CardNoteCreate,
                     db: Session = Depends(get_db), _=Depends(get_current_admin)):
    if not db.query(CrmCard).filter(CrmCard.id == card_id).first():
        raise HTTPException(404, "Card não encontrado.")
    n = CrmCardNote(id=str(uuid.uuid4()), card_id=card_id,
                    author=body.author, body=body.body)
    db.add(n)
    # Also record in history
    h = CrmCardHistory(id=str(uuid.uuid4()), card_id=card_id,
                       event_type="note_added",
                       description=f"{body.author} adicionou uma nota.")
    db.add(h)
    db.commit()
    return created({"id": n.id, "body": n.body, "created_at": n.created_at.isoformat()},
                   "Nota adicionada.")


# ── Card History ──────────────────────────────────────────────────────────────

@router.get("/cards/{card_id}/history")
def list_card_history(card_id: str, db: Session = Depends(get_db),
                      _=Depends(get_current_admin)):
    rows = (
        db.query(CrmCardHistory)
        .filter(CrmCardHistory.card_id == card_id)
        .order_by(CrmCardHistory.created_at.desc())
        .limit(50)
        .all()
    )
    return ok([{
        "id": r.id, "event_type": r.event_type, "description": r.description,
        "created_at": r.created_at.isoformat(),
    } for r in rows])

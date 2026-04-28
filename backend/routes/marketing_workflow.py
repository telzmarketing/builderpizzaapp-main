"""
Marketing Workflow de Aprovação — CRUD completo.

Endpoints:
  GET    /marketing/workflows
  POST   /marketing/workflows
  GET    /marketing/workflows/{id}
  PATCH  /marketing/workflows/{id}
  DELETE /marketing/workflows/{id}
  POST   /marketing/workflows/{id}/submit
  POST   /marketing/workflows/{id}/approve
  POST   /marketing/workflows/{id}/reject
  POST   /marketing/workflows/{id}/request_adjustments
  POST   /marketing/workflows/{id}/cancel
  POST   /marketing/workflows/{id}/comments
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from backend.routes.admin_auth import get_current_admin as require_admin
from backend.core.response import ok
from backend.database import SessionLocal

router = APIRouter(prefix="/marketing/workflows", tags=["marketing-workflow"])

# ── helpers ───────────────────────────────────────────────────────────────────

def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_workflow(db, wf_id: str) -> dict:
    row = db.execute(
        text("SELECT * FROM marketing_workflows WHERE id = :id"),
        {"id": wf_id},
    ).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Workflow não encontrado.")
    wf = dict(row)
    comments = db.execute(
        text("SELECT * FROM marketing_workflow_comments WHERE workflow_id = :id ORDER BY created_at ASC"),
        {"id": wf_id},
    ).mappings().all()
    wf["comments"] = [dict(c) for c in comments]
    return wf


def _serialize(wf: dict) -> dict:
    for k, v in wf.items():
        if isinstance(v, datetime):
            wf[k] = v.isoformat()
    return wf


# ── Pydantic models ───────────────────────────────────────────────────────────

class WorkflowCreate(BaseModel):
    name: str
    campaign_type: str = "whatsapp"
    audience_description: Optional[str] = None
    template_preview: Optional[str] = None
    scheduled_at: Optional[str] = None
    budget: Optional[float] = None
    status: str = "draft"


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    campaign_type: Optional[str] = None
    audience_description: Optional[str] = None
    template_preview: Optional[str] = None
    scheduled_at: Optional[str] = None
    budget: Optional[float] = None


class CommentCreate(BaseModel):
    body: str
    author: Optional[str] = "Admin"


class ActionWithComment(BaseModel):
    comment: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("")
def list_workflows(db=Depends(_get_db), _=Depends(require_admin)):
    rows = db.execute(
        text("SELECT * FROM marketing_workflows ORDER BY created_at DESC")
    ).mappings().all()
    result = []
    for row in rows:
        wf = dict(row)
        comments = db.execute(
            text("SELECT * FROM marketing_workflow_comments WHERE workflow_id = :id ORDER BY created_at ASC"),
            {"id": wf["id"]},
        ).mappings().all()
        wf["comments"] = [dict(c) for c in comments]
        result.append(_serialize(wf))
    return ok(result)


@router.post("")
def create_workflow(body: WorkflowCreate, db=Depends(_get_db), admin=Depends(require_admin)):
    wf_id = str(uuid.uuid4())
    admin_name = getattr(admin, "name", None) or getattr(admin, "email", "Admin")
    db.execute(
        text("""
            INSERT INTO marketing_workflows
              (id, name, campaign_type, status, audience_description,
               template_preview, scheduled_at, budget, created_by, created_at, updated_at)
            VALUES
              (:id, :name, :campaign_type, :status, :audience_description,
               :template_preview, :scheduled_at, :budget, :created_by, NOW(), NOW())
        """),
        {
            "id": wf_id,
            "name": body.name,
            "campaign_type": body.campaign_type,
            "status": body.status,
            "audience_description": body.audience_description,
            "template_preview": body.template_preview,
            "scheduled_at": body.scheduled_at,
            "budget": body.budget,
            "created_by": admin_name,
        },
    )
    db.commit()
    return ok(_serialize(_fetch_workflow(db, wf_id)))


@router.get("/{wf_id}")
def get_workflow(wf_id: str, db=Depends(_get_db), _=Depends(require_admin)):
    return ok(_serialize(_fetch_workflow(db, wf_id)))


@router.patch("/{wf_id}")
def update_workflow(wf_id: str, body: WorkflowUpdate, db=Depends(_get_db), _=Depends(require_admin)):
    _fetch_workflow(db, wf_id)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Nenhum campo para atualizar.")
    updates["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    db.execute(text(f"UPDATE marketing_workflows SET {set_clause} WHERE id = :wf_id"), {**updates, "wf_id": wf_id})
    db.commit()
    return ok(_serialize(_fetch_workflow(db, wf_id)))


@router.delete("/{wf_id}")
def delete_workflow(wf_id: str, db=Depends(_get_db), _=Depends(require_admin)):
    _fetch_workflow(db, wf_id)
    db.execute(text("DELETE FROM marketing_workflows WHERE id = :id"), {"id": wf_id})
    db.commit()
    return ok({"deleted": True})


# ── Status transitions ────────────────────────────────────────────────────────

def _transition(wf_id: str, new_status: str, db, admin, comment: Optional[str] = None,
                set_approver: bool = False):
    wf = _fetch_workflow(db, wf_id)
    params: dict = {"status": new_status, "updated_at": _now(), "wf_id": wf_id}
    extra = "status = :status, updated_at = :updated_at"
    if set_approver:
        admin_name = getattr(admin, "name", None) or getattr(admin, "email", "Admin")
        extra += ", approved_by = :approved_by, approved_at = NOW()"
        params["approved_by"] = admin_name
    db.execute(text(f"UPDATE marketing_workflows SET {extra} WHERE id = :wf_id"), params)
    if comment:
        admin_name = getattr(admin, "name", None) or getattr(admin, "email", "Admin")
        db.execute(
            text("INSERT INTO marketing_workflow_comments (id, workflow_id, author, body, created_at) VALUES (:id, :wf_id, :author, :body, NOW())"),
            {"id": str(uuid.uuid4()), "wf_id": wf_id, "author": admin_name, "body": comment},
        )
    db.commit()
    return ok(_serialize(_fetch_workflow(db, wf_id)))


@router.post("/{wf_id}/submit")
def submit_workflow(wf_id: str, body: ActionWithComment = ActionWithComment(), db=Depends(_get_db), admin=Depends(require_admin)):
    return _transition(wf_id, "pending_approval", db, admin, body.comment)


@router.post("/{wf_id}/approve")
def approve_workflow(wf_id: str, body: ActionWithComment = ActionWithComment(), db=Depends(_get_db), admin=Depends(require_admin)):
    return _transition(wf_id, "approved", db, admin, body.comment, set_approver=True)


@router.post("/{wf_id}/reject")
def reject_workflow(wf_id: str, body: ActionWithComment = ActionWithComment(), db=Depends(_get_db), admin=Depends(require_admin)):
    return _transition(wf_id, "rejected", db, admin, body.comment)


@router.post("/{wf_id}/request_adjustments")
def request_adjustments(wf_id: str, body: ActionWithComment = ActionWithComment(), db=Depends(_get_db), admin=Depends(require_admin)):
    return _transition(wf_id, "adjustment_requested", db, admin, body.comment)


@router.post("/{wf_id}/cancel")
def cancel_workflow(wf_id: str, body: ActionWithComment = ActionWithComment(), db=Depends(_get_db), admin=Depends(require_admin)):
    return _transition(wf_id, "cancelled", db, admin, body.comment)


# ── Comments ──────────────────────────────────────────────────────────────────

@router.post("/{wf_id}/comments")
def add_comment(wf_id: str, body: CommentCreate, db=Depends(_get_db), admin=Depends(require_admin)):
    _fetch_workflow(db, wf_id)
    admin_name = getattr(admin, "name", None) or getattr(admin, "email", "Admin")
    db.execute(
        text("INSERT INTO marketing_workflow_comments (id, workflow_id, author, body, created_at) VALUES (:id, :wf_id, :author, :body, NOW())"),
        {"id": str(uuid.uuid4()), "wf_id": wf_id, "author": body.author or admin_name, "body": body.body},
    )
    db.commit()
    return ok(_serialize(_fetch_workflow(db, wf_id)))

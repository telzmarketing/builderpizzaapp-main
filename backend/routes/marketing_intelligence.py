from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.response import ok
from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.schemas.marketing_intelligence import (
    MarketingGoalCreate,
    MarketingGoalStatusUpdate,
    MarketingGoalUpdate,
    MarketingIntelligencePeriod,
    MarketingTimelineEventCreate,
    MarketingTimelineEventUpdate,
)
from backend.services.marketing_intelligence_service import MarketingIntelligenceService


router = APIRouter(
    prefix="/marketing-intelligence",
    tags=["marketing-intelligence"],
    dependencies=[Depends(get_current_admin)],
)


def _service(db: Session) -> MarketingIntelligenceService:
    return MarketingIntelligenceService(db)


@router.get("/dashboard")
def dashboard(
    period: MarketingIntelligencePeriod = Query(default="30d"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return ok(_service(db).dashboard(period=period, date_from=date_from, date_to=date_to))


@router.get("/campaigns")
def campaigns(
    period: MarketingIntelligencePeriod = Query(default="30d"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return ok(_service(db).campaigns(period=period, date_from=date_from, date_to=date_to, limit=limit))


@router.get("/channels")
def channels(
    period: MarketingIntelligencePeriod = Query(default="30d"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return ok(_service(db).channels(period=period, date_from=date_from, date_to=date_to, limit=limit))


@router.get("/funnel")
def funnel(
    period: MarketingIntelligencePeriod = Query(default="30d"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return ok(_service(db).funnel(period=period, date_from=date_from, date_to=date_to))


@router.get("/products")
def products(
    period: MarketingIntelligencePeriod = Query(default="30d"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return ok(_service(db).products(period=period, date_from=date_from, date_to=date_to, limit=limit))


@router.get("/promotions")
def promotions(
    period: MarketingIntelligencePeriod = Query(default="30d"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return ok(_service(db).promotions(period=period, date_from=date_from, date_to=date_to, limit=limit))


@router.get("/planning")
def planning(
    status: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
):
    return ok(_service(db).planning(status=status, date_from=date_from, date_to=date_to, limit=limit))


@router.get("/goals")
def goals(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
):
    return ok(_service(db).list_goals(status=status, limit=limit))


@router.post("/goals")
def create_goal(
    body: MarketingGoalCreate,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    return ok(_service(db).create_goal(body, created_by=getattr(current_admin, "id", None)), "Meta criada.")


@router.put("/goals/{goal_id}")
def update_goal(
    goal_id: str,
    body: MarketingGoalUpdate,
    db: Session = Depends(get_db),
):
    return ok(_service(db).update_goal(goal_id, body), "Meta atualizada.")


@router.patch("/goals/{goal_id}/status")
def update_goal_status(
    goal_id: str,
    body: MarketingGoalStatusUpdate,
    db: Session = Depends(get_db),
):
    return ok(_service(db).update_goal_status(goal_id, body), "Status da meta atualizado.")


@router.delete("/goals/{goal_id}")
def delete_goal(
    goal_id: str,
    db: Session = Depends(get_db),
):
    _service(db).delete_goal(goal_id)
    return ok(None, "Meta excluida.")


@router.get("/timeline")
def timeline(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    event_type: str | None = Query(default=None),
    category: str | None = Query(default=None),
    impact_level: str | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=300),
    db: Session = Depends(get_db),
):
    return ok(
        _service(db).list_timeline(
            date_from=date_from,
            date_to=date_to,
            event_type=event_type,
            category=category,
            impact_level=impact_level,
            search=search,
            limit=limit,
        )
    )


@router.post("/timeline")
def create_timeline_event(
    body: MarketingTimelineEventCreate,
    db: Session = Depends(get_db),
    current_admin=Depends(get_current_admin),
):
    return ok(_service(db).create_timeline_event(body, created_by=getattr(current_admin, "id", None)), "Evento criado.")


@router.put("/timeline/{event_id}")
def update_timeline_event(
    event_id: str,
    body: MarketingTimelineEventUpdate,
    db: Session = Depends(get_db),
):
    return ok(_service(db).update_timeline_event(event_id, body), "Evento atualizado.")


@router.delete("/timeline/{event_id}")
def delete_timeline_event(
    event_id: str,
    db: Session = Depends(get_db),
):
    _service(db).delete_timeline_event(event_id)
    return ok(None, "Evento excluido.")

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.response import ok
from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.schemas.bi import BIInsightStatusUpdate, GranularityKey, PeriodKey
from backend.services.business_intelligence_service import BusinessIntelligenceService

router = APIRouter(prefix="/bi", tags=["business-intelligence"], dependencies=[Depends(get_current_admin)])


def _service(db: Session) -> BusinessIntelligenceService:
    return BusinessIntelligenceService(db)


@router.get("/dashboard")
def dashboard(
    period: PeriodKey = Query(default="30d"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return ok(_service(db).dashboard(period=period, date_from=date_from, date_to=date_to))


@router.get("/overview")
def overview(
    period: PeriodKey = Query(default="30d"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    service = _service(db)
    bounds = service.resolve_bounds(period, date_from, date_to)
    data = service.get_overview(**bounds)
    return ok({**service.period_payload(bounds), **data})


@router.get("/sales")
def sales(
    period: PeriodKey = Query(default="30d"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    granularity: GranularityKey = Query(default="day"),
    db: Session = Depends(get_db),
):
    service = _service(db)
    bounds = service.resolve_bounds(period, date_from, date_to)
    return ok(service.get_sales(**bounds, granularity=granularity))


@router.get("/customers")
def customers(
    period: PeriodKey = Query(default="30d"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    service = _service(db)
    bounds = service.resolve_bounds(period, date_from, date_to)
    return ok(service.get_customers(**bounds))


@router.get("/products")
def products(
    period: PeriodKey = Query(default="30d"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = _service(db)
    bounds = service.resolve_bounds(period, date_from, date_to)
    return ok(service.get_products(**bounds, limit=limit))


@router.get("/marketing")
def marketing(
    period: PeriodKey = Query(default="30d"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    service = _service(db)
    bounds = service.resolve_bounds(period, date_from, date_to)
    return ok(service.get_marketing(**bounds))


@router.get("/operations")
def operations(
    period: PeriodKey = Query(default="30d"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    service = _service(db)
    bounds = service.resolve_bounds(period, date_from, date_to)
    return ok(service.get_operations(**bounds))


@router.get("/funnel")
def funnel(
    period: PeriodKey = Query(default="30d"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    service = _service(db)
    bounds = service.resolve_bounds(period, date_from, date_to)
    return ok(service.get_marketing(**bounds)["funnel"])


@router.get("/insights")
def insights(
    period: PeriodKey = Query(default="30d"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return ok(_service(db).dashboard(period=period, date_from=date_from, date_to=date_to)["insights"])


@router.get("/insights/latest")
def latest_insights(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return ok(_service(db).latest_insights(status=status, limit=limit))


@router.patch("/insights/{insight_id}/status")
def update_insight_status(
    insight_id: str,
    body: BIInsightStatusUpdate,
    db: Session = Depends(get_db),
):
    return ok(_service(db).update_insight_status(insight_id, body.status), "Status do insight atualizado.")


@router.get("/recommendations")
def recommendations(
    period: PeriodKey = Query(default="30d"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return ok(_service(db).dashboard(period=period, date_from=date_from, date_to=date_to)["recommendations"])


@router.post("/run-analysis")
def run_analysis(
    period: PeriodKey = Query(default="30d"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return ok(_service(db).run_analysis(period=period, date_from=date_from, date_to=date_to))

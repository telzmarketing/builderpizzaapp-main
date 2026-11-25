from datetime import date
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import created, err, ok
from backend.database import get_db
from backend.core.tenant_runtime import resolve_public_tenant_context
from backend.schemas.strategic_campaign import StrategicCampaignCreate, StrategicCampaignOut, StrategicCampaignUpdate, StrategicCampaignVersionOut, StrategicOfferCreate, StrategicOfferOut, StrategicOfferUpdate
from backend.services.strategic_campaign_service import StrategicCampaignService
from backend.services.strategic_campaign_metrics_service import StrategicCampaignMetricsService

router = APIRouter(prefix="/strategic-campaigns", tags=["strategic-campaigns"])
view = require_rbac_permission("marketing", "view")
edit = require_rbac_permission("marketing", "edit")


@router.get("")
def list_campaigns(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    return StrategicCampaignService(db, actor.tenant_id).list()


@router.post("", status_code=201)
def create_campaign(body: StrategicCampaignCreate, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        return created(StrategicCampaignService(db, actor.tenant_id).create(body))
    except DomainError as exc:
        return err(exc)


@router.get("/public/{slug}")
def public_campaign(slug: str, request: Request, db: Session = Depends(get_db)):
    context = resolve_public_tenant_context(request, db)
    if context is None:
        raise DomainError("Tenant público não resolvido.", code="PublicTenantRequired")
    return ok(StrategicCampaignService(db, context.tenant_id).get_public(slug))


@router.get("/{campaign_id}")
def get_campaign(campaign_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    try:
        return StrategicCampaignService(db, actor.tenant_id)._campaign(campaign_id)
    except DomainError as exc:
        return err(exc)


@router.get("/{campaign_id}/metrics")
def campaign_metrics(
    campaign_id: str,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(view),
):
    try:
        return ok(StrategicCampaignMetricsService(db, actor.tenant_id).get(campaign_id, date_from, date_to))
    except LookupError as exc:
        raise DomainError(str(exc), code="StrategicCampaignNotFound") from exc
    except ValueError as exc:
        raise DomainError(str(exc), code="InvalidMetricsPeriod") from exc


@router.put("/{campaign_id}")
def update_campaign(campaign_id: str, body: StrategicCampaignUpdate, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        return StrategicCampaignService(db, actor.tenant_id).update(campaign_id, body)
    except DomainError as exc:
        return err(exc)


@router.post("/{campaign_id}/offers", status_code=201)
def add_offer(campaign_id: str, body: StrategicOfferCreate, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        return created(StrategicCampaignService(db, actor.tenant_id).add_offer(campaign_id, body))
    except DomainError as exc:
        return err(exc)


@router.put("/offers/{offer_id}")
def update_offer(offer_id: str, body: StrategicOfferUpdate, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        return StrategicCampaignService(db, actor.tenant_id).update_offer(offer_id, body)
    except DomainError as exc:
        return err(exc)


@router.post("/{campaign_id}/publish")
def publish_campaign(campaign_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        return StrategicCampaignService(db, actor.tenant_id).publish(campaign_id)
    except DomainError as exc:
        return err(exc)

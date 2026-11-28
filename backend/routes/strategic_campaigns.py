from datetime import date
from typing import Literal
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import created, err, ok
from backend.database import get_db
from backend.core.tenant_runtime import resolve_public_tenant_context
from backend.schemas.strategic_campaign import (
    StrategicCampaignCreate,
    StrategicCampaignDuplicate,
    StrategicCampaignOut,
    StrategicCampaignPublicOut,
    StrategicCampaignUpdate,
    StrategicCampaignVersionOut,
    StrategicOfferCreate,
    StrategicOfferDuplicate,
    StrategicOfferOut,
    StrategicOfferReorder,
    StrategicOfferUpdate,
    StrategicAvailableCampaignOut,
    StrategicOfferConfigurationOut,
)
from backend.schemas.strategic_campaign_capacity import (
    StrategicCampaignAvailabilityOut,
    StrategicCapacitySlotCreate,
    StrategicCapacitySlotOut,
    StrategicCapacitySlotUpdate,
    StrategicReservationCreate,
    StrategicReservationExpirationResult,
    StrategicOperationalReleaseResult,
    StrategicReservationOrderBinding,
    StrategicReservationOut,
    StrategicReservationRelease,
)
from backend.schemas.strategic_campaign_automation import StrategicCampaignAutomationOut, StrategicCampaignAutomationUpdate
from backend.services.strategic_campaign_capacity_service import StrategicCampaignCapacityService
from backend.services.strategic_campaign_service import StrategicCampaignService
from backend.services.strategic_offer_composition_service import StrategicOfferCompositionService
from backend.services.strategic_campaign_metrics_service import StrategicCampaignMetricsService
from backend.services.strategic_campaign_automation_service import StrategicCampaignAutomationService

router = APIRouter(prefix="/strategic-campaigns", tags=["strategic-campaigns"])
view = require_rbac_permission("marketing", "view")
edit = require_rbac_permission("marketing", "edit")
publish = require_rbac_permission("marketing", "publish")


@router.get("")
def list_campaigns(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    return StrategicCampaignService(db, actor.tenant_id).list()


@router.post("", status_code=201)
def create_campaign(body: StrategicCampaignCreate, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        return created(StrategicCampaignService(db, actor.tenant_id).create(body))
    except DomainError as exc:
        return err(exc)


@router.get("/available")
def available_campaigns(
    entry_channel: Literal["landing_page", "pdv", "operations", "phone", "whatsapp", "counter"] = Query(...),
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(view),
):
    rows = StrategicOfferCompositionService(db, actor.tenant_id).available_campaigns(entry_channel)
    return ok([StrategicAvailableCampaignOut.model_validate(row) for row in rows])


@router.get("/offers/{offer_id}/configuration")
def offer_configuration(
    offer_id: str,
    campaign_version: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(view),
):
    try:
        document = StrategicOfferCompositionService(db, actor.tenant_id).configuration(offer_id, campaign_version)
        return ok(StrategicOfferConfigurationOut.model_validate(document))
    except DomainError as exc:
        return err(exc)


@router.get("/{campaign_id}/available-offers")
def available_offers(
    campaign_id: str,
    entry_channel: Literal["landing_page", "pdv", "operations", "phone", "whatsapp", "counter"] = Query(...),
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(view),
):
    try:
        return ok(StrategicOfferCompositionService(db, actor.tenant_id).available_offers(campaign_id, entry_channel))
    except DomainError as exc:
        return err(exc)


@router.get("/public/offers/{offer_id}/configuration")
def public_offer_configuration(
    offer_id: str,
    request: Request,
    campaign_version: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
):
    context = resolve_public_tenant_context(request, db)
    if context is None:
        raise DomainError("Tenant publico nao resolvido.", code="PublicTenantRequired")
    document = StrategicOfferCompositionService(db, context.tenant_id).configuration(offer_id, campaign_version)
    return ok(StrategicOfferConfigurationOut.model_validate(document))


@router.get("/public/{slug}")
def public_campaign(slug: str, request: Request, db: Session = Depends(get_db)):
    context = resolve_public_tenant_context(request, db)
    if context is None:
        raise DomainError("Tenant público não resolvido.", code="PublicTenantRequired")
    public_document = StrategicCampaignService(db, context.tenant_id).get_public(slug)
    availability = StrategicOfferCompositionService(db, context.tenant_id).available_offers(
        public_document.id, "landing_page",
    )
    by_offer_id = {row["id"]: row for row in availability}
    public_document = public_document.model_copy(update={
        "offers": [
            offer.model_copy(update={
                # Keep every active offer from the published snapshot on the
                # landing page. Availability is a purchase guard, not a
                # visibility filter: an offer can be outside its sale window
                # or temporarily unavailable and still belong in the page.
                "available": by_offer_id.get(offer.id, {}).get("available", False),
                "remaining_quantity": by_offer_id.get(offer.id, {}).get("remaining_quantity"),
            })
            for offer in public_document.offers
            if offer.active and offer.archived_at is None
        ],
    })
    return ok(StrategicCampaignPublicOut.model_validate(public_document))


@router.get("/{campaign_id}")
def get_campaign(campaign_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    try:
        campaign = StrategicCampaignService(db, actor.tenant_id)._campaign(campaign_id)
        return ok(StrategicCampaignOut.model_validate(campaign, from_attributes=True))
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


@router.get("/{campaign_id}/automations")
def list_campaign_automations(campaign_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    try:
        rows = StrategicCampaignAutomationService(db, actor.tenant_id).list(campaign_id)
        return ok([StrategicCampaignAutomationOut.model_validate(row) for row in rows])
    except DomainError as exc:
        return err(exc)


@router.post("/{campaign_id}/automations/generate")
def generate_campaign_automations(campaign_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        rows = StrategicCampaignAutomationService(db, actor.tenant_id).generate(campaign_id)
        return ok([StrategicCampaignAutomationOut.model_validate(row) for row in rows])
    except DomainError as exc:
        return err(exc)


@router.patch("/{campaign_id}/automations/{automation_id}")
def update_campaign_automation(
    campaign_id: str,
    automation_id: str,
    body: StrategicCampaignAutomationUpdate,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(edit),
):
    try:
        row = StrategicCampaignAutomationService(db, actor.tenant_id).update(campaign_id, automation_id, body)
        return ok(StrategicCampaignAutomationOut.model_validate(row))
    except DomainError as exc:
        return err(exc)


@router.put("/{campaign_id}")
def update_campaign(campaign_id: str, body: StrategicCampaignUpdate, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        return StrategicCampaignService(db, actor.tenant_id).update(campaign_id, body)
    except DomainError as exc:
        return err(exc)


@router.post("/{campaign_id}/duplicate", status_code=201)
def duplicate_campaign(campaign_id: str, body: StrategicCampaignDuplicate, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        duplicated = StrategicCampaignService(db, actor.tenant_id).duplicate_campaign(campaign_id, body)
        return created(StrategicCampaignOut.model_validate(duplicated))
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
        # Do not expose the SQLAlchemy row directly.  Besides leaking ORM
        # internals, that makes the response dependent on lazy relationship
        # state and can turn a successful image update into a generic 500 while
        # the UI reloads the offer.
        offer = StrategicCampaignService(db, actor.tenant_id).update_offer(offer_id, body)
        return ok(StrategicOfferOut.model_validate(offer, from_attributes=True))
    except DomainError as exc:
        return err(exc)


@router.post("/offers/{offer_id}/duplicate", status_code=201)
def duplicate_offer(offer_id: str, body: StrategicOfferDuplicate, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        duplicated = StrategicCampaignService(db, actor.tenant_id).duplicate_offer(offer_id, body)
        return created(StrategicOfferOut.model_validate(duplicated))
    except DomainError as exc:
        return err(exc)


@router.put("/{campaign_id}/offers/reorder")
def reorder_offers(campaign_id: str, body: StrategicOfferReorder, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        ordered = StrategicCampaignService(db, actor.tenant_id).reorder_offers(campaign_id, body)
        return ok([StrategicOfferOut.model_validate(offer) for offer in ordered])
    except DomainError as exc:
        return err(exc)


@router.post("/offers/{offer_id}/archive")
def archive_offer(offer_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    try:
        archived = StrategicCampaignService(db, actor.tenant_id).archive_offer(offer_id)
        return ok(StrategicOfferOut.model_validate(archived))
    except DomainError as exc:
        return err(exc)


@router.post("/{campaign_id}/publish")
def publish_campaign(campaign_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(publish)):
    try:
        published = StrategicCampaignService(db, actor.tenant_id).publish(campaign_id)
        return StrategicCampaignVersionOut.model_validate(published)
    except DomainError as exc:
        return err(exc)


@router.get("/{campaign_id}/capacity-slots")
def list_capacity_slots(campaign_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    try:
        rows = StrategicCampaignCapacityService(db, actor.tenant_id).list_slots(campaign_id)
        return ok([StrategicCapacitySlotOut.model_validate(row) for row in rows])
    except DomainError as exc:
        return err(exc)


@router.get("/public/{campaign_id}/availability", response_model=None)
def public_campaign_availability(
    campaign_id: str,
    request: Request,
    offer_id: str | None = Query(default=None, min_length=1, max_length=120),
    db: Session = Depends(get_db),
):
    context = resolve_public_tenant_context(request, db)
    if context is None:
        raise DomainError("Tenant publico nao resolvido.", code="PublicTenantRequired")
    document = StrategicCampaignCapacityService(db, context.tenant_id).public_availability(
        campaign_id,
        offer_id,
    )
    return ok(StrategicCampaignAvailabilityOut.model_validate(document))


@router.post("/public/{campaign_id}/reservations", status_code=201)
def create_public_strategic_reservation(
    campaign_id: str,
    body: StrategicReservationCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    context = resolve_public_tenant_context(request, db)
    if context is None:
        raise DomainError("Tenant publico nao resolvido.", code="PublicTenantRequired")
    try:
        row = StrategicCampaignCapacityService(db, context.tenant_id).create_reservation(campaign_id, body)
        return created(StrategicReservationOut.model_validate(row))
    except DomainError as exc:
        return err(exc)


@router.post("/{campaign_id}/capacity-slots", status_code=201)
def create_capacity_slot(
    campaign_id: str,
    body: StrategicCapacitySlotCreate,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(edit),
):
    try:
        row = StrategicCampaignCapacityService(db, actor.tenant_id).create_slot(campaign_id, body)
        return created(StrategicCapacitySlotOut.model_validate(row))
    except DomainError as exc:
        return err(exc)


@router.put("/capacity-slots/{slot_id}")
def update_capacity_slot(
    slot_id: str,
    body: StrategicCapacitySlotUpdate,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(edit),
):
    try:
        row = StrategicCampaignCapacityService(db, actor.tenant_id).update_slot(slot_id, body)
        return ok(StrategicCapacitySlotOut.model_validate(row))
    except DomainError as exc:
        return err(exc)


@router.get("/{campaign_id}/reservations")
def list_strategic_reservations(
    campaign_id: str,
    status: Literal["held", "confirmed", "released", "expired", "cancelled"] | None = Query(default=None),
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(view),
):
    try:
        rows = StrategicCampaignCapacityService(db, actor.tenant_id).list_reservations(campaign_id, status)
        return ok([StrategicReservationOut.model_validate(row) for row in rows])
    except DomainError as exc:
        return err(exc)


@router.post("/{campaign_id}/reservations", status_code=201)
def create_strategic_reservation(
    campaign_id: str,
    body: StrategicReservationCreate,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(edit),
):
    try:
        row = StrategicCampaignCapacityService(db, actor.tenant_id).create_reservation(campaign_id, body)
        return created(StrategicReservationOut.model_validate(row))
    except DomainError as exc:
        return err(exc)


@router.post("/reservations/{reservation_id}/confirm")
def confirm_strategic_reservation(
    reservation_id: str,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(edit),
):
    try:
        row = StrategicCampaignCapacityService(db, actor.tenant_id).confirm_reservation(reservation_id)
        return ok(StrategicReservationOut.model_validate(row))
    except DomainError as exc:
        return err(exc)


@router.post("/reservations/{reservation_id}/release")
def release_strategic_reservation(
    reservation_id: str,
    body: StrategicReservationRelease,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(edit),
):
    try:
        row = StrategicCampaignCapacityService(db, actor.tenant_id).release_reservation(reservation_id, body)
        return ok(StrategicReservationOut.model_validate(row))
    except DomainError as exc:
        return err(exc)


@router.post("/reservations/{reservation_id}/bind-order")
def bind_strategic_reservation_order(
    reservation_id: str,
    body: StrategicReservationOrderBinding,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(edit),
):
    try:
        row = StrategicCampaignCapacityService(db, actor.tenant_id).bind_confirmed_order(
            reservation_id, body.order_id,
        )
        return ok(StrategicReservationOut.model_validate(row))
    except DomainError as exc:
        return err(exc)


@router.post("/reservations/release-due-orders")
def release_due_strategic_orders(
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(edit),
):
    try:
        rows = StrategicCampaignCapacityService(db, actor.tenant_id).release_due_orders(
            actor_id=actor.user_id,
        )
        return ok(StrategicOperationalReleaseResult(
            released_count=len(rows),
            reservation_ids=[row.id for row in rows],
            order_ids=[row.order_id for row in rows if row.order_id],
        ))
    except DomainError as exc:
        return err(exc)


@router.post("/{campaign_id}/reservations/expire")
def expire_strategic_reservations(
    campaign_id: str,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(edit),
):
    try:
        reservation_ids = StrategicCampaignCapacityService(db, actor.tenant_id).expire_due(campaign_id)
        return ok(StrategicReservationExpirationResult(
            expired_count=len(reservation_ids),
            reservation_ids=reservation_ids,
        ))
    except DomainError as exc:
        return err(exc)

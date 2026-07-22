from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from backend.core.response import ok
from backend.core.tenant_runtime import resolve_panel_tenant_context
from backend.core.tenant_route_context import operation_tenant_id
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.models.customer_contact_risk import CustomerContactRiskEvent
from backend.routes.admin_auth import get_current_admin
from backend.schemas.customer_contact_risk import ContactRiskOverride
from backend.services.customer_contact_risk_service import CustomerContactRiskService

router = APIRouter(prefix="/customers", tags=["customer-contact-risk"])


def _service(request: Request, db: Session, admin: AdminUser) -> CustomerContactRiskService:
    context = resolve_panel_tenant_context(request, db, admin)
    return CustomerContactRiskService(db, operation_tenant_id(context))


@router.get("/{customer_id}/contact-risk")
def get_contact_risk(customer_id: str, request: Request, channel: str = Query("whatsapp"),
    db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    if channel != "whatsapp":
        from backend.core.exceptions import DomainError
        raise DomainError("Canal de rating ainda nao suportado.", code="ContactRiskChannelInvalid")
    return ok(_service(request, db, admin).serialize(customer_id))


@router.get("/{customer_id}/contact-risk/events")
def list_contact_risk_events(customer_id: str, request: Request, channel: str = Query("whatsapp"),
    db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    service = _service(request, db, admin)
    service.get_or_create(customer_id, channel)
    rows = db.query(CustomerContactRiskEvent).filter(CustomerContactRiskEvent.tenant_id == service.tenant_id,
        CustomerContactRiskEvent.customer_id == customer_id, CustomerContactRiskEvent.channel == channel
    ).order_by(CustomerContactRiskEvent.occurred_at.desc()).limit(100).all()
    return ok([{"id": row.id, "event_type": row.event_type, "points_delta": row.points_delta,
        "score_before": row.score_before, "score_after": row.score_after,
        "blocks_contact": row.blocks_contact, "source_type": row.source_type,
        "source_id": row.source_id, "occurred_at": row.occurred_at,
        "metadata_json": row.metadata_json} for row in rows])


@router.post("/{customer_id}/contact-risk/override")
def override_contact_risk(customer_id: str, body: ContactRiskOverride, request: Request,
    channel: str = Query("whatsapp"), db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)):
    service = _service(request, db, admin)
    risk = service.get_or_create(customer_id, channel)
    if body.action == "set_score":
        if body.score is None:
            from backend.core.exceptions import DomainError
            raise DomainError("Informe o score para o ajuste manual.", code="ContactRiskScoreRequired")
        service.record_event(customer_id, "manual_adjustment", points_delta=body.score - int(risk.score or 0),
            source_type="admin", source_id=admin.id, reason=body.reason,
            metadata={"reason": body.reason, "target_score": body.score})
    elif body.action == "block":
        service.record_event(customer_id, "manual_block", points_delta=100 - int(risk.score or 0),
            source_type="admin", source_id=admin.id, reason=body.reason, metadata={"reason": body.reason})
    elif body.action == "unblock":
        service.record_event(customer_id, "contact_unblocked", points_delta=0,
            source_type="admin", source_id=admin.id, reason=body.reason, metadata={"reason": body.reason})
    else:
        event_type = {
            "complaint": "order_complaint",
            "reported": "contact_reported",
            "opt_out": "marketing_opt_out",
            "whatsapp_blocked": "whatsapp_blocked",
        }[body.action]
        service.record_event(customer_id, event_type, source_type="admin", source_id=admin.id,
            reason=body.reason, metadata={"reason": body.reason})
    db.commit()
    return ok(service.serialize(customer_id))

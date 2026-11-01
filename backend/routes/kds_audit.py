from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import err, ok
from backend.database import get_db
from backend.schemas.kds_audit import AuditEvidenceIn, AuditHandoffIn, AuditItemConfirmIn
from backend.services.kds_audit_service import KdsAuditService

router = APIRouter(prefix="/kds/auditoria", tags=["kds-auditoria"])


def _service(db: Session, actor: AuthorizedTenantActor) -> KdsAuditService:
    return KdsAuditService(db, actor.tenant_id)


@router.get("/queue")
def queue(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("kds_auditoria", "view"))):
    return ok(_service(db, actor).queue())


@router.get("/orders/{order_id}")
def detail(order_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("kds_auditoria", "view"))):
    try:
        return ok(_service(db, actor).detail(order_id))
    except DomainError as exc:
        return err(exc)


@router.post("/orders/{order_id}/start", status_code=201)
def start(order_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("kds_auditoria", "edit"))):
    try:
        return ok(_service(db, actor).start(order_id, actor.user_id), status_code=201)
    except DomainError as exc:
        return err(exc)


@router.post("/{audit_id}/items/{item_id}/confirm")
def confirm_item(audit_id: str, item_id: str, body: AuditItemConfirmIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("kds_auditoria", "edit"))):
    try:
        return ok(_service(db, actor).confirm_item(audit_id, item_id, body.confirmed_quantity, actor.user_id))
    except DomainError as exc:
        return err(exc)


@router.post("/{audit_id}/volumes/{volume_id}/confirm")
def confirm_volume(audit_id: str, volume_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("kds_auditoria", "edit"))):
    try:
        return ok(_service(db, actor).confirm_volume(audit_id, volume_id, actor.user_id))
    except DomainError as exc:
        return err(exc)


@router.post("/{audit_id}/evidence")
def evidence(audit_id: str, body: AuditEvidenceIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("kds_auditoria", "edit"))):
    try:
        return ok(_service(db, actor).add_evidence(audit_id, body, actor.user_id), status_code=201)
    except DomainError as exc:
        return err(exc)


@router.post("/{audit_id}/handoff")
def handoff(audit_id: str, body: AuditHandoffIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("kds_auditoria", "edit"))):
    try:
        return ok(_service(db, actor).handoff(audit_id, actor.user_id))
    except DomainError as exc:
        return err(exc)

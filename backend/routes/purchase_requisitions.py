from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import err
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.database import get_db
from backend.schemas.purchase_requisition import PurchaseRequisitionCreate, PurchaseRequisitionOut, PurchaseRequisitionTransitionIn, PurchaseRequisitionUpdate
from backend.schemas.purchase_planning import PurchasePlanningOut
from backend.services.purchase_requisition_service import PurchaseRequisitionService
from backend.services.purchase_planning_service import PurchasePlanningService

router = APIRouter(prefix="/gestao/purchases/requisitions", tags=["purchase-requisitions"])


def service(db: Session, actor: AuthorizedTenantActor) -> PurchaseRequisitionService:
    return PurchaseRequisitionService(db, actor.user_id, actor.tenant_context)


@router.get("/planning/needs", response_model=PurchasePlanningOut)
def planning_needs(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "view"))):
    return PurchasePlanningService(db, actor.tenant_context).plan()


@router.get("", response_model=list[PurchaseRequisitionOut])
def list_requisitions(status: str | None = Query(default=None), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "view"))):
    return service(db, actor).list(status)


@router.get("/{requisition_id}", response_model=PurchaseRequisitionOut)
def get_requisition(requisition_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "view"))):
    try:
        return service(db, actor).get(requisition_id)
    except DomainError as exc:
        return err(exc)


@router.post("", response_model=PurchaseRequisitionOut, status_code=201)
def create_requisition(body: PurchaseRequisitionCreate, idempotency_key: str = Header(..., alias="Idempotency-Key"), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "create"))):
    try:
        return service(db, actor).create(body, idempotency_key)
    except DomainError as exc:
        return err(exc)


@router.put("/{requisition_id}", response_model=PurchaseRequisitionOut)
def update_requisition(requisition_id: str, body: PurchaseRequisitionUpdate, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "edit"))):
    try:
        return service(db, actor).update(requisition_id, body)
    except DomainError as exc:
        return err(exc)


def transition(action: str, permission: str = "edit"):
    def handler(requisition_id: str, body: PurchaseRequisitionTransitionIn, idempotency_key: str = Header(..., alias="Idempotency-Key"), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", permission))):
        try:
            return service(db, actor).transition(requisition_id, action, body, idempotency_key)
        except DomainError as exc:
            return err(exc)
    return handler


router.post("/{requisition_id}/submit", response_model=PurchaseRequisitionOut)(transition("submit"))
router.post("/{requisition_id}/approve", response_model=PurchaseRequisitionOut)(transition("approve", "manage"))
router.post("/{requisition_id}/reject", response_model=PurchaseRequisitionOut)(transition("reject", "manage"))
router.post("/{requisition_id}/cancel", response_model=PurchaseRequisitionOut)(transition("cancel"))
router.post("/{requisition_id}/source", response_model=PurchaseRequisitionOut)(transition("source"))
router.post("/{requisition_id}/order", response_model=PurchaseRequisitionOut)(transition("order"))

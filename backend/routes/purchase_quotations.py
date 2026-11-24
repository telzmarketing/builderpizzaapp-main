from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from backend.core.response import err
from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.database import get_db
from backend.schemas.purchase_quotation import PurchaseQuotationCreate, PurchaseQuotationOfferCreate, PurchaseQuotationOut, PurchaseQuotationTransitionIn
from backend.services.purchase_quotation_service import PurchaseQuotationService

router = APIRouter(prefix="/gestao/purchases/quotations", tags=["purchase-quotations"])


def service(db: Session, actor: AuthorizedTenantActor) -> PurchaseQuotationService:
    return PurchaseQuotationService(db, actor.user_id, actor.tenant_context)


@router.get("", response_model=list[PurchaseQuotationOut])
def list_quotations(status: str | None = Query(default=None), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "view"))):
    return service(db, actor).list(status)


@router.get("/{quotation_id}", response_model=PurchaseQuotationOut)
def get_quotation(quotation_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "view"))):
    try: return service(db, actor).get(quotation_id)
    except DomainError as exc: return err(exc)


@router.post("", response_model=PurchaseQuotationOut, status_code=201)
def create_quotation(body: PurchaseQuotationCreate, idempotency_key: str = Header(..., alias="Idempotency-Key"), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "create"))):
    try: return service(db, actor).create(body, idempotency_key)
    except DomainError as exc: return err(exc)


@router.post("/{quotation_id}/offers", response_model=PurchaseQuotationOut)
def add_offer(quotation_id: str, body: PurchaseQuotationOfferCreate, idempotency_key: str = Header(..., alias="Idempotency-Key"), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "edit"))):
    try: return service(db, actor).add_offer(quotation_id, body, idempotency_key)
    except DomainError as exc: return err(exc)


@router.post("/{quotation_id}/open", response_model=PurchaseQuotationOut)
def open_quotation(quotation_id: str, body: PurchaseQuotationTransitionIn, idempotency_key: str = Header(..., alias="Idempotency-Key"), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "edit"))):
    try: return service(db, actor).transition(quotation_id, "open", body, idempotency_key)
    except DomainError as exc: return err(exc)


@router.post("/{quotation_id}/close", response_model=PurchaseQuotationOut)
def close_quotation(quotation_id: str, body: PurchaseQuotationTransitionIn, idempotency_key: str = Header(..., alias="Idempotency-Key"), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "edit"))):
    try: return service(db, actor).transition(quotation_id, "close", body, idempotency_key)
    except DomainError as exc: return err(exc)


@router.post("/{quotation_id}/award", response_model=PurchaseQuotationOut)
def award_quotation(quotation_id: str, supplier_id: str, body: PurchaseQuotationTransitionIn, idempotency_key: str = Header(..., alias="Idempotency-Key"), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "manage"))):
    try: return service(db, actor).transition(quotation_id, "award", body, idempotency_key, supplier_id)
    except DomainError as exc: return err(exc)


@router.post("/{quotation_id}/cancel", response_model=PurchaseQuotationOut)
def cancel_quotation(quotation_id: str, body: PurchaseQuotationTransitionIn, idempotency_key: str = Header(..., alias="Idempotency-Key"), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "edit"))):
    try: return service(db, actor).transition(quotation_id, "cancel", body, idempotency_key)
    except DomainError as exc: return err(exc)

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import err
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.database import get_db
from backend.schemas.purchase_receipt import PurchaseReceiptCreate, PurchaseReceiptOut, PurchaseReceiptTransition
from backend.services.purchase_receipt_service import PurchaseReceiptService

router = APIRouter(prefix="/gestao/purchases/receipts", tags=["purchase-receipts"])

def service(db: Session, actor: AuthorizedTenantActor) -> PurchaseReceiptService:
    return PurchaseReceiptService(db, actor.user_id, actor.tenant_context)

@router.get("", response_model=list[PurchaseReceiptOut])
def list_receipts(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "view"))):
    return service(db, actor).list()

@router.get("/{receipt_id}", response_model=PurchaseReceiptOut)
def get_receipt(receipt_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "view"))):
    try: return service(db, actor).get(receipt_id)
    except DomainError as exc: return err(exc)

@router.post("", response_model=PurchaseReceiptOut, status_code=201)
def create_receipt(body: PurchaseReceiptCreate, idempotency_key: str = Header(..., alias="Idempotency-Key"), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "create"))):
    try: return service(db, actor).create(body, idempotency_key)
    except DomainError as exc: return err(exc)

@router.post("/{receipt_id}/submit", response_model=PurchaseReceiptOut)
def submit_receipt(receipt_id: str, body: PurchaseReceiptTransition, idempotency_key: str = Header(..., alias="Idempotency-Key"), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "edit"))):
    try: return service(db, actor).submit(receipt_id, body, idempotency_key)
    except DomainError as exc: return err(exc)

@router.post("/{receipt_id}/post", response_model=PurchaseReceiptOut)
def post_receipt(receipt_id: str, body: PurchaseReceiptTransition, idempotency_key: str = Header(..., alias="Idempotency-Key"), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "manage"))):
    try: return service(db, actor).post(receipt_id, body, idempotency_key)
    except DomainError as exc: return err(exc)

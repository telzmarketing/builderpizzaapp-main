from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from sqlalchemy.orm import Session
from backend.core.response import err
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.exceptions import DomainError
from backend.database import get_db
from backend.services.inventory_receipt_service import InventoryReceiptService

router = APIRouter(prefix="/gestao/inventory/v1/documents", tags=["inventory-receipts"])
view = require_rbac_permission("inventory", "view")
create = require_rbac_permission("inventory", "create")
edit = require_rbac_permission("inventory", "edit")

def invoke(fn, *args):
    try: return fn(*args)
    except DomainError as exc: return err(exc)

@router.get("")
def list_documents(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    return InventoryReceiptService(db, actor.tenant_id, actor.user_id).list()

@router.get("/{document_id}")
def get_document(document_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    return invoke(InventoryReceiptService(db, actor.tenant_id, actor.user_id).get, document_id)

@router.post("", status_code=201)
async def upload_document(file: UploadFile = File(...), purchase_id: str | None = Form(None), idempotency_key: str | None = Header(None, alias="Idempotency-Key"), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(create)):
    return invoke(InventoryReceiptService(db, actor.tenant_id, actor.user_id).upload, await file.read(), idempotency_key, purchase_id, file.filename, file.content_type)

@router.patch("/{document_id}")
def update_document(document_id: str, body: dict, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit)):
    return invoke(InventoryReceiptService(db, actor.tenant_id, actor.user_id).update, document_id, body)

@router.post("/{document_id}/approve")
def approve_document(document_id: str, body: dict | None = None, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit), idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    return invoke(InventoryReceiptService(db, actor.tenant_id, actor.user_id).approve, document_id, (body or {}).get("expected_version"), idempotency_key)

@router.post("/{document_id}/payables/reconcile")
def reconcile(document_id: str, body: dict, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit), idempotency_key: str = Header(..., alias="Idempotency-Key")):
    return invoke(InventoryReceiptService(db, actor.tenant_id, actor.user_id).reconcile, document_id, body, idempotency_key)

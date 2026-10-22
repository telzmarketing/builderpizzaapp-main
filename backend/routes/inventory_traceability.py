from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session
from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import err
from backend.database import get_db
from backend.schemas.inventory_traceability import OpeningIn, OpeningOut, GenealogyIn, GenealogyPage
from backend.services.inventory_traceability_service import InventoryTraceabilityService

router = APIRouter(prefix="/gestao/inventory/v1", tags=["inventory-traceability"])
view = require_rbac_permission("inventory", "view")
manage = require_rbac_permission("inventory", "manage")
def svc(db, actor): return InventoryTraceabilityService(db, actor.tenant_id, actor.user_id)
def call(fn, *args):
    try: return fn(*args)
    except DomainError as exc: return err(exc)

@router.post("/lots/{lot_id}/openings", response_model=OpeningOut)
def opening(lot_id: str, body: OpeningIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(manage), key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200)):
    return call(svc(db, actor).open_lot, lot_id, body, key)

@router.post("/lots/{lot_id}/open", response_model=OpeningOut)
def open_compat(lot_id: str, body: OpeningIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(manage), key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200)):
    return call(svc(db, actor).open_lot, lot_id, body, key)

@router.post("/lot-genealogy", response_model=dict)
def create_genealogy(body: GenealogyIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(manage), key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200)):
    return call(svc(db, actor).add_genealogy, body, key)

@router.get("/lots/{lot_id}/genealogy", response_model=GenealogyPage)
def list_genealogy(lot_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    return call(svc(db, actor).genealogy, lot_id)

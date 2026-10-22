"""Tenant/RBAC boundary for explicit stock foundation commands."""
from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import err
from backend.database import get_db
from backend.schemas.inventory_foundation import (
    ConversionPreviewIn, LotIn, LotStateIn, OperationIn, PackagingIn, ReleaseIn, ReservationIn, UnitIn,
    UnitOut, PackagingOut, LotOut, ReservationOut, ConversionPreviewOut, OperationOut,
    UnitsPage, PackagingsPage, LotsPage, ReservationsPage, BalancesPage, ReconciliationPage,
)
from backend.services.inventory_foundation_service import InventoryFoundationService

router = APIRouter(prefix="/gestao/inventory/v1", tags=["inventory-foundation"])
view = require_rbac_permission("inventory", "view")
create = require_rbac_permission("inventory", "create")
edit = require_rbac_permission("inventory", "edit")
manage = require_rbac_permission("inventory", "manage")


def service(db, actor):
    return InventoryFoundationService(db, actor.tenant_id, actor.user_id, actor.tenant_context)


def invoke(fn, *args):
    try:
        return fn(*args)
    except DomainError as exc:
        return err(exc)


@router.get("/units", response_model=UnitsPage)
def units(cursor: str | None = None, limit: int = Query(500, ge=1, le=500), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    return invoke(service(db, actor).list_units, cursor, limit)


@router.post("/units", status_code=201, response_model=UnitOut)
def create_unit(body: UnitIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(create), key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200)):
    return invoke(service(db, actor).create_unit, body, key)


@router.put("/units/{unit_id}", response_model=UnitOut)
def update_unit(unit_id: str, body: UnitIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(edit), key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200)):
    return invoke(service(db, actor).update_unit, unit_id, body, key)


@router.post("/conversions/preview", response_model=ConversionPreviewOut)
def preview(body: ConversionPreviewIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    return invoke(service(db, actor).preview, body)


@router.get("/packagings", response_model=PackagingsPage)
def packagings(item_id: str | None = None, cursor: str | None = None, limit: int = Query(500, ge=1, le=500), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    return invoke(service(db, actor).list_packagings, item_id, cursor, limit)


@router.post("/packagings", status_code=201, response_model=PackagingOut)
def create_packaging(body: PackagingIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(create), key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200)):
    return invoke(service(db, actor).create_packaging, body, key)


@router.get("/lots", response_model=LotsPage)
def lots(item_id: str | None = None, cursor: str | None = None, limit: int = Query(500, ge=1, le=500), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    return invoke(service(db, actor).list_lots, item_id, cursor, limit)


@router.post("/lots", status_code=201, response_model=LotOut)
def create_lot(body: LotIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(create), key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200)):
    return invoke(service(db, actor).create_lot, body, key)


@router.post("/lots/{lot_id}/state", response_model=LotOut)
def lot_state(lot_id: str, body: LotStateIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(manage), key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200)):
    return invoke(service(db, actor).set_lot_state, lot_id, body, key)


@router.post("/operations", status_code=201, response_model=OperationOut)
def create_operation(body: OperationIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(manage), key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200)):
    return invoke(service(db, actor).create_operation, body, key)


@router.get("/balances", response_model=BalancesPage)
def balances(item_id: str | None = None, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    return invoke(service(db, actor).balances, item_id)


@router.get("/reconciliation", response_model=ReconciliationPage)
def reconciliation(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    return invoke(service(db, actor).reconciliation)


@router.get("/reservations", response_model=ReservationsPage)
def reservations(cursor: str | None = None, limit: int = Query(500, ge=1, le=500), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    return invoke(service(db, actor).list_reservations, cursor, limit)


@router.post("/reservations", status_code=201, response_model=ReservationOut)
def reserve(body: ReservationIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(manage), key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200)):
    return invoke(service(db, actor).reserve, body, key)


@router.post("/reservations/{reservation_id}/release", response_model=ReservationOut)
def release(reservation_id: str, body: ReleaseIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(manage), key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200)):
    return invoke(service(db, actor).release, reservation_id, body, key)

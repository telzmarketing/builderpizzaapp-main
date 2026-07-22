from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from backend.core.tenant_context import TenantContext
from backend.core.tenant_route_context import panel_operation_context, public_operation_context
from backend.core.tenant_runtime import resolve_panel_tenant_context, resolve_public_tenant_context
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.admin_auth import get_current_admin
from backend.schemas.salao import (
    PublicReservationCreate,
    ReservationCreate,
    ReservationOut,
    ReservationStatusUpdate,
    ReservationUpdate,
    RestaurantTableCreate,
    RestaurantTableOut,
    RestaurantTableStatusUpdate,
    RestaurantTableUpdate,
    TableSessionClose,
    TableSessionCreate,
    TableSessionItemCreate,
    TableSessionItemUpdate,
    TableSessionOrderCreate,
    TableSessionOrderOut,
    TableSessionPaymentConfirm,
    TableSessionOut,
    TableSessionUpdate,
)
from backend.services.order_service import OrderService
from backend.services.salao_service import ReservationService, RestaurantTableService, TableSessionService

router = APIRouter(prefix="/salao", tags=["salao"])


def _panel_context(request: Request, db: Session, admin: AdminUser) -> TenantContext | None:
    return resolve_panel_tenant_context(request, db, admin)


def _public_context(request: Request, db: Session) -> TenantContext | None:
    return resolve_public_tenant_context(request, db)


@router.get("/tables", response_model=list[RestaurantTableOut])
def list_tables(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    return RestaurantTableService(db, tenant_context).list(include_inactive=include_inactive)


@router.post("/tables", response_model=RestaurantTableOut, status_code=201)
def create_table(
    body: RestaurantTableCreate,
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    return RestaurantTableService(db, tenant_context).create(body.model_dump())


@router.patch("/tables/{table_id}", response_model=RestaurantTableOut)
def update_table(
    table_id: str,
    body: RestaurantTableUpdate,
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    return RestaurantTableService(db, tenant_context).update(table_id, body.model_dump(exclude_unset=True))


@router.patch("/tables/{table_id}/status", response_model=RestaurantTableOut)
def update_table_status(
    table_id: str,
    body: RestaurantTableStatusUpdate,
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    return RestaurantTableService(db, tenant_context).update_status(table_id, body.status)


@router.get("/reservations", response_model=list[ReservationOut])
def list_reservations(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    return ReservationService(db, tenant_context).list(status=status)


@router.post("/reservations", response_model=ReservationOut, status_code=201)
def create_reservation(
    body: ReservationCreate,
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    return ReservationService(db, tenant_context).create(body.model_dump())


@router.post("/reservations/public", response_model=ReservationOut, status_code=201)
def create_public_reservation(
    body: PublicReservationCreate,
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(public_operation_context),
):
    data = body.model_dump()
    data["status"] = "pending"
    data["source"] = "salao_public"
    return ReservationService(db, tenant_context).create(data)


@router.patch("/reservations/{reservation_id}", response_model=ReservationOut)
def update_reservation(
    reservation_id: str,
    body: ReservationUpdate,
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    return ReservationService(db, tenant_context).update(reservation_id, body.model_dump(exclude_unset=True))


@router.patch("/reservations/{reservation_id}/status", response_model=ReservationOut)
def update_reservation_status(
    reservation_id: str,
    body: ReservationStatusUpdate,
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    return ReservationService(db, tenant_context).update_status(reservation_id, body.status)


@router.get("/table-sessions", response_model=list[TableSessionOut])
def list_table_sessions(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    return TableSessionService(db, tenant_context).list(status=status)


@router.post("/table-sessions", response_model=TableSessionOut, status_code=201)
def open_table_session(
    body: TableSessionCreate,
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    return TableSessionService(db, tenant_context).open(body.model_dump())


@router.patch("/table-sessions/{session_id}", response_model=TableSessionOut)
def update_table_session(
    session_id: str,
    body: TableSessionUpdate,
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    return TableSessionService(db, tenant_context).update(session_id, body.model_dump(exclude_unset=True))


@router.post("/table-sessions/{session_id}/close", response_model=TableSessionOut)
def close_table_session(
    session_id: str,
    body: TableSessionClose,
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    return TableSessionService(db, tenant_context).close(session_id, body.model_dump(exclude_unset=True))


@router.post("/table-sessions/{session_id}/order", response_model=TableSessionOrderOut, status_code=201)
def create_order_from_table_session(
    session_id: str,
    body: TableSessionOrderCreate,
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    order = OrderService(db, tenant_context).create_from_table_session(session_id, payment_method=body.payment_method)
    return {"order_id": order.id}


@router.post("/table-sessions/{session_id}/payment", response_model=TableSessionOrderOut)
def confirm_table_session_payment(
    session_id: str,
    body: TableSessionPaymentConfirm,
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    order = OrderService(db, tenant_context).confirm_table_session_payment(session_id, payment_method=body.payment_method)
    return {"order_id": order.id}


@router.post("/table-sessions/{session_id}/items", response_model=TableSessionOut, status_code=201)
def add_table_session_item(
    session_id: str,
    body: TableSessionItemCreate,
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    return TableSessionService(db, tenant_context).add_item(session_id, body.model_dump())


@router.patch("/table-sessions/{session_id}/items/{item_id}", response_model=TableSessionOut)
def update_table_session_item(
    session_id: str,
    item_id: str,
    body: TableSessionItemUpdate,
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    return TableSessionService(db, tenant_context).update_item(session_id, item_id, body.model_dump(exclude_unset=True))


@router.delete("/table-sessions/{session_id}/items/{item_id}", response_model=TableSessionOut)
def delete_table_session_item(
    session_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    return TableSessionService(db, tenant_context).delete_item(session_id, item_id)

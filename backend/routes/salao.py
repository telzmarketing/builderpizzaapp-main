from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.database import get_db
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


@router.get("/tables", response_model=list[RestaurantTableOut])
def list_tables(
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return RestaurantTableService(db).list(include_inactive=include_inactive)


@router.post("/tables", response_model=RestaurantTableOut, status_code=201)
def create_table(
    body: RestaurantTableCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return RestaurantTableService(db).create(body.model_dump())


@router.patch("/tables/{table_id}", response_model=RestaurantTableOut)
def update_table(
    table_id: str,
    body: RestaurantTableUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return RestaurantTableService(db).update(table_id, body.model_dump(exclude_unset=True))


@router.patch("/tables/{table_id}/status", response_model=RestaurantTableOut)
def update_table_status(
    table_id: str,
    body: RestaurantTableStatusUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return RestaurantTableService(db).update_status(table_id, body.status)


@router.get("/reservations", response_model=list[ReservationOut])
def list_reservations(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return ReservationService(db).list(status=status)


@router.post("/reservations", response_model=ReservationOut, status_code=201)
def create_reservation(
    body: ReservationCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return ReservationService(db).create(body.model_dump())


@router.post("/reservations/public", response_model=ReservationOut, status_code=201)
def create_public_reservation(body: PublicReservationCreate, db: Session = Depends(get_db)):
    data = body.model_dump()
    data["status"] = "pending"
    data["source"] = "salao_public"
    return ReservationService(db).create(data)


@router.patch("/reservations/{reservation_id}", response_model=ReservationOut)
def update_reservation(
    reservation_id: str,
    body: ReservationUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return ReservationService(db).update(reservation_id, body.model_dump(exclude_unset=True))


@router.patch("/reservations/{reservation_id}/status", response_model=ReservationOut)
def update_reservation_status(
    reservation_id: str,
    body: ReservationStatusUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return ReservationService(db).update_status(reservation_id, body.status)


@router.get("/table-sessions", response_model=list[TableSessionOut])
def list_table_sessions(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return TableSessionService(db).list(status=status)


@router.post("/table-sessions", response_model=TableSessionOut, status_code=201)
def open_table_session(
    body: TableSessionCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return TableSessionService(db).open(body.model_dump())


@router.patch("/table-sessions/{session_id}", response_model=TableSessionOut)
def update_table_session(
    session_id: str,
    body: TableSessionUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return TableSessionService(db).update(session_id, body.model_dump(exclude_unset=True))


@router.post("/table-sessions/{session_id}/close", response_model=TableSessionOut)
def close_table_session(
    session_id: str,
    body: TableSessionClose,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return TableSessionService(db).close(session_id, body.model_dump(exclude_unset=True))


@router.post("/table-sessions/{session_id}/order", response_model=TableSessionOrderOut, status_code=201)
def create_order_from_table_session(
    session_id: str,
    body: TableSessionOrderCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    order = OrderService(db).create_from_table_session(session_id, payment_method=body.payment_method)
    return {"order_id": order.id}


@router.post("/table-sessions/{session_id}/payment", response_model=TableSessionOrderOut)
def confirm_table_session_payment(
    session_id: str,
    body: TableSessionPaymentConfirm,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    order = OrderService(db).confirm_table_session_payment(session_id, payment_method=body.payment_method)
    return {"order_id": order.id}


@router.post("/table-sessions/{session_id}/items", response_model=TableSessionOut, status_code=201)
def add_table_session_item(
    session_id: str,
    body: TableSessionItemCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return TableSessionService(db).add_item(session_id, body.model_dump())


@router.patch("/table-sessions/{session_id}/items/{item_id}", response_model=TableSessionOut)
def update_table_session_item(
    session_id: str,
    item_id: str,
    body: TableSessionItemUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return TableSessionService(db).update_item(session_id, item_id, body.model_dump(exclude_unset=True))


@router.delete("/table-sessions/{session_id}/items/{item_id}", response_model=TableSessionOut)
def delete_table_session_item(
    session_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    return TableSessionService(db).delete_item(session_id, item_id)

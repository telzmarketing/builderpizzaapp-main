from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.models.product import Product
from backend.models.salao import Reservation, RestaurantTable, TableSession, TableSessionItem


TABLE_STATUSES = {"available", "occupied", "reserved", "cleaning", "inactive"}
RESERVATION_STATUSES = {"pending", "confirmed", "seated", "cancelled", "no_show", "completed"}
SESSION_STATUSES = {"open", "pending_payment", "paid", "closed", "cancelled"}
OPEN_SESSION_STATUSES = {"open", "pending_payment"}


class SalaoNotFound(DomainError):
    http_status = 404

    def __init__(self, entity: str):
        super().__init__(f"{entity} nao encontrado.", code="SalaoNotFound")


class SalaoRuleError(DomainError):
    def __init__(self, message: str, *, code: str = "SalaoRuleError"):
        super().__init__(message, code=code)


class RestaurantTableService:
    def __init__(self, db: Session):
        self._db = db

    def list(self, *, include_inactive: bool = False) -> list[RestaurantTable]:
        query = self._db.query(RestaurantTable)
        if not include_inactive:
            query = query.filter(RestaurantTable.active == True)  # noqa: E712
        return query.order_by(RestaurantTable.number.asc()).all()

    def get(self, table_id: str) -> RestaurantTable:
        table = self._db.query(RestaurantTable).filter(RestaurantTable.id == table_id).first()
        if not table:
            raise SalaoNotFound("Mesa")
        return table

    def create(self, data: dict) -> RestaurantTable:
        self._validate_status(data.get("status", "available"))
        existing = self._db.query(RestaurantTable).filter(RestaurantTable.number == data["number"]).first()
        if existing:
            raise SalaoRuleError("Ja existe uma mesa com este numero.", code="RestaurantTableNumberExists")
        table = RestaurantTable(id=f"tbl-{uuid.uuid4().hex[:10]}", **data)
        self._db.add(table)
        self._db.commit()
        self._db.refresh(table)
        return table

    def update(self, table_id: str, data: dict) -> RestaurantTable:
        table = self.get(table_id)
        if "status" in data and data["status"] is not None:
            self._validate_status(data["status"])
        if "number" in data and data["number"]:
            existing = (
                self._db.query(RestaurantTable)
                .filter(RestaurantTable.number == data["number"], RestaurantTable.id != table_id)
                .first()
            )
            if existing:
                raise SalaoRuleError("Ja existe uma mesa com este numero.", code="RestaurantTableNumberExists")
        for key, value in data.items():
            setattr(table, key, value)
        self._db.commit()
        self._db.refresh(table)
        return table

    def update_status(self, table_id: str, status: str) -> RestaurantTable:
        self._validate_status(status)
        return self.update(table_id, {"status": status, "active": status != "inactive"})

    def _validate_status(self, status: str) -> None:
        if status not in TABLE_STATUSES:
            raise SalaoRuleError("Status de mesa invalido.", code="InvalidRestaurantTableStatus")


class ReservationService:
    def __init__(self, db: Session):
        self._db = db

    def list(self, *, status: str | None = None) -> list[Reservation]:
        query = self._db.query(Reservation)
        if status:
            self._validate_status(status)
            query = query.filter(Reservation.status == status)
        return query.order_by(Reservation.reservation_date.desc(), Reservation.reservation_time.desc()).all()

    def get(self, reservation_id: str) -> Reservation:
        reservation = self._db.query(Reservation).filter(Reservation.id == reservation_id).first()
        if not reservation:
            raise SalaoNotFound("Reserva")
        return reservation

    def create(self, data: dict) -> Reservation:
        self._validate_status(data.get("status", "pending"))
        table_id = data.get("table_id")
        if table_id:
            RestaurantTableService(self._db).get(table_id)
        reservation = Reservation(id=f"res-{uuid.uuid4().hex[:10]}", **data)
        self._db.add(reservation)
        self._sync_table_from_reservation(reservation)
        self._db.commit()
        self._db.refresh(reservation)
        return reservation

    def update(self, reservation_id: str, data: dict) -> Reservation:
        reservation = self.get(reservation_id)
        if "status" in data and data["status"] is not None:
            self._validate_status(data["status"])
        if data.get("table_id"):
            RestaurantTableService(self._db).get(data["table_id"])
        for key, value in data.items():
            setattr(reservation, key, value)
        self._sync_table_from_reservation(reservation)
        self._db.commit()
        self._db.refresh(reservation)
        return reservation

    def update_status(self, reservation_id: str, status: str) -> Reservation:
        return self.update(reservation_id, {"status": status})

    def _validate_status(self, status: str) -> None:
        if status not in RESERVATION_STATUSES:
            raise SalaoRuleError("Status de reserva invalido.", code="InvalidReservationStatus")

    def _sync_table_from_reservation(self, reservation: Reservation) -> None:
        if not reservation.table_id:
            return
        table = RestaurantTableService(self._db).get(reservation.table_id)
        if reservation.status in {"confirmed"} and table.status == "available":
            table.status = "reserved"
        if reservation.status == "seated":
            table.status = "occupied"


class TableSessionService:
    def __init__(self, db: Session):
        self._db = db

    def list(self, *, status: str | None = None) -> list[TableSession]:
        query = self._db.query(TableSession)
        if status:
            self._validate_status(status)
            query = query.filter(TableSession.status == status)
        return query.order_by(TableSession.opened_at.desc()).all()

    def get(self, session_id: str) -> TableSession:
        session = self._db.query(TableSession).filter(TableSession.id == session_id).first()
        if not session:
            raise SalaoNotFound("Comanda")
        return session

    def open(self, data: dict) -> TableSession:
        self._validate_status(data.get("status", "open"))
        table = RestaurantTableService(self._db).get(data["table_id"])
        if not table.active or table.status == "inactive":
            raise SalaoRuleError("Mesa inativa nao pode abrir comanda.", code="InactiveRestaurantTable")
        existing = (
            self._db.query(TableSession)
            .filter(TableSession.table_id == table.id, TableSession.status.in_(OPEN_SESSION_STATUSES))
            .first()
        )
        if existing:
            raise SalaoRuleError("Mesa ja possui comanda aberta.", code="TableSessionAlreadyOpen")
        session = TableSession(id=f"cmd-{uuid.uuid4().hex[:10]}", **data)
        table.status = "occupied"
        self._db.add(session)
        self._db.commit()
        self._db.refresh(session)
        return session

    def update(self, session_id: str, data: dict) -> TableSession:
        session = self.get(session_id)
        if "status" in data and data["status"] is not None:
            self._validate_status(data["status"])
        for key, value in data.items():
            setattr(session, key, value)
        self._recalculate(session)
        self._sync_table_from_session(session)
        self._db.commit()
        self._db.refresh(session)
        return session

    def close(self, session_id: str, data: dict) -> TableSession:
        session = self.get(session_id)
        status = data.pop("status", "closed")
        if status not in {"paid", "closed"}:
            raise SalaoRuleError("Fechamento aceita apenas paid ou closed.", code="InvalidTableSessionCloseStatus")
        for key, value in data.items():
            if value is not None:
                setattr(session, key, value)
        self._recalculate(session)
        session.status = status
        session.closed_at = datetime.now(timezone.utc)
        if session.table:
            session.table.status = "cleaning"
        self._db.commit()
        self._db.refresh(session)
        return session

    def add_item(self, session_id: str, data: dict) -> TableSession:
        session = self.get(session_id)
        self._ensure_open(session)
        product = self._get_dine_in_product(data["product_id"])
        quantity = max(1, int(data.get("quantity") or 1))
        unit_price = data.get("unit_price")
        if unit_price is None:
            unit_price = product.dine_in_price if product.dine_in_price is not None else product.price
        unit_price = round(float(unit_price), 2)
        item = TableSessionItem(
            id=f"tsi-{uuid.uuid4().hex[:10]}",
            table_session_id=session.id,
            product_id=product.id,
            product_name=product.name,
            quantity=quantity,
            unit_price=unit_price,
            total_price=round(unit_price * quantity, 2),
            notes=data.get("notes"),
        )
        self._db.add(item)
        self._db.flush()
        self._recalculate(session)
        self._db.commit()
        self._db.refresh(session)
        return session

    def update_item(self, session_id: str, item_id: str, data: dict) -> TableSession:
        session = self.get(session_id)
        self._ensure_open(session)
        item = self._get_item(session_id, item_id)
        if "quantity" in data and data["quantity"] is not None:
            item.quantity = max(1, int(data["quantity"]))
        if "unit_price" in data and data["unit_price"] is not None:
            item.unit_price = round(float(data["unit_price"]), 2)
        if "notes" in data:
            item.notes = data["notes"]
        item.total_price = round(item.unit_price * item.quantity, 2)
        self._recalculate(session)
        self._db.commit()
        self._db.refresh(session)
        return session

    def delete_item(self, session_id: str, item_id: str) -> TableSession:
        session = self.get(session_id)
        self._ensure_open(session)
        item = self._get_item(session_id, item_id)
        self._db.delete(item)
        self._db.flush()
        self._recalculate(session)
        self._db.commit()
        self._db.refresh(session)
        return session

    def _validate_status(self, status: str) -> None:
        if status not in SESSION_STATUSES:
            raise SalaoRuleError("Status de comanda invalido.", code="InvalidTableSessionStatus")

    def _sync_table_from_session(self, session: TableSession) -> None:
        if not session.table:
            return
        if session.status in OPEN_SESSION_STATUSES:
            session.table.status = "occupied"
        elif session.status in {"paid", "closed", "cancelled"}:
            session.table.status = "cleaning"

    def _ensure_open(self, session: TableSession) -> None:
        if session.status != "open":
            raise SalaoRuleError("Comanda precisa estar aberta para alterar itens.", code="TableSessionNotOpen")

    def _get_dine_in_product(self, product_id: str) -> Product:
        product = (
            self._db.query(Product)
            .filter(Product.id == product_id, Product.active == True, Product.visible_dine_in == True)  # noqa: E712
            .first()
        )
        if not product:
            raise SalaoRuleError("Produto nao encontrado no cardapio do salao.", code="DineInProductNotFound")
        return product

    def _get_item(self, session_id: str, item_id: str) -> TableSessionItem:
        item = (
            self._db.query(TableSessionItem)
            .filter(TableSessionItem.id == item_id, TableSessionItem.table_session_id == session_id)
            .first()
        )
        if not item:
            raise SalaoNotFound("Item da comanda")
        return item

    def _recalculate(self, session: TableSession) -> None:
        self._db.flush()
        items = self._db.query(TableSessionItem).filter(TableSessionItem.table_session_id == session.id).all()
        subtotal = round(sum((item.total_price or 0.0) for item in items), 2)
        session.subtotal = subtotal
        session.total = round(max(0.0, subtotal + (session.service_fee or 0.0) - (session.discount or 0.0)), 2)
        session.updated_at = datetime.now(timezone.utc)

"""
Delivery endpoints — shared by loja online, ERP and mobile app (motoboy).

All business logic lives in DeliveryService.

Delivery Person endpoints (admin / ERP):
  POST   /delivery/persons                  → register motoboy
  GET    /delivery/persons                  → list active motoboys (?available_only=true)
  GET    /delivery/persons/available        → shortcut: only available
  GET    /delivery/persons/{id}             → motoboy detail
  PUT    /delivery/persons/{id}             → update motoboy details
  PUT    /delivery/persons/{id}/status      → set available | offline
  PUT    /delivery/persons/{id}/location    → update GPS (mobile app)
  DELETE /delivery/persons/{id}             → deactivate (soft delete)

Driver App endpoints (token-based, public):
  POST /delivery/driver/login               → email+password → token
  GET  /delivery/driver/me                  → driver identity
  GET  /delivery/driver/deliveries          → driver's active deliveries

Logistics settings:
  GET  /delivery/settings                   → get settings
  PUT  /delivery/settings                   → update settings

Delivery endpoints:
  POST /delivery/assign             → assign motoboy to order
  GET  /delivery/active             → in-progress deliveries
  GET  /delivery/order/{order_id}   → delivery for a specific order
  GET  /delivery/{id}               → delivery detail
  PUT  /delivery/{id}/status        → advance delivery status
  POST /delivery/{id}/complete      → finalize + proof of delivery
  POST /delivery/{id}/confirm-code  → confirm delivery with 4-digit code
  POST /delivery/{id}/rate          → customer rates delivery (1–5)
"""
import base64

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import ok, created, no_content, err, err_msg
from backend.database import get_db
from backend.routes.admin_auth import get_current_admin
from backend.routes.order_access import require_order_or_admin
from backend.services.delivery_service import DeliveryService
from backend.schemas.delivery import (
    DeliveryPersonCreate,
    DeliveryPersonUpdate,
    DeliveryPersonStatusUpdate,
    DeliveryPersonLocationUpdate,
    DeliveryAssignIn,
    DeliveryStatusUpdate,
    DeliveryCompleteIn,
    DeliveryConfirmIn,
    DeliveryRateIn,
    DriverLoginIn,
    LogisticsSettingsUpdate,
)

router = APIRouter(prefix="/delivery", tags=["delivery"])


# ── Delivery Persons ──────────────────────────────────────────────────────────

@router.post("/persons", status_code=201)
def create_person(
    body: DeliveryPersonCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Register a new delivery person (motoboy)."""
    try:
        person = DeliveryService(db).create_person(
            body.name,
            body.phone,
            body.vehicle_type.value,
            email=body.email,
            cpf=body.cpf,
            cnh=body.cnh,
            pix_key=body.pix_key,
            password=body.password,
        )
        return created(person, "Motoboy cadastrado.")
    except DomainError as exc:
        return err(exc)


@router.get("/persons")
def list_persons(
    available_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """
    List active delivery persons.
    Pass ?available_only=true to see only those ready to receive deliveries.
    """
    try:
        persons = DeliveryService(db).list_persons(available_only=available_only)
        return ok(persons)
    except DomainError as exc:
        return err(exc)


@router.get("/persons/available")
def list_available_persons(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Shortcut: list only available (ready) delivery persons."""
    try:
        return ok(DeliveryService(db).list_persons(available_only=True))
    except DomainError as exc:
        return err(exc)


@router.get("/persons/{person_id}")
def get_person(
    person_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Get a single delivery person by ID."""
    try:
        return ok(DeliveryService(db).get_person(person_id))
    except DomainError as exc:
        return err(exc)


@router.put("/persons/{person_id}/status")
def update_person_status(
    person_id: str,
    body: DeliveryPersonStatusUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """
    Set a delivery person's availability.
    Accepted values: 'available' | 'offline'
    Note: 'busy' is set automatically by DeliveryService.assign().
    """
    try:
        person = DeliveryService(db).set_person_status(person_id, body.status)
        return ok(person, f"Status atualizado para '{body.status}'.")
    except DomainError as exc:
        return err(exc)
    except ValueError as exc:
        from backend.core.response import err_msg
        return err_msg(str(exc), code="InvalidStatus")


@router.put("/persons/{person_id}/location")
def update_person_location(
    person_id: str,
    body: DeliveryPersonLocationUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """
    Update real-time GPS coordinates for a delivery person.
    Called by the mobile app at regular intervals while on duty.
    """
    try:
        person = DeliveryService(db).update_location(person_id, body.lat, body.lng)
        return ok(person)
    except DomainError as exc:
        return err(exc)


@router.put("/persons/{person_id}")
def update_person(
    person_id: str,
    body: DeliveryPersonUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Update motoboy details (name, phone, documents, credentials, etc.)."""
    try:
        person = DeliveryService(db).update_person(person_id, **body.model_dump(exclude_none=True))
        return ok(person, "Motoboy atualizado.")
    except DomainError as exc:
        return err(exc)


@router.delete("/persons/{person_id}", status_code=204)
def deactivate_person(
    person_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Soft-delete a delivery person (sets active=False)."""
    try:
        DeliveryService(db).deactivate_person(person_id)
        return no_content()
    except DomainError as exc:
        return err(exc)


# ── Driver App ────────────────────────────────────────────────────────────────

def _decode_driver_token(authorization: str | None) -> str:
    """Extract person_id from Bearer token. Raises ValueError on failure."""
    if not authorization or not authorization.startswith("Bearer "):
        raise ValueError("Token necessário.")
    try:
        raw = base64.b64decode(authorization[7:]).decode()
        prefix, person_id = raw.split(":", 1)
        if prefix != "driver":
            raise ValueError()
        return person_id
    except Exception:
        raise ValueError("Token inválido.")


@router.post("/driver/login")
def driver_login(body: DriverLoginIn, db: Session = Depends(get_db)):
    """Driver app login — returns a bearer token containing the driver's ID."""
    try:
        person = DeliveryService(db).driver_login(body.email, body.password)
        token = base64.b64encode(f"driver:{person.id}".encode()).decode()
        return ok({"token": token, "person": person})
    except DomainError as exc:
        return err(exc)


@router.get("/driver/me")
def driver_me(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Return driver profile from bearer token."""
    try:
        person_id = _decode_driver_token(authorization)
        person = DeliveryService(db).get_person(person_id)
        return ok(person)
    except (ValueError, DomainError) as exc:
        return err_msg(str(exc), code="Unauthorized", status_code=401)


@router.get("/driver/deliveries")
def driver_deliveries(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Return active + recent deliveries for the logged-in driver."""
    try:
        person_id = _decode_driver_token(authorization)
        deliveries = DeliveryService(db).get_driver_deliveries(person_id)
        return ok(deliveries)
    except (ValueError, DomainError) as exc:
        return err_msg(str(exc), code="Unauthorized", status_code=401)


# ── Logistics Settings ────────────────────────────────────────────────────────

@router.get("/settings")
def get_logistics_settings(db: Session = Depends(get_db), _=Depends(get_current_admin)):
    """Get logistics configuration."""
    try:
        return ok(DeliveryService(db).get_logistics_settings())
    except DomainError as exc:
        return err(exc)


@router.put("/settings")
def update_logistics_settings(
    body: LogisticsSettingsUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Update logistics configuration."""
    try:
        settings = DeliveryService(db).update_logistics_settings(**body.model_dump(exclude_none=True))
        return ok(settings, "Configurações salvas.")
    except DomainError as exc:
        return err(exc)


# ── Deliveries ────────────────────────────────────────────────────────────────

@router.post("/assign", status_code=201)
def assign_delivery(
    body: DeliveryAssignIn,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """
    Assign a delivery person to an order.

    Preconditions:
      - Order must be in 'preparing' or 'ready_for_pickup'
        (guarantees payment was confirmed — state machine enforces this)
      - Delivery person must be active and 'available'
      - No active delivery already assigned to the order

    On success:
      - Order advances to 'on_the_way'
      - Motoboy status changes to 'busy'
      - DeliveryAssigned event published → push notification to customer
    """
    try:
        delivery = DeliveryService(db).assign(
            body.order_id,
            body.delivery_person_id,
            estimated_minutes=body.estimated_minutes,
        )
        return created(delivery, "Motoboy atribuído. Pedido a caminho!")
    except DomainError as exc:
        return err(exc)


@router.get("/active")
def list_active_deliveries(
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Return all deliveries currently in progress (assigned / picked_up / on_the_way)."""
    try:
        return ok(DeliveryService(db).list_active())
    except DomainError as exc:
        return err(exc)


@router.get("/order/{order_id}")
def get_delivery_by_order(
    order_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Get the delivery record linked to a specific order."""
    try:
        return ok(DeliveryService(db).get_by_order(order_id))
    except DomainError as exc:
        return err(exc)


@router.get("/{delivery_id}")
def get_delivery(
    delivery_id: str,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """Get a delivery by its own ID."""
    try:
        return ok(DeliveryService(db).get(delivery_id))
    except DomainError as exc:
        return err(exc)


@router.put("/{delivery_id}/status")
def update_delivery_status(
    delivery_id: str,
    body: DeliveryStatusUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """
    Advance a delivery through its state machine.

    Valid transitions:
      assigned → picked_up → on_the_way → delivered → completed
      any      → failed | cancelled

    When status reaches 'delivered':
      - Order advances to 'delivered' automatically
      - Loyalty points are awarded to the customer
    """
    try:
        delivery = DeliveryService(db).update_status(delivery_id, body.status)
        return ok(delivery, f"Entrega atualizada para '{body.status}'.")
    except DomainError as exc:
        return err(exc)


@router.post("/{delivery_id}/complete")
def complete_delivery(
    delivery_id: str,
    body: DeliveryCompleteIn,
    db: Session = Depends(get_db),
    _=Depends(get_current_admin),
):
    """
    Mark a delivery as completed and record proof of delivery.

    On success:
      - Motoboy status returns to 'available'
      - total_deliveries counter is incremented
      - DeliveryCompleted event published → ERP + push notification
    """
    try:
        delivery = DeliveryService(db).complete(
            delivery_id,
            recipient_name=body.recipient_name,
            delivery_photo_url=body.delivery_photo_url,
            notes=body.notes,
        )
        return ok(delivery, "Entrega finalizada.")
    except DomainError as exc:
        return err(exc)


@router.post("/{delivery_id}/confirm-code")
def confirm_delivery_code(
    delivery_id: str,
    body: DeliveryConfirmIn,
    db: Session = Depends(get_db),
):
    """
    Confirm a delivery using the 4-digit code shown to the customer.
    The driver submits this code at the customer's door.
    No authentication required — the code itself acts as proof.
    """
    try:
        delivery = DeliveryService(db).confirm_delivery_code(delivery_id, body.code)
        return ok(delivery, "Entrega confirmada com sucesso!")
    except DomainError as exc:
        return err(exc)


@router.post("/{delivery_id}/rate")
def rate_delivery(
    delivery_id: str,
    body: DeliveryRateIn,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_customer_phone: str | None = Header(default=None),
    x_customer_email: str | None = Header(default=None),
):
    """
    Customer rates the delivery (1–5 stars).
    Updates the motoboy's weighted average rating automatically.
    """
    try:
        service = DeliveryService(db)
        existing_delivery = service.get(delivery_id)
        require_order_or_admin(
            existing_delivery.order,
            db,
            authorization,
            x_customer_phone,
            x_customer_email,
        )
        delivery = service.rate(delivery_id, body.rating, body.comment)
        return ok(delivery, "Avaliação registrada. Obrigado!")
    except DomainError as exc:
        return err(exc)

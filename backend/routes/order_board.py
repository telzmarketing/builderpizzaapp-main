"""Public device pairing/read routes and RBAC-protected order board administration."""
from fastapi import APIRouter, Cookie, Depends, Header
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import created, err, ok
from backend.database import get_db
from backend.schemas.order_board import (
    OrderBoardActivationApproveIn,
    OrderBoardDeviceRenameIn,
    OrderBoardSettingsIn,
)
from backend.services.order_board_service import OrderBoardService


router = APIRouter(prefix="/order-board", tags=["order-board"])
admin_router = APIRouter(prefix="/admin/order-board", tags=["admin-order-board"])

DEVICE_COOKIE = "order_board_device"
ACTIVATION_COOKIE = "order_board_activation"
COOKIE_PATH = "/api/order-board"


def _admin_service(db: Session, actor: AuthorizedTenantActor) -> OrderBoardService:
    return OrderBoardService(db, actor.tenant_context)


@router.post("/activations")
def create_activation(db: Session = Depends(get_db)):
    try:
        payload = OrderBoardService(db).create_activation()
        claim_token = payload.pop("_claim_token")
        response = created(payload)
        response.set_cookie(
            ACTIVATION_COOKIE,
            claim_token,
            max_age=600,
            httponly=True,
            secure=True,
            samesite="strict",
            path=COOKIE_PATH,
        )
        response.headers["Cache-Control"] = "no-store"
        return response
    except DomainError as exc:
        return err(exc)


@router.get("/activations/{activation_id}/status")
def activation_status(
    activation_id: str,
    db: Session = Depends(get_db),
    claim_token: str | None = Cookie(default=None, alias=ACTIVATION_COOKIE),
):
    try:
        payload, device_credential = OrderBoardService(db).activation_status(
            activation_id, claim_token or ""
        )
        response = ok(payload)
        response.headers["Cache-Control"] = "no-store"
        if device_credential:
            response.set_cookie(
                DEVICE_COOKIE,
                device_credential,
                max_age=60 * 60 * 24 * 365,
                httponly=True,
                secure=True,
                samesite="strict",
                path=COOKIE_PATH,
            )
            response.delete_cookie(ACTIVATION_COOKIE, path=COOKIE_PATH)
        return response
    except DomainError as exc:
        return err(exc)


def _device(service: OrderBoardService, credential: str | None):
    return service.authenticate_device(credential)


@router.get("/snapshot")
def snapshot(
    db: Session = Depends(get_db),
    credential: str | None = Cookie(default=None, alias=DEVICE_COOKIE),
    if_none_match: str | None = Header(default=None),
):
    try:
        service = OrderBoardService(db)
        payload, etag = service.snapshot(_device(service, credential))
        headers = {"ETag": etag, "Cache-Control": "no-store"}
        if if_none_match == etag:
            return FastAPIResponse(status_code=304, headers=headers)
        response = ok(payload)
        response.headers.update(headers)
        return response
    except DomainError as exc:
        response = err(exc)
        response.headers["Cache-Control"] = "no-store"
        return response


@router.post("/heartbeat")
def heartbeat(
    db: Session = Depends(get_db),
    credential: str | None = Cookie(default=None, alias=DEVICE_COOKIE),
):
    try:
        service = OrderBoardService(db)
        response = ok(service.heartbeat(_device(service, credential)))
        response.headers["Cache-Control"] = "no-store"
        return response
    except DomainError as exc:
        return err(exc)


@admin_router.get("/settings")
def get_settings(
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("pedidos", "view")),
):
    return ok(_admin_service(db, actor).get_settings())


@admin_router.put("/settings")
def update_settings(
    body: OrderBoardSettingsIn,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("pedidos", "edit")),
):
    return ok(_admin_service(db, actor).update_settings(body))


@admin_router.get("/devices")
def list_devices(
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("pedidos", "view")),
):
    return ok(_admin_service(db, actor).list_devices())


@admin_router.patch("/devices/{device_id}")
def rename_device(
    device_id: str,
    body: OrderBoardDeviceRenameIn,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("pedidos", "edit")),
):
    try:
        return ok(_admin_service(db, actor).rename_device(device_id, body.name))
    except DomainError as exc:
        return err(exc)


@admin_router.post("/devices/{device_id}/revoke")
def revoke_device(
    device_id: str,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("pedidos", "edit")),
):
    try:
        return ok(_admin_service(db, actor).revoke_device(device_id))
    except DomainError as exc:
        return err(exc)


@admin_router.delete("/devices/{device_id}")
def delete_device(
    device_id: str,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("pedidos", "edit")),
):
    try:
        return ok(_admin_service(db, actor).delete_device(device_id))
    except DomainError as exc:
        return err(exc)


@admin_router.post("/activations/approve")
def approve_activation(
    body: OrderBoardActivationApproveIn,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("pedidos", "edit")),
):
    try:
        return created(_admin_service(db, actor).approve_activation(
            body.code, body.name, actor_id=actor.user_id
        ))
    except DomainError as exc:
        return err(exc)

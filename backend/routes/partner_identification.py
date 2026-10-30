"""Tenant-scoped CRUD for partner names and logos."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import created, err, no_content, ok
from backend.database import get_db
from backend.schemas.partner_identification import (
    PartnerIdentificationBatchIn,
    PartnerIdentificationIn,
)
from backend.services.partner_identification_service import PartnerIdentificationService


router = APIRouter(prefix="/admin/partner-identifications", tags=["partner-identifications"])
compat_router = APIRouter(prefix="/partner-identification", tags=["partner-identifications"])


def _service(db: Session, actor: AuthorizedTenantActor) -> PartnerIdentificationService:
    return PartnerIdentificationService(db, actor.tenant_context)


@router.get("")
def list_partner_identifications(
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("pedidos", "view")),
):
    return ok(_service(db, actor).list())


@router.get("/{partner_code}")
def get_partner_identification(
    partner_code: str,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("pedidos", "view")),
):
    try:
        return ok(_service(db, actor).get(partner_code))
    except DomainError as exc:
        return err(exc)


@router.post("", status_code=201)
def create_partner_identification(
    body: PartnerIdentificationIn,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("pedidos", "edit")),
):
    try:
        return created(_service(db, actor).create(body))
    except DomainError as exc:
        return err(exc)


@router.put("/{partner_code}")
def update_partner_identification(
    partner_code: str,
    body: PartnerIdentificationIn,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("pedidos", "edit")),
):
    try:
        return ok(_service(db, actor).update(partner_code, body))
    except DomainError as exc:
        return err(exc)


@router.delete("/{partner_code}", status_code=204)
def delete_partner_identification(
    partner_code: str,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("pedidos", "edit")),
):
    try:
        _service(db, actor).delete(partner_code)
        return no_content()
    except DomainError as exc:
        return err(exc)


@compat_router.get("")
def list_partner_identifications_compat(
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("pedidos", "view")),
):
    return ok({"partners": [
        {
            "order_origin": row["partner_code"],
            "display_name": row["display_name"],
            "logo_url": row["logo_url"],
            "enabled": row["active"],
        }
        for row in _service(db, actor).list()
    ]})


@compat_router.put("")
def update_partner_identifications_compat(
    body: PartnerIdentificationBatchIn,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("pedidos", "edit")),
):
    service = _service(db, actor)
    result = []
    for item in body.partners:
        result.append(service.update(item.order_origin, PartnerIdentificationIn(
            partner_code=item.order_origin,
            display_name=item.display_name,
            logo_url=item.logo_url,
            active=item.enabled,
        )))
    return ok({"partners": [
        {
            "order_origin": row["partner_code"],
            "display_name": row["display_name"],
            "logo_url": row["logo_url"],
            "enabled": row["active"],
        }
        for row in result
    ]})

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import err
from backend.core.tenant_context import TenantContext
from backend.core.tenant_route_context import operation_tenant_id, panel_operation_context
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.admin_auth import get_current_admin
from backend.schemas.fiscal import (
    FiscalCancelIn,
    FiscalCertificateIn,
    FiscalCertificateOut,
    FiscalCompanyIn,
    FiscalCompanyOut,
    FiscalDocumentFromOrderIn,
    FiscalDocumentOut,
    FiscalInvalidateIn,
    FiscalOverviewOut,
    FiscalProductProfileIn,
    FiscalProductProfileOut,
    FiscalSeriesIn,
    FiscalSeriesOut,
)
from backend.services.fiscal_service import FiscalService

router = APIRouter(prefix="/gestao/fiscal", tags=["gestao-fiscal"])


def service(db: Session, tenant_context: TenantContext | None) -> FiscalService:
    return FiscalService(db, operation_tenant_id(tenant_context))


@router.get("/overview", response_model=FiscalOverviewOut)
def overview(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    return service(db, tenant_context).overview()


@router.put("/company", response_model=FiscalCompanyOut)
def upsert_company(body: FiscalCompanyIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).upsert_company(body)
    except DomainError as exc:
        return err(exc)


@router.put("/certificate", response_model=FiscalCertificateOut)
def upsert_certificate(body: FiscalCertificateIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).upsert_certificate(body)
    except DomainError as exc:
        return err(exc)


@router.post("/series", response_model=FiscalSeriesOut, status_code=201)
def create_series(body: FiscalSeriesIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).create_series(body)
    except DomainError as exc:
        return err(exc)


@router.put("/series/{series_id}", response_model=FiscalSeriesOut)
def update_series(series_id: str, body: FiscalSeriesIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).update_series(series_id, body)
    except DomainError as exc:
        return err(exc)


@router.post("/series/{series_id}/invalidate-number", response_model=FiscalDocumentOut)
def invalidate_number(series_id: str, body: FiscalInvalidateIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).invalidate_number(series_id, body)
    except DomainError as exc:
        return err(exc)


@router.put("/products/{product_id}/tax-profile", response_model=FiscalProductProfileOut)
def upsert_product_profile(product_id: str, body: FiscalProductProfileIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).upsert_product_profile(product_id, body)
    except DomainError as exc:
        return err(exc)


@router.post("/documents/from-order/{order_id}", response_model=FiscalDocumentOut, status_code=201)
def create_document_from_order(order_id: str, body: FiscalDocumentFromOrderIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).create_document_from_order(order_id, body)
    except DomainError as exc:
        return err(exc)


@router.post("/documents/{document_id}/sign", response_model=FiscalDocumentOut)
def sign_document(document_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).sign_document(document_id)
    except DomainError as exc:
        return err(exc)


@router.post("/documents/{document_id}/transmit", response_model=FiscalDocumentOut)
def transmit_document(document_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).transmit_document(document_id)
    except DomainError as exc:
        return err(exc)


@router.post("/documents/{document_id}/consult", response_model=FiscalDocumentOut)
def consult_document(document_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).consult_document(document_id)
    except DomainError as exc:
        return err(exc)


@router.post("/documents/{document_id}/cancel", response_model=FiscalDocumentOut)
def cancel_document(document_id: str, body: FiscalCancelIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).cancel_document(document_id, body)
    except DomainError as exc:
        return err(exc)

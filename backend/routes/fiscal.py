from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import err
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


def service(db: Session) -> FiscalService:
    return FiscalService(db)


@router.get("/overview", response_model=FiscalOverviewOut)
def overview(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).overview()


@router.put("/company", response_model=FiscalCompanyOut)
def upsert_company(body: FiscalCompanyIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).upsert_company(body)
    except DomainError as exc:
        return err(exc)


@router.put("/certificate", response_model=FiscalCertificateOut)
def upsert_certificate(body: FiscalCertificateIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).upsert_certificate(body)
    except DomainError as exc:
        return err(exc)


@router.post("/series", response_model=FiscalSeriesOut, status_code=201)
def create_series(body: FiscalSeriesIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).create_series(body)
    except DomainError as exc:
        return err(exc)


@router.put("/series/{series_id}", response_model=FiscalSeriesOut)
def update_series(series_id: str, body: FiscalSeriesIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).update_series(series_id, body)
    except DomainError as exc:
        return err(exc)


@router.post("/series/{series_id}/invalidate-number", response_model=FiscalDocumentOut)
def invalidate_number(series_id: str, body: FiscalInvalidateIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).invalidate_number(series_id, body)
    except DomainError as exc:
        return err(exc)


@router.put("/products/{product_id}/tax-profile", response_model=FiscalProductProfileOut)
def upsert_product_profile(product_id: str, body: FiscalProductProfileIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).upsert_product_profile(product_id, body)
    except DomainError as exc:
        return err(exc)


@router.post("/documents/from-order/{order_id}", response_model=FiscalDocumentOut, status_code=201)
def create_document_from_order(order_id: str, body: FiscalDocumentFromOrderIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).create_document_from_order(order_id, body)
    except DomainError as exc:
        return err(exc)


@router.post("/documents/{document_id}/sign", response_model=FiscalDocumentOut)
def sign_document(document_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).sign_document(document_id)
    except DomainError as exc:
        return err(exc)


@router.post("/documents/{document_id}/transmit", response_model=FiscalDocumentOut)
def transmit_document(document_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).transmit_document(document_id)
    except DomainError as exc:
        return err(exc)


@router.post("/documents/{document_id}/consult", response_model=FiscalDocumentOut)
def consult_document(document_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).consult_document(document_id)
    except DomainError as exc:
        return err(exc)


@router.post("/documents/{document_id}/cancel", response_model=FiscalDocumentOut)
def cancel_document(document_id: str, body: FiscalCancelIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).cancel_document(document_id, body)
    except DomainError as exc:
        return err(exc)

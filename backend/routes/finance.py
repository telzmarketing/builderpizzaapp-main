from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import err, no_content
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.admin_auth import get_current_admin
from backend.schemas.finance import (
    FinanceAccountIn,
    FinanceAccountOut,
    FinanceCategoryIn,
    FinanceCategoryOut,
    FinanceCounterpartyIn,
    FinanceCounterpartyOut,
    FinanceOverviewOut,
    FinanceSettlementIn,
    FinanceTransactionIn,
    FinanceTransactionOut,
)
from backend.services.finance_service import FinanceService

router = APIRouter(prefix="/gestao/finance", tags=["gestao-finance"])


def service(db: Session) -> FinanceService:
    return FinanceService(db)


@router.get("/overview", response_model=FinanceOverviewOut)
def overview(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).overview()


@router.get("/accounts", response_model=list[FinanceAccountOut])
def list_accounts(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).list_accounts()


@router.post("/accounts", response_model=FinanceAccountOut, status_code=201)
def create_account(body: FinanceAccountIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).create_account(body)


@router.put("/accounts/{account_id}", response_model=FinanceAccountOut)
def update_account(account_id: str, body: FinanceAccountIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).update_account(account_id, body)
    except DomainError as exc:
        return err(exc)


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        service(db).delete_account(account_id)
        return no_content()
    except DomainError as exc:
        return err(exc)


@router.get("/categories", response_model=list[FinanceCategoryOut])
def list_categories(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).list_categories()


@router.post("/categories", response_model=FinanceCategoryOut, status_code=201)
def create_category(body: FinanceCategoryIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).create_category(body)
    except DomainError as exc:
        return err(exc)


@router.put("/categories/{category_id}", response_model=FinanceCategoryOut)
def update_category(category_id: str, body: FinanceCategoryIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).update_category(category_id, body)
    except DomainError as exc:
        return err(exc)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        service(db).delete_category(category_id)
        return no_content()
    except DomainError as exc:
        return err(exc)


@router.get("/counterparties", response_model=list[FinanceCounterpartyOut])
def list_counterparties(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).list_counterparties()


@router.post("/counterparties", response_model=FinanceCounterpartyOut, status_code=201)
def create_counterparty(body: FinanceCounterpartyIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).create_counterparty(body)


@router.put("/counterparties/{counterparty_id}", response_model=FinanceCounterpartyOut)
def update_counterparty(counterparty_id: str, body: FinanceCounterpartyIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).update_counterparty(counterparty_id, body)
    except DomainError as exc:
        return err(exc)


@router.delete("/counterparties/{counterparty_id}", status_code=204)
def delete_counterparty(counterparty_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        service(db).delete_counterparty(counterparty_id)
        return no_content()
    except DomainError as exc:
        return err(exc)


@router.get("/transactions", response_model=list[FinanceTransactionOut])
def list_transactions(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    return service(db).list_transactions()


@router.post("/transactions", response_model=FinanceTransactionOut, status_code=201)
def create_transaction(body: FinanceTransactionIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).create_transaction(body, admin.id)
    except DomainError as exc:
        return err(exc)


@router.put("/transactions/{transaction_id}", response_model=FinanceTransactionOut)
def update_transaction(transaction_id: str, body: FinanceTransactionIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).update_transaction(transaction_id, body, admin.id)
    except DomainError as exc:
        return err(exc)


@router.post("/transactions/{transaction_id}/settle", response_model=FinanceTransactionOut)
def settle_transaction(transaction_id: str, body: FinanceSettlementIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin)):
    try:
        return service(db).settle_transaction(transaction_id, body, admin.id)
    except DomainError as exc:
        return err(exc)


@router.delete("/transactions/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin)):
    try:
        service(db).delete_transaction(transaction_id)
        return no_content()
    except DomainError as exc:
        return err(exc)

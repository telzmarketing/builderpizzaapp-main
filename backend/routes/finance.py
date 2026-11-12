from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import err, no_content
from backend.core.tenant_context import TenantContext
from backend.core.tenant_route_context import operation_tenant_id, panel_operation_context
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.admin_auth import get_current_admin
from backend.schemas.finance import (
    FinanceAccountIn,
    FinanceAccountOut,
    FinanceBankStatementImportIn,
    FinanceBankStatementLineOut,
    FinanceBankMatchIn,
    FinanceBankReconciliationEventOut,
    FinanceBankReconciliationReasonIn,
    FinanceBankReconciliationLineOut,
    FinanceBankStatementOut,
    FinanceCategoryIn,
    FinanceCategoryOut,
    FinanceCounterpartyIn,
    FinanceCounterpartyOut,
    FinanceOverviewOut,
    FinanceObligationFromFiscalIn,
    FinanceObligationOut,
    FinanceSettlementIn,
    FinanceTransactionIn,
    FinanceTransactionOut,
)
from backend.services.finance_service import FinanceService

router = APIRouter(prefix="/gestao/finance", tags=["gestao-finance"])


def service(db: Session, tenant_context: TenantContext | None) -> FinanceService:
    return FinanceService(db, operation_tenant_id(tenant_context), tenant_context)


@router.get("/overview", response_model=FinanceOverviewOut)
def overview(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    return service(db, tenant_context).overview()


@router.get("/accounts", response_model=list[FinanceAccountOut])
def list_accounts(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    return service(db, tenant_context).list_accounts()


@router.post("/accounts", response_model=FinanceAccountOut, status_code=201)
def create_account(body: FinanceAccountIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    return service(db, tenant_context).create_account(body)


@router.get("/bank-statements", response_model=list[FinanceBankStatementOut])
def list_bank_statements(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    return service(db, tenant_context).list_bank_statements()


@router.get("/bank-statements/{statement_id}/lines", response_model=list[FinanceBankStatementLineOut])
def list_bank_statement_lines(statement_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).list_bank_statement_lines(statement_id)
    except DomainError as exc:
        return err(exc)


@router.get("/bank-statements/{statement_id}/reconciliation", response_model=list[FinanceBankReconciliationLineOut])
def list_bank_reconciliation(statement_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).list_bank_reconciliation(statement_id)
    except DomainError as exc:
        return err(exc)


@router.post("/bank-statement-lines/{line_id}/match", response_model=FinanceBankStatementLineOut)
def match_bank_statement_line(line_id: str, body: FinanceBankMatchIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).match_bank_statement_line(line_id, body, admin.id)
    except DomainError as exc:
        return err(exc)


@router.post("/bank-statement-lines/{line_id}/unmatch", response_model=FinanceBankStatementLineOut)
def unmatch_bank_statement_line(line_id: str, body: FinanceBankReconciliationReasonIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).unmatch_bank_statement_line(line_id, body, admin.id)
    except DomainError as exc:
        return err(exc)


@router.post("/bank-statement-lines/{line_id}/ignore", response_model=FinanceBankStatementLineOut)
def ignore_bank_statement_line(line_id: str, body: FinanceBankReconciliationReasonIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).ignore_bank_statement_line(line_id, body, admin.id)
    except DomainError as exc:
        return err(exc)


@router.get("/bank-statement-lines/{line_id}/events", response_model=list[FinanceBankReconciliationEventOut])
def list_reconciliation_events(line_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).list_reconciliation_events(line_id)
    except DomainError as exc:
        return err(exc)


@router.post("/bank-statements/import", response_model=FinanceBankStatementOut, status_code=201)
def import_bank_statement(body: FinanceBankStatementImportIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).import_bank_statement(body, admin.id)
    except DomainError as exc:
        return err(exc)


@router.put("/accounts/{account_id}", response_model=FinanceAccountOut)
def update_account(account_id: str, body: FinanceAccountIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).update_account(account_id, body)
    except DomainError as exc:
        return err(exc)


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        service(db, tenant_context).delete_account(account_id)
        return no_content()
    except DomainError as exc:
        return err(exc)


@router.get("/categories", response_model=list[FinanceCategoryOut])
def list_categories(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    return service(db, tenant_context).list_categories()


@router.post("/categories", response_model=FinanceCategoryOut, status_code=201)
def create_category(body: FinanceCategoryIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).create_category(body)
    except DomainError as exc:
        return err(exc)


@router.put("/categories/{category_id}", response_model=FinanceCategoryOut)
def update_category(category_id: str, body: FinanceCategoryIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).update_category(category_id, body)
    except DomainError as exc:
        return err(exc)


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        service(db, tenant_context).delete_category(category_id)
        return no_content()
    except DomainError as exc:
        return err(exc)


@router.get("/counterparties", response_model=list[FinanceCounterpartyOut])
def list_counterparties(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    return service(db, tenant_context).list_counterparties()


@router.post("/counterparties", response_model=FinanceCounterpartyOut, status_code=201)
def create_counterparty(body: FinanceCounterpartyIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    return service(db, tenant_context).create_counterparty(body)


@router.put("/counterparties/{counterparty_id}", response_model=FinanceCounterpartyOut)
def update_counterparty(counterparty_id: str, body: FinanceCounterpartyIn, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).update_counterparty(counterparty_id, body)
    except DomainError as exc:
        return err(exc)


@router.delete("/counterparties/{counterparty_id}", status_code=204)
def delete_counterparty(counterparty_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        service(db, tenant_context).delete_counterparty(counterparty_id)
        return no_content()
    except DomainError as exc:
        return err(exc)


@router.get("/transactions", response_model=list[FinanceTransactionOut])
def list_transactions(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    return service(db, tenant_context).list_transactions()


@router.get("/obligations", response_model=list[FinanceObligationOut])
def list_obligations(
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("finance", "view")),
):
    return FinanceService(db, actor.tenant_id, actor.tenant_context).list_obligations()


@router.post("/fiscal-documents/{document_id}/obligation", response_model=FinanceObligationOut, status_code=201)
def create_fiscal_obligation(
    document_id: str,
    body: FinanceObligationFromFiscalIn,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=160),
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("finance", "create")),
):
    try:
        return FinanceService(db, actor.tenant_id, actor.tenant_context).create_obligation_from_fiscal_document(
            document_id, body, idempotency_key, actor.user_id,
        )
    except DomainError as exc:
        return err(exc)


@router.post("/obligations/{obligation_id}/reconcile", response_model=FinanceObligationOut)
def reconcile_obligation(
    obligation_id: str,
    db: Session = Depends(get_db),
    actor: AuthorizedTenantActor = Depends(require_rbac_permission("finance", "edit")),
):
    try:
        return FinanceService(db, actor.tenant_id, actor.tenant_context).reconcile_obligation(obligation_id)
    except DomainError as exc:
        return err(exc)


@router.post("/transactions", response_model=FinanceTransactionOut, status_code=201)
def create_transaction(body: FinanceTransactionIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).create_transaction(body, admin.id)
    except DomainError as exc:
        return err(exc)


@router.put("/transactions/{transaction_id}", response_model=FinanceTransactionOut)
def update_transaction(transaction_id: str, body: FinanceTransactionIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).update_transaction(transaction_id, body, admin.id)
    except DomainError as exc:
        return err(exc)


@router.post("/transactions/{transaction_id}/settle", response_model=FinanceTransactionOut)
def settle_transaction(transaction_id: str, body: FinanceSettlementIn, db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        return service(db, tenant_context).settle_transaction(transaction_id, body, admin.id)
    except DomainError as exc:
        return err(exc)


@router.delete("/transactions/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: str, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    try:
        service(db, tenant_context).delete_transaction(transaction_id)
        return no_content()
    except DomainError as exc:
        return err(exc)

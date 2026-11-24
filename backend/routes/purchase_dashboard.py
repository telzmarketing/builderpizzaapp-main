from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import err
from backend.core.exceptions import DomainError
from backend.database import get_db
from backend.schemas.purchase_dashboard import PurchaseDashboardOut
from backend.services.purchase_dashboard_service import PurchaseDashboardService

router = APIRouter(prefix="/gestao/purchases/dashboard", tags=["purchase-dashboard"])

@router.get("", response_model=PurchaseDashboardOut)
def purchase_dashboard(date_from: date | None = Query(default=None), date_to: date | None = Query(default=None), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "view")), finance_actor: AuthorizedTenantActor = Depends(require_rbac_permission("finance", "view"))):
    try:
        return PurchaseDashboardService(db, actor.tenant_context).dashboard(date_from, date_to)
    except (DomainError, ValueError) as exc:
        return err(exc) if isinstance(exc, DomainError) else err(DomainError(str(exc), code="PurchaseDashboardInvalidPeriod"))

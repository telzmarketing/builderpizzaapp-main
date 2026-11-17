from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import created, ok, err
from backend.core.exceptions import DomainError
from backend.database import get_db
from backend.schemas.app_finance import AppFinanceConfigIn, AppFinanceRuleIn, DeliveryAppOrigin
from backend.services.app_finance_service import DeliveryAppFinanceService

router = APIRouter(prefix="/operations/apps-finance", tags=["delivery-app-finance"])
def svc(db, actor): return DeliveryAppFinanceService(db, actor.tenant_id)
@router.get("")
def list_configs(db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("finance", "view"))): return ok(svc(db, actor).list())
@router.post("")
def create(body: AppFinanceConfigIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("finance", "edit"))):
    try: return created(svc(db, actor).create(body))
    except DomainError as exc: return err(exc)
@router.put("/{config_id}")
def update(config_id: str, body: AppFinanceConfigIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("finance", "edit"))):
    try: return ok(svc(db, actor).update(config_id, body))
    except DomainError as exc: return err(exc)
@router.delete("/{config_id}")
def delete(config_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("finance", "edit"))):
    try: return ok(svc(db, actor).delete(config_id))
    except DomainError as exc: return err(exc)
@router.post("/{config_id}/rules")
def add_rule(config_id: str, body: AppFinanceRuleIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("finance", "edit"))):
    try: return created(svc(db, actor).add_rule(config_id, body))
    except DomainError as exc: return err(exc)
@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("finance", "edit"))):
    try: return ok(svc(db, actor).delete_rule(rule_id))
    except DomainError as exc: return err(exc)

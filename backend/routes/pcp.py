from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.core.response import err, ok
from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.schemas.pcp import PcpPlanApprovalIn, PcpPlanGenerateIn
from backend.services.pcp_service import PcpService

router = APIRouter(prefix="/pcp", tags=["pcp"])
view = require_rbac_permission("inventory", "view")
manage = require_rbac_permission("inventory", "manage")


@router.get("/weekly/{week_start}")
def get_weekly(week_start: date, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(view)):
    try: return ok(PcpService(db, actor).get(week_start))
    except DomainError as exc: return err(exc)


@router.post("/weekly/generate")
def generate_weekly(body: PcpPlanGenerateIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(manage)):
    try: return ok(PcpService(db, actor).generate(body))
    except DomainError as exc: return err(exc)


@router.post("/weekly/{week_start}/approve")
def approve_weekly(week_start: date, body: PcpPlanApprovalIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(manage)):
    try: return ok(PcpService(db, actor).approve(week_start, body))
    except DomainError as exc: return err(exc)

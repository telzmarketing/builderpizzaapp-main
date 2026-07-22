from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.admin_auth import get_current_admin
from backend.core.tenant_context import TenantContext
from backend.core.tenant_route_context import operation_tenant_id, panel_operation_context
from backend.schemas.cmv import CmvOverviewOut
from backend.services.cmv_service import CmvService

router = APIRouter(prefix="/gestao/cmv", tags=["gestao-cmv"])


@router.get("/overview", response_model=CmvOverviewOut)
def overview(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    return CmvService(db, operation_tenant_id(tenant_context)).overview()

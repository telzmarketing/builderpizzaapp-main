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


def _catalog_tenant_id(tenant_context: TenantContext | None) -> str:
    """Use the selected panel tenant; fall back to legacy compatibility only when absent."""
    return tenant_context.tenant_id if tenant_context is not None else operation_tenant_id(None)


@router.get("/overview", response_model=CmvOverviewOut)
def overview(db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), tenant_context: TenantContext | None = Depends(panel_operation_context)):
    return CmvService(db, _catalog_tenant_id(tenant_context), tenant_context).overview()

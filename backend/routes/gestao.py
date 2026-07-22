from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.response import err, ok
from backend.core.tenant_context import TenantContext
from backend.core.tenant_route_context import operation_tenant_id, panel_operation_context
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.admin_auth import get_current_admin
from backend.schemas.gestao import GestaoModuleSettingsUpdate
from backend.services.gestao_service import GestaoService

router = APIRouter(prefix="/gestao", tags=["gestao"])


def service(db: Session, tenant_context: TenantContext | None) -> GestaoService:
    return GestaoService(db, operation_tenant_id(tenant_context))


@router.get("/settings", response_model=None)
def list_settings(
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    return ok({"modules": service(db, tenant_context).list_settings()})


@router.put("/settings/{module_key}", response_model=None)
def update_settings(
    module_key: str,
    body: GestaoModuleSettingsUpdate,
    db: Session = Depends(get_db),
    _admin: AdminUser = Depends(get_current_admin),
    tenant_context: TenantContext | None = Depends(panel_operation_context),
):
    try:
        return ok(
            service(db, tenant_context).update_settings(module_key, body),
            "Configuracao de Gestao atualizada.",
        )
    except DomainError as exc:
        return err(exc)

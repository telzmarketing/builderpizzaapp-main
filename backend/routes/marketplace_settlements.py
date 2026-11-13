from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import require_rbac_permission
from backend.core.response import err, ok
from backend.core.tenant_route_context import operation_tenant_id, panel_operation_context
from backend.database import get_db
from backend.models.admin import AdminUser
from backend.routes.admin_auth import get_current_admin
from backend.schemas.marketplace_settlement import MarketplaceProvider, MarketplaceSettlementIn, MarketplaceSettlementOut, MarketplaceSettlementStatus
from backend.services.marketplace_settlement_service import MarketplaceSettlementService


router = APIRouter(prefix="/gestao/marketplace-settlements", tags=["marketplace-settlements"])
view_permission = require_rbac_permission("pedidos", "view")
edit_permission = require_rbac_permission("pedidos", "edit")


def _service(db: Session, context):
    return MarketplaceSettlementService(db, operation_tenant_id(context))


@router.get("", response_model=list[MarketplaceSettlementOut], dependencies=[Depends(view_permission)])
def list_settlements(order_id: str | None = None, provider: MarketplaceProvider | None = None, status: MarketplaceSettlementStatus | None = None, db: Session = Depends(get_db), _admin: AdminUser = Depends(get_current_admin), context=Depends(panel_operation_context)):
    return _service(db, context).list(order_id=order_id, provider=provider, status=status)


@router.post("/orders/{order_id}", response_model=MarketplaceSettlementOut, status_code=201, dependencies=[Depends(edit_permission)])
def create_settlement(order_id: str, body: MarketplaceSettlementIn, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), db: Session = Depends(get_db), admin: AdminUser = Depends(get_current_admin), context=Depends(panel_operation_context)):
    try:
        return _service(db, context).create(order_id, body, idempotency_key or "", admin.id)
    except DomainError as exc:
        return err(exc)

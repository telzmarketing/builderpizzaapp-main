from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.rbac_authorization import AuthorizedTenantActor, require_rbac_permission
from backend.core.response import err
from backend.database import get_db
from backend.schemas.inventory_portion import InventoryPortionConfigIn, InventoryPortionConfigOut
from backend.services.inventory_portion_service import InventoryPortionConfigService

router = APIRouter(prefix="/gestao/inventory/v1/portion-configs", tags=["inventory-portioning"])


def invoke(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except DomainError as exc:
        return err(exc)


def service(db: Session, actor: AuthorizedTenantActor) -> InventoryPortionConfigService:
    return InventoryPortionConfigService(db, actor.tenant_id, actor.user_id)


@router.get("", response_model=list[InventoryPortionConfigOut])
def list_configs(active: bool | None = Query(default=None), db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "view"))):
    return [serialize(row) for row in service(db, actor).list(active=active)]


@router.get("/{config_id}", response_model=InventoryPortionConfigOut)
def get_config(config_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "view"))):
    return invoke(lambda: serialize(service(db, actor).get(config_id)))


@router.post("", status_code=201, response_model=InventoryPortionConfigOut)
def create_config(body: InventoryPortionConfigIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "create")), key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200)):
    return invoke(lambda: serialize(service(db, actor).create(body, key)))


@router.put("/{config_id}", response_model=InventoryPortionConfigOut)
def update_config(config_id: str, body: InventoryPortionConfigIn, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "edit")), key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200)):
    return invoke(lambda: serialize(service(db, actor).update(config_id, body, key)))


@router.delete("/{config_id}", response_model=InventoryPortionConfigOut)
def deactivate_config(config_id: str, db: Session = Depends(get_db), actor: AuthorizedTenantActor = Depends(require_rbac_permission("inventory", "manage")), key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200)):
    return invoke(lambda: serialize(service(db, actor).deactivate(config_id, key)))


def serialize(row):
    return InventoryPortionConfigOut(
        id=row.id,
        tenant_id=row.tenant_id,
        source_item_id=row.source_item_id,
        source_item_name=row.source_item.name if row.source_item else None,
        output_item_id=row.output_item_id,
        output_item_name=row.output_item.name if row.output_item else None,
        output_item_sku=row.output_item.sku if row.output_item else None,
        usage=row.usage,
        portion_weight=row.portion_weight,
        unit_id=row.unit_id,
        unit_symbol=row.unit.symbol if row.unit else None,
        reference_fraction=row.reference_fraction,
        size=row.size,
        min_stock=row.min_stock,
        target_stock=row.target_stock,
        shelf_life_days=row.shelf_life_days,
        yield_percent=row.yield_percent,
        loss_percent=row.loss_percent,
        active=row.active,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )

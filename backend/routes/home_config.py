import json
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.home_config import HomeCatalogConfig
from backend.schemas.home_config import HomeCatalogConfigOut, HomeCatalogConfigUpdate
from backend.routes.admin_auth import get_current_admin
from backend.core.tenant_context import TenantContext
from backend.core.tenant_ownership import assign_tenant_on_create, identity_catalog_enforcement_enabled, scope_query_to_tenant
from backend.core.tenant_runtime import resolve_panel_tenant_context, resolve_public_tenant_context

router = APIRouter(prefix="/home-config", tags=["home-config"])


def _get_or_create(db: Session, context: TenantContext | None) -> HomeCatalogConfig:
    enabled = identity_catalog_enforcement_enabled()
    config_id = f"home-config-{context.tenant_id}" if enabled and context else "default"
    query = scope_query_to_tenant(db.query(HomeCatalogConfig), HomeCatalogConfig, context, enabled=enabled)
    config = query.filter(HomeCatalogConfig.id == config_id).first()
    if not config:
        config = HomeCatalogConfig(id=config_id)
        assign_tenant_on_create(config, context, enabled=enabled)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.get("", response_model=HomeCatalogConfigOut)
def get_home_config(request: Request, db: Session = Depends(get_db)):
    return _get_or_create(db, resolve_public_tenant_context(request, db))


@router.put("", response_model=HomeCatalogConfigOut)
def update_home_config(
    body: HomeCatalogConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    config = _get_or_create(db, resolve_panel_tenant_context(request, db, admin))
    if body.mode is not None:
        config.mode = body.mode
    if body.selected_categories is not None:
        config.selected_categories = json.dumps(body.selected_categories)
    if body.selected_product_ids is not None:
        config.selected_product_ids = json.dumps(body.selected_product_ids)
    if body.show_promotions is not None:
        config.show_promotions = body.show_promotions
    db.commit()
    db.refresh(config)
    return config

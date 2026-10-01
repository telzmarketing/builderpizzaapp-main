import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.core.tenant_runtime import resolve_panel_tenant_context, resolve_public_tenant_context
from backend.routes.admin_auth import get_current_admin
from backend.models.admin import AdminUser
from backend.services.campaign_service import CampaignService
from backend.schemas.campaign import (
    CampaignCreate, CampaignUpdate, CampaignOut,
    CampaignProductCreate, CampaignProductUpdate, CampaignProductOut,
    PromotionalKitCreate, PromotionalKitUpdate, PromotionalKitOut,
    KitItemCreate, KitItemOut,
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


def _require_admin(request: Request, db: Session) -> AdminUser:
    return get_current_admin(
        request=request,
        authorization=request.headers.get("authorization"),
        db=db,
    )


# ── Campaigns ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[CampaignOut])
def list_campaigns(
    request: Request,
    published_only: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    context = (
        resolve_public_tenant_context(request, db)
        if published_only
        else resolve_panel_tenant_context(request, db, _require_admin(request, db))
    )
    return CampaignService(db, context).list_campaigns(published_only=published_only)


@router.get("/slug/{slug}", response_model=CampaignOut)
def get_campaign_by_slug(slug: str, request: Request, db: Session = Depends(get_db)):
    campaign = CampaignService(db, resolve_public_tenant_context(request, db)).get_public_by_slug(slug)
    if not campaign:
        raise HTTPException(404, "Campanha não encontrada.")
    return campaign


@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign(
    campaign_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    campaign = CampaignService(db, resolve_panel_tenant_context(request, db, admin)).get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(404, "Campanha não encontrada.")
    return campaign


@router.post("", response_model=CampaignOut, status_code=201)
def create_campaign(
    body: CampaignCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    return CampaignService(db, resolve_panel_tenant_context(request, db, admin)).create_campaign(body)


@router.put("/{campaign_id}", response_model=CampaignOut)
def update_campaign(
    campaign_id: str,
    body: CampaignUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    return CampaignService(db, resolve_panel_tenant_context(request, db, admin)).update_campaign(campaign_id, body)


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(
    campaign_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    CampaignService(db, resolve_panel_tenant_context(request, db, admin)).delete_campaign(campaign_id)


# ── Campaign Products ─────────────────────────────────────────────────────────

@router.get("/{campaign_id}/products", response_model=list[CampaignProductOut])
def list_campaign_products(campaign_id: str, request: Request, db: Session = Depends(get_db)):
    return CampaignService(db, resolve_public_tenant_context(request, db)).list_campaign_products(campaign_id)


@router.post("/{campaign_id}/products", response_model=CampaignProductOut, status_code=201)
def add_campaign_product(
    campaign_id: str,
    body: CampaignProductCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    return CampaignService(db, resolve_panel_tenant_context(request, db, admin)).add_campaign_product(campaign_id, body)


@router.put("/products/{cp_id}", response_model=CampaignProductOut)
def update_campaign_product(
    cp_id: str,
    body: CampaignProductUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    return CampaignService(db, resolve_panel_tenant_context(request, db, admin)).update_campaign_product(cp_id, body)


@router.delete("/products/{cp_id}", status_code=204)
def remove_campaign_product(
    cp_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    CampaignService(db, resolve_panel_tenant_context(request, db, admin)).remove_campaign_product(cp_id)


# ── Promotional Kits ──────────────────────────────────────────────────────────

@router.get("/kits/all", response_model=list[PromotionalKitOut])
def list_kits(
    request: Request,
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    context = (
        resolve_public_tenant_context(request, db)
        if active_only
        else resolve_panel_tenant_context(request, db, _require_admin(request, db))
    )
    return CampaignService(db, context).list_kits(active_only=active_only)


@router.post("/kits", response_model=PromotionalKitOut, status_code=201)
def create_kit(
    body: PromotionalKitCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    return CampaignService(db, resolve_panel_tenant_context(request, db, admin)).create_kit(body)


@router.put("/kits/{kit_id}", response_model=PromotionalKitOut)
def update_kit(
    kit_id: str,
    body: PromotionalKitUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    return CampaignService(db, resolve_panel_tenant_context(request, db, admin)).update_kit(kit_id, body)


@router.delete("/kits/{kit_id}", status_code=204)
def delete_kit(
    kit_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    CampaignService(db, resolve_panel_tenant_context(request, db, admin)).delete_kit(kit_id)


@router.post("/kits/{kit_id}/items", response_model=KitItemOut, status_code=201)
def add_kit_item(
    kit_id: str,
    body: KitItemCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    return CampaignService(db, resolve_panel_tenant_context(request, db, admin)).add_kit_item(kit_id, body)


@router.delete("/kits/items/{item_id}", status_code=204)
def remove_kit_item(
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
):
    CampaignService(db, resolve_panel_tenant_context(request, db, admin)).remove_kit_item(item_id)

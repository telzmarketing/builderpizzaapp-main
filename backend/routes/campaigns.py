import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.campaign_service import CampaignService
from backend.schemas.campaign import (
    CampaignCreate, CampaignUpdate, CampaignOut,
    CampaignProductCreate, CampaignProductUpdate, CampaignProductOut,
    PromotionalKitCreate, PromotionalKitUpdate, PromotionalKitOut,
    KitItemCreate, KitItemOut,
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


# ── Campaigns ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[CampaignOut])
def list_campaigns(
    published_only: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    return CampaignService(db).list_campaigns(published_only=published_only)


@router.get("/slug/{slug}", response_model=CampaignOut)
def get_campaign_by_slug(slug: str, db: Session = Depends(get_db)):
    campaign = CampaignService(db).get_public_by_slug(slug)
    if not campaign:
        raise HTTPException(404, "Campanha não encontrada.")
    return campaign


@router.get("/{campaign_id}", response_model=CampaignOut)
def get_campaign(campaign_id: str, db: Session = Depends(get_db)):
    campaign = CampaignService(db).get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(404, "Campanha não encontrada.")
    return campaign


@router.post("", response_model=CampaignOut, status_code=201)
def create_campaign(body: CampaignCreate, db: Session = Depends(get_db)):
    return CampaignService(db).create_campaign(body)


@router.put("/{campaign_id}", response_model=CampaignOut)
def update_campaign(campaign_id: str, body: CampaignUpdate, db: Session = Depends(get_db)):
    return CampaignService(db).update_campaign(campaign_id, body)


@router.delete("/{campaign_id}", status_code=204)
def delete_campaign(campaign_id: str, db: Session = Depends(get_db)):
    CampaignService(db).delete_campaign(campaign_id)


# ── Campaign Products ─────────────────────────────────────────────────────────

@router.get("/{campaign_id}/products", response_model=list[CampaignProductOut])
def list_campaign_products(campaign_id: str, db: Session = Depends(get_db)):
    return CampaignService(db).list_campaign_products(campaign_id)


@router.post("/{campaign_id}/products", response_model=CampaignProductOut, status_code=201)
def add_campaign_product(campaign_id: str, body: CampaignProductCreate, db: Session = Depends(get_db)):
    return CampaignService(db).add_campaign_product(campaign_id, body)


@router.put("/products/{cp_id}", response_model=CampaignProductOut)
def update_campaign_product(cp_id: str, body: CampaignProductUpdate, db: Session = Depends(get_db)):
    return CampaignService(db).update_campaign_product(cp_id, body)


@router.delete("/products/{cp_id}", status_code=204)
def remove_campaign_product(cp_id: str, db: Session = Depends(get_db)):
    CampaignService(db).remove_campaign_product(cp_id)


# ── Promotional Kits ──────────────────────────────────────────────────────────

@router.get("/kits/all", response_model=list[PromotionalKitOut])
def list_kits(active_only: bool = Query(default=False), db: Session = Depends(get_db)):
    return CampaignService(db).list_kits(active_only=active_only)


@router.post("/kits", response_model=PromotionalKitOut, status_code=201)
def create_kit(body: PromotionalKitCreate, db: Session = Depends(get_db)):
    return CampaignService(db).create_kit(body)


@router.put("/kits/{kit_id}", response_model=PromotionalKitOut)
def update_kit(kit_id: str, body: PromotionalKitUpdate, db: Session = Depends(get_db)):
    return CampaignService(db).update_kit(kit_id, body)


@router.delete("/kits/{kit_id}", status_code=204)
def delete_kit(kit_id: str, db: Session = Depends(get_db)):
    CampaignService(db).delete_kit(kit_id)


@router.post("/kits/{kit_id}/items", response_model=KitItemOut, status_code=201)
def add_kit_item(kit_id: str, body: KitItemCreate, db: Session = Depends(get_db)):
    return CampaignService(db).add_kit_item(kit_id, body)


@router.delete("/kits/items/{item_id}", status_code=204)
def remove_kit_item(item_id: str, db: Session = Depends(get_db)):
    CampaignService(db).remove_kit_item(item_id)

import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload

from backend.models.campaign import Campaign, CampaignProduct, PromotionalKit, PromotionalKitItem, CampaignStatus
from backend.schemas.campaign import (
    CampaignCreate, CampaignUpdate,
    CampaignProductCreate, CampaignProductUpdate,
    PromotionalKitCreate, PromotionalKitUpdate,
    KitItemCreate,
)


class CampaignService:
    def __init__(self, db: Session):
        self._db = db

    # ── Campaigns ─────────────────────────────────────────────────────────────

    def list_campaigns(self, published_only: bool = False):
        q = self._db.query(Campaign)
        if published_only:
            now = datetime.now(timezone.utc)
            q = q.filter(
                Campaign.published == True,  # noqa: E712
                Campaign.status == "active",
            ).filter(
                (Campaign.start_at == None) | (Campaign.start_at <= now)  # noqa: E711
            ).filter(
                (Campaign.end_at == None) | (Campaign.end_at >= now)  # noqa: E711
            )
        return q.order_by(Campaign.display_order.asc(), Campaign.created_at.desc()).all()

    def get_campaign(self, campaign_id: str) -> Campaign | None:
        return self._db.query(Campaign).filter(Campaign.id == campaign_id).first()

    def get_by_slug(self, slug: str) -> Campaign | None:
        return self._db.query(Campaign).filter(Campaign.slug == slug).first()

    def get_public_by_slug(self, slug: str) -> Campaign | None:
        now = datetime.now(timezone.utc)
        return (
            self._db.query(Campaign)
            .filter(
                Campaign.slug == slug,
                Campaign.published == True,  # noqa: E712
                Campaign.status == CampaignStatus.active,
            )
            .filter((Campaign.start_at == None) | (Campaign.start_at <= now))  # noqa: E711
            .filter((Campaign.end_at == None) | (Campaign.end_at >= now))  # noqa: E711
            .first()
        )

    def create_campaign(self, payload: CampaignCreate) -> Campaign:
        existing = self._db.query(Campaign).filter(Campaign.slug == payload.slug).first()
        if existing:
            from fastapi import HTTPException
            raise HTTPException(400, f"Slug '{payload.slug}' já está em uso.")
        campaign = Campaign(id=str(uuid.uuid4()), **payload.model_dump())
        self._db.add(campaign)
        self._db.commit()
        self._db.refresh(campaign)
        return campaign

    def update_campaign(self, campaign_id: str, payload: CampaignUpdate) -> Campaign:
        campaign = self._db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            from fastapi import HTTPException
            raise HTTPException(404, "Campanha não encontrada.")
        data = payload.model_dump(exclude_none=True)
        if "slug" in data:
            dup = self._db.query(Campaign).filter(
                Campaign.slug == data["slug"], Campaign.id != campaign_id
            ).first()
            if dup:
                from fastapi import HTTPException
                raise HTTPException(400, f"Slug '{data['slug']}' já está em uso.")
        data["updated_at"] = datetime.now(timezone.utc)
        for k, v in data.items():
            setattr(campaign, k, v)
        self._db.commit()
        self._db.refresh(campaign)
        return campaign

    def delete_campaign(self, campaign_id: str) -> None:
        campaign = self._db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            from fastapi import HTTPException
            raise HTTPException(404, "Campanha não encontrada.")
        self._db.delete(campaign)
        self._db.commit()

    # ── Campaign Products ─────────────────────────────────────────────────────

    def list_campaign_products(self, campaign_id: str):
        return (
            self._db.query(CampaignProduct)
            .options(joinedload(CampaignProduct.product), joinedload(CampaignProduct.kit))
            .filter(CampaignProduct.campaign_id == campaign_id)
            .all()
        )

    def add_campaign_product(self, campaign_id: str, payload: CampaignProductCreate) -> CampaignProduct:
        campaign = self._db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            from fastapi import HTTPException
            raise HTTPException(404, "Campanha não encontrada.")
        existing = (
            self._db.query(CampaignProduct)
            .filter(
                CampaignProduct.campaign_id == campaign_id,
                CampaignProduct.product_id == payload.product_id,
                CampaignProduct.kit_id == payload.kit_id,
            )
            .first()
        )
        if existing:
            for k, v in payload.model_dump().items():
                setattr(existing, k, v)
            self._db.commit()
            self._db.refresh(existing)
            return existing
        cp = CampaignProduct(id=str(uuid.uuid4()), campaign_id=campaign_id, **payload.model_dump())
        self._db.add(cp)
        self._db.commit()
        self._db.refresh(cp)
        return cp

    def update_campaign_product(self, cp_id: str, payload: CampaignProductUpdate) -> CampaignProduct:
        cp = self._db.query(CampaignProduct).filter(CampaignProduct.id == cp_id).first()
        if not cp:
            from fastapi import HTTPException
            raise HTTPException(404, "Item de campanha não encontrado.")
        for k, v in payload.model_dump(exclude_none=True).items():
            setattr(cp, k, v)
        self._db.commit()
        self._db.refresh(cp)
        return cp

    def remove_campaign_product(self, cp_id: str) -> None:
        cp = self._db.query(CampaignProduct).filter(CampaignProduct.id == cp_id).first()
        if not cp:
            from fastapi import HTTPException
            raise HTTPException(404, "Item de campanha não encontrado.")
        self._db.delete(cp)
        self._db.commit()

    # ── Promotional Kits ──────────────────────────────────────────────────────

    def list_kits(self, active_only: bool = False):
        q = self._db.query(PromotionalKit).options(joinedload(PromotionalKit.items))
        if active_only:
            q = q.filter(PromotionalKit.active == True)  # noqa: E712
        return q.order_by(PromotionalKit.created_at.desc()).all()

    def get_kit(self, kit_id: str) -> PromotionalKit | None:
        return (
            self._db.query(PromotionalKit)
            .options(joinedload(PromotionalKit.items))
            .filter(PromotionalKit.id == kit_id)
            .first()
        )

    def create_kit(self, payload: PromotionalKitCreate) -> PromotionalKit:
        kit = PromotionalKit(id=str(uuid.uuid4()), **payload.model_dump())
        self._db.add(kit)
        self._db.commit()
        self._db.refresh(kit)
        return self.get_kit(kit.id)

    def update_kit(self, kit_id: str, payload: PromotionalKitUpdate) -> PromotionalKit:
        kit = self._db.query(PromotionalKit).filter(PromotionalKit.id == kit_id).first()
        if not kit:
            from fastapi import HTTPException
            raise HTTPException(404, "Kit não encontrado.")
        data = payload.model_dump(exclude_none=True)
        data["updated_at"] = datetime.now(timezone.utc)
        for k, v in data.items():
            setattr(kit, k, v)
        self._db.commit()
        return self.get_kit(kit_id)

    def delete_kit(self, kit_id: str) -> None:
        kit = self._db.query(PromotionalKit).filter(PromotionalKit.id == kit_id).first()
        if not kit:
            from fastapi import HTTPException
            raise HTTPException(404, "Kit não encontrado.")
        self._db.delete(kit)
        self._db.commit()

    def add_kit_item(self, kit_id: str, payload: KitItemCreate) -> PromotionalKitItem:
        kit = self._db.query(PromotionalKit).filter(PromotionalKit.id == kit_id).first()
        if not kit:
            from fastapi import HTTPException
            raise HTTPException(404, "Kit não encontrado.")
        item = PromotionalKitItem(id=str(uuid.uuid4()), kit_id=kit_id, **payload.model_dump())
        self._db.add(item)
        self._db.commit()
        self._db.refresh(item)
        return item

    def remove_kit_item(self, item_id: str) -> None:
        item = self._db.query(PromotionalKitItem).filter(PromotionalKitItem.id == item_id).first()
        if not item:
            from fastapi import HTTPException
            raise HTTPException(404, "Item do kit não encontrado.")
        self._db.delete(item)
        self._db.commit()

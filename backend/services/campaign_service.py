import uuid
import re
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session, joinedload

from backend.core.tenant_context import TenantContext
from backend.core.tenant_context import TenantContextMissing
from backend.core.tenant_ownership import assign_tenant_on_create, scope_query_to_tenant
from backend.models.campaign import Campaign, CampaignProduct, PromotionalKit, PromotionalKitItem, CampaignStatus
from backend.models.product import Product, ProductCategory
from backend.schemas.campaign import (
    CampaignCreate, CampaignUpdate,
    CampaignProductCreate, CampaignProductUpdate,
    PromotionalKitCreate, PromotionalKitUpdate,
    KitItemCreate,
)


class CampaignService:
    def __init__(self, db: Session, tenant_context: TenantContext | None = None):
        self._db = db
        self._tenant_context = tenant_context
        # Campaign tables are covered by the tenant catalog contract and have
        # a NOT NULL tenant_id in production. A service instance used by an
        # administrative route must therefore always carry trusted context;
        # the route layer rejects legacy/global tokens before reaching here.
        self._tenant_enabled = tenant_context is not None

    def _query(self, model):
        return scope_query_to_tenant(
            self._db.query(model), model, self._tenant_context, enabled=self._tenant_enabled
        )

    def _own(self, resource):
        if self._tenant_context is None:
            raise TenantContextMissing(
                "Contexto de tenant obrigatorio para campanhas."
            )
        return assign_tenant_on_create(
            resource, self._tenant_context, enabled=True
        )

    def _require_product(self, product_id: str | None) -> None:
        if not product_id:
            return
        if not self._query(Product).filter(Product.id == product_id).first():
            from fastapi import HTTPException
            raise HTTPException(404, "Produto nao encontrado.")

    def _kit_prices(self, items: list[KitItemCreate], discount_type, discount_value) -> tuple[float, float]:
        from fastapi import HTTPException
        total = Decimal("0.00")
        seen: set[str] = set()
        for item in items:
            if item.product_id in seen:
                raise HTTPException(422, "O mesmo produto nao pode ser repetido no kit; ajuste a quantidade.")
            seen.add(item.product_id)
            product = self._query(Product).filter(Product.id == item.product_id, Product.active == True).first()  # noqa: E712
            if not product:
                raise HTTPException(404, "Produto do kit nao encontrado ou inativo.")
            total += Decimal(str(product.price or 0)) * item.quantity
        total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        discount = Decimal(str(discount_value or 0))
        if discount < 0 or (discount_type == "percentage" and discount > 100):
            raise HTTPException(422, "Desconto do kit invalido.")
        if discount_type == "percentage":
            promotional = total * (Decimal("1") - discount / Decimal("100"))
        elif discount_type == "fixed":
            promotional = total - discount
        else:
            promotional = total
        return float(total), float(max(Decimal("0.00"), promotional).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    def _require_highlight(self, highlight_type: str | None, highlight_id: str | None) -> None:
        if not highlight_id:
            return
        if highlight_type == "product":
            self._require_product(highlight_id)
        elif highlight_type == "category":
            if not self._query(ProductCategory).filter(ProductCategory.id == highlight_id, ProductCategory.active == True).first():  # noqa: E712
                from fastapi import HTTPException
                raise HTTPException(404, "Categoria nao encontrada ou inativa.")
        elif highlight_type == "kit":
            if not self._query(PromotionalKit).filter(PromotionalKit.id == highlight_id, PromotionalKit.active == True).first():
                from fastapi import HTTPException
                raise HTTPException(404, "Kit nao encontrado ou inativo.")
        else:
            from fastapi import HTTPException
            raise HTTPException(422, "Tipo de destaque invalido.")

    # ── Campaigns ─────────────────────────────────────────────────────────────

    def list_campaigns(self, published_only: bool = False):
        q = self._query(Campaign)
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
        return self._query(Campaign).filter(Campaign.id == campaign_id).first()

    def get_by_slug(self, slug: str) -> Campaign | None:
        return self._query(Campaign).filter(Campaign.slug == slug).first()

    def get_public_by_slug(self, slug: str) -> Campaign | None:
        now = datetime.now(timezone.utc)
        return (
            self._query(Campaign)
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
        existing = self._query(Campaign).filter(Campaign.slug == payload.slug).first()
        if existing:
            from fastapi import HTTPException
            raise HTTPException(400, f"Slug '{payload.slug}' já está em uso.")
        self._require_product(payload.product_id)
        self._require_highlight(payload.highlight_type, payload.highlight_id)
        campaign = self._own(Campaign(id=str(uuid.uuid4()), **payload.model_dump()))
        self._db.add(campaign)
        self._db.commit()
        self._db.refresh(campaign)
        return campaign

    def update_campaign(self, campaign_id: str, payload: CampaignUpdate) -> Campaign:
        campaign = self._query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            from fastapi import HTTPException
            raise HTTPException(404, "Campanha não encontrada.")
        data = payload.model_dump(exclude_none=True)
        if "product_id" in data:
            self._require_product(data["product_id"])
        if "highlight_type" in data or "highlight_id" in data:
            self._require_highlight(data.get("highlight_type", campaign.highlight_type), data.get("highlight_id", campaign.highlight_id))
        if "slug" in data:
            dup = self._query(Campaign).filter(
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
        campaign = self._query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            from fastapi import HTTPException
            raise HTTPException(404, "Campanha não encontrada.")
        self._db.delete(campaign)
        self._db.commit()

    # ── Campaign Products ─────────────────────────────────────────────────────

    def list_campaign_products(self, campaign_id: str):
        return (
            self._query(CampaignProduct)
            .options(joinedload(CampaignProduct.product), joinedload(CampaignProduct.kit))
            .filter(CampaignProduct.campaign_id == campaign_id)
            .all()
        )

    def add_campaign_product(self, campaign_id: str, payload: CampaignProductCreate) -> CampaignProduct:
        campaign = self._query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            from fastapi import HTTPException
            raise HTTPException(404, "Campanha não encontrada.")
        existing = (
            self._query(CampaignProduct)
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
        self._require_product(payload.product_id)
        if payload.kit_id and not self._query(PromotionalKit).filter(PromotionalKit.id == payload.kit_id).first():
            from fastapi import HTTPException
            raise HTTPException(404, "Kit nao encontrado.")
        cp = self._own(CampaignProduct(id=str(uuid.uuid4()), campaign_id=campaign_id, **payload.model_dump()))
        self._db.add(cp)
        self._db.commit()
        self._db.refresh(cp)
        return cp

    def update_campaign_product(self, cp_id: str, payload: CampaignProductUpdate) -> CampaignProduct:
        cp = self._query(CampaignProduct).filter(CampaignProduct.id == cp_id).first()
        if not cp:
            from fastapi import HTTPException
            raise HTTPException(404, "Item de campanha não encontrado.")
        data = payload.model_dump(exclude_none=True)
        if "product_id" in data:
            self._require_product(data["product_id"])
        if data.get("kit_id") and not self._query(PromotionalKit).filter(PromotionalKit.id == data["kit_id"]).first():
            from fastapi import HTTPException
            raise HTTPException(404, "Kit nao encontrado.")
        for k, v in data.items():
            setattr(cp, k, v)
        self._db.commit()
        self._db.refresh(cp)
        return cp

    def remove_campaign_product(self, cp_id: str) -> None:
        cp = self._query(CampaignProduct).filter(CampaignProduct.id == cp_id).first()
        if not cp:
            from fastapi import HTTPException
            raise HTTPException(404, "Item de campanha não encontrado.")
        self._db.delete(cp)
        self._db.commit()

    # ── Promotional Kits ──────────────────────────────────────────────────────

    def list_kits(self, active_only: bool = False):
        q = self._query(PromotionalKit).options(joinedload(PromotionalKit.items))
        if active_only:
            q = q.filter(PromotionalKit.active == True)  # noqa: E712
        return q.order_by(PromotionalKit.created_at.desc()).all()

    def get_kit(self, kit_id: str) -> PromotionalKit | None:
        return (
            self._query(PromotionalKit)
            .options(joinedload(PromotionalKit.items))
            .filter(PromotionalKit.id == kit_id)
            .first()
        )

    def create_kit(self, payload: PromotionalKitCreate) -> PromotionalKit:
        items = payload.items
        original, promotional = self._kit_prices(items, payload.discount_type, payload.discount_value)
        kit_data = payload.model_dump(exclude={"items"})
        kit_data["slug"] = self._unique_kit_slug(kit_data.get("slug") or payload.name)
        kit_data.update(price_original=original, price_promotional=promotional)
        kit = self._own(PromotionalKit(id=str(uuid.uuid4()), **kit_data))
        self._db.add(kit)
        self._db.flush()
        for item in items:
            self._db.add(self._own(PromotionalKitItem(id=str(uuid.uuid4()), kit_id=kit.id, product_id=item.product_id, quantity=item.quantity)))
        self._db.commit()
        self._db.refresh(kit)
        return self.get_kit(kit.id)

    def update_kit(self, kit_id: str, payload: PromotionalKitUpdate) -> PromotionalKit:
        kit = self._query(PromotionalKit).filter(PromotionalKit.id == kit_id).first()
        if not kit:
            from fastapi import HTTPException
            raise HTTPException(404, "Kit não encontrado.")
        data = payload.model_dump(exclude_none=True)
        if "slug" in data:
            data["slug"] = self._unique_kit_slug(data["slug"], current_id=kit_id)
        if any(key in data for key in ("discount_type", "discount_value", "price_original", "price_promotional")):
            items = [KitItemCreate(product_id=item.product_id, quantity=item.quantity) for item in kit.items]
            original, promotional = self._kit_prices(items, data.get("discount_type", kit.discount_type), data.get("discount_value", kit.discount_value))
            data["price_original"] = original
            data["price_promotional"] = promotional
        data["updated_at"] = datetime.now(timezone.utc)
        for k, v in data.items():
            setattr(kit, k, v)
        self._db.commit()
        return self.get_kit(kit_id)

    def get_public_kit_by_slug(self, slug: str) -> PromotionalKit | None:
        kit = self._query(PromotionalKit).options(joinedload(PromotionalKit.items)).filter(
            PromotionalKit.slug == slug, PromotionalKit.active == True  # noqa: E712
        ).first()
        if kit and kit.valid_until and kit.valid_until < datetime.now(timezone.utc):
            return None
        return kit

    def get_public_kit_by_id(self, kit_id: str) -> PromotionalKit | None:
        kit = self.get_kit(kit_id)
        if not kit or not kit.active:
            return None
        if kit.valid_until and kit.valid_until < datetime.now(timezone.utc):
            return None
        return kit

    def _unique_kit_slug(self, raw: str, current_id: str | None = None) -> str:
        normalized = unicodedata.normalize("NFKD", raw or "").encode("ascii", "ignore").decode("ascii")
        base = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-") or f"combo-{uuid.uuid4().hex[:8]}"
        slug = base[:150]
        suffix = 1
        while True:
            query = self._query(PromotionalKit).filter(PromotionalKit.slug == slug)
            if current_id:
                query = query.filter(PromotionalKit.id != current_id)
            if not query.first():
                return slug
            suffix += 1
            tail = f"-{suffix}"
            slug = f"{base[:150 - len(tail)]}{tail}"

    def delete_kit(self, kit_id: str) -> None:
        kit = self._query(PromotionalKit).filter(PromotionalKit.id == kit_id).first()
        if not kit:
            from fastapi import HTTPException
            raise HTTPException(404, "Kit não encontrado.")
        self._db.delete(kit)
        self._db.commit()

    def add_kit_item(self, kit_id: str, payload: KitItemCreate) -> PromotionalKitItem:
        kit = self._query(PromotionalKit).filter(PromotionalKit.id == kit_id).first()
        if not kit:
            from fastapi import HTTPException
            raise HTTPException(404, "Kit não encontrado.")
        self._require_product(payload.product_id)
        if self._query(PromotionalKitItem).filter(PromotionalKitItem.kit_id == kit_id, PromotionalKitItem.product_id == payload.product_id).first():
            from fastapi import HTTPException
            raise HTTPException(422, "O produto ja existe no kit; ajuste a quantidade.")
        item = self._own(PromotionalKitItem(id=str(uuid.uuid4()), kit_id=kit_id, **payload.model_dump()))
        self._db.add(item)
        self._db.flush()
        items = [KitItemCreate(product_id=current.product_id, quantity=current.quantity) for current in kit.items] + [payload]
        kit.price_original, kit.price_promotional = self._kit_prices(items, kit.discount_type, kit.discount_value)
        kit.updated_at = datetime.now(timezone.utc)
        self._db.commit()
        self._db.refresh(item)
        return item

    def remove_kit_item(self, item_id: str) -> None:
        item = self._query(PromotionalKitItem).filter(PromotionalKitItem.id == item_id).first()
        if not item:
            from fastapi import HTTPException
            raise HTTPException(404, "Item do kit não encontrado.")
        self._db.delete(item)
        self._db.commit()

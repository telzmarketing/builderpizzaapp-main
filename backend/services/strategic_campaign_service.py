from __future__ import annotations

import re
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session, selectinload

from backend.core.exceptions import DomainError
from backend.models.product import Product, ProductCategory
from backend.models.product_promotion import ProductPromotion
from backend.models.campaign import PromotionalKit
from backend.models.strategic_campaign import StrategicCampaign, StrategicCampaignStatus, StrategicCampaignVersion, StrategicOffer, StrategicOfferComponent
from backend.schemas.strategic_campaign import (
    STRATEGIC_CAMPAIGN_SNAPSHOT_SCHEMA_VERSION,
    StrategicCampaignCreate,
    StrategicCampaignDuplicate,
    StrategicCampaignPublicOut,
    StrategicCampaignSnapshot,
    StrategicCampaignSnapshotCampaign,
    StrategicCampaignSnapshotOffer,
    StrategicCampaignUpdate,
    StrategicCommercialConfig,
    StrategicOfferCreate,
    StrategicOfferDuplicate,
    StrategicOfferReorder,
    StrategicOfferUpdate,
)


class StrategicCampaignService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def _campaign(self, campaign_id: str) -> StrategicCampaign:
        row = self.db.query(StrategicCampaign).options(selectinload(StrategicCampaign.offers).selectinload(StrategicOffer.components)).filter(
            StrategicCampaign.tenant_id == self.tenant_id, StrategicCampaign.id == campaign_id,
        ).first()
        if not row:
            raise DomainError("Campanha estratégica não encontrada.", code="StrategicCampaignNotFound")
        return row

    def list(self) -> list[StrategicCampaign]:
        return self.db.query(StrategicCampaign).options(selectinload(StrategicCampaign.offers).selectinload(StrategicOffer.components)).filter(
            StrategicCampaign.tenant_id == self.tenant_id,
        ).order_by(StrategicCampaign.updated_at.desc()).all()

    def get_public(self, slug: str) -> StrategicCampaignPublicOut:
        published_rows = self.db.query(StrategicCampaignVersion).join(
            StrategicCampaign,
            (StrategicCampaign.id == StrategicCampaignVersion.campaign_id)
            & (StrategicCampaign.tenant_id == StrategicCampaignVersion.tenant_id)
            & (StrategicCampaign.published_version == StrategicCampaignVersion.version),
        ).filter(
            StrategicCampaign.tenant_id == self.tenant_id,
            StrategicCampaign.status == StrategicCampaignStatus.active,
        ).all()
        for published in published_rows:
            document = self._snapshot_document(published)
            if document.campaign.slug == slug:
                self._assert_public_period(document.campaign.starts_at, document.campaign.ends_at)
                return document.as_public_campaign()
        raise DomainError("Campanha estratégica não encontrada.", code="StrategicCampaignNotFound")

    def resolve_checkout_offer(self, offer_id: str) -> tuple[StrategicCampaign, StrategicOffer]:
        offer = self._offer(offer_id)
        campaign = self.get_public_by_id(offer.campaign_id)
        if offer.archived_at is not None or not offer.active:
            raise DomainError("Oferta estratégica indisponível.", code="StrategicOfferUnavailable")
        now = datetime.now(timezone.utc)
        if offer.sales_starts_at and offer.sales_starts_at > now or offer.sales_ends_at and offer.sales_ends_at <= now:
            raise DomainError("Oferta estratégica fora do período de venda.", code="StrategicOfferUnavailable")
        return campaign, offer

    def get_public_by_id(self, campaign_id: str) -> StrategicCampaign:
        row = self._campaign(campaign_id)
        if row.status != StrategicCampaignStatus.active or row.published_version is None:
            raise DomainError("Campanha estratégica não publicada.", code="StrategicCampaignUnavailable")
        now = datetime.now(timezone.utc)
        if row.starts_at and row.starts_at > now or row.ends_at and row.ends_at <= now:
            raise DomainError("Campanha estratégica fora do período de venda.", code="StrategicCampaignUnavailable")
        return row

    def create(self, payload: StrategicCampaignCreate) -> StrategicCampaign:
        self._assert_period(payload.starts_at, payload.ends_at)
        self._assert_slug(payload.slug)
        self._assert_commercial_config(payload.commercial_config)
        row = StrategicCampaign(id=f"sc-{uuid.uuid4().hex[:12]}", tenant_id=self.tenant_id, **payload.model_dump())
        self.db.add(row)
        self.db.commit()
        return self._campaign(row.id)

    def update(self, campaign_id: str, payload: StrategicCampaignUpdate) -> StrategicCampaign:
        row = self._campaign(campaign_id)
        data = payload.model_dump(exclude_unset=True)
        if "slug" in data and data["slug"] != row.slug:
            self._assert_slug(data["slug"], current_id=row.id)
        self._assert_period(data.get("starts_at", row.starts_at), data.get("ends_at", row.ends_at))
        if "commercial_config" in data:
            self._assert_commercial_config(data["commercial_config"])
        if "status" in data:
            self._assert_transition(row.status, data["status"])
        for key, value in data.items():
            setattr(row, key, value)
        self.db.commit()
        return self._campaign(row.id)

    def duplicate_campaign(self, campaign_id: str, payload: StrategicCampaignDuplicate) -> StrategicCampaign:
        source = self._campaign(campaign_id)
        slug = payload.slug or self._next_campaign_slug(source.slug)
        self._assert_slug(slug)
        duplicate = StrategicCampaign(
            id=f"sc-{uuid.uuid4().hex[:12]}",
            tenant_id=self.tenant_id,
            name=payload.name or self._copy_label(source.name, 200),
            commercial_name=source.commercial_name,
            slug=slug,
            description=source.description,
            status=StrategicCampaignStatus.draft,
            starts_at=source.starts_at,
            ends_at=source.ends_at,
            visual_config=deepcopy(source.visual_config or {}),
            commercial_config=deepcopy(source.commercial_config or {}),
            marketing_config=deepcopy(source.marketing_config or {}),
            published_version=None,
        )
        self.db.add(duplicate)
        for offer in sorted(source.offers, key=lambda item: (item.display_order, item.id)):
            if offer.archived_at is None:
                self.db.add(self._copy_offer(offer, duplicate.id, code=offer.code, title=offer.title))
        self.db.commit()
        return self._campaign(duplicate.id)

    def add_offer(self, campaign_id: str, payload: StrategicOfferCreate) -> StrategicOffer:
        campaign = self._campaign(campaign_id)
        if self.db.query(StrategicOffer).filter(StrategicOffer.tenant_id == self.tenant_id, StrategicOffer.campaign_id == campaign_id, StrategicOffer.code == payload.code).first():
            raise DomainError("Código de oferta já utilizado nesta campanha.", code="StrategicOfferCodeConflict")
        if payload.product_id and not self.db.query(Product).filter(Product.tenant_id == self.tenant_id, Product.id == payload.product_id, Product.active.is_(True)).first():
            raise DomainError("Produto da oferta não encontrado.", code="StrategicOfferProductNotFound")
        if payload.kit_id and not self.db.query(PromotionalKit).filter(PromotionalKit.tenant_id == self.tenant_id, PromotionalKit.id == payload.kit_id, PromotionalKit.active.is_(True)).first():
            raise DomainError("Kit da oferta não encontrado.", code="StrategicOfferKitNotFound")
        self._assert_reference_shape(payload.reference_type, payload.product_id, payload.kit_id, payload.components)
        self._assert_offer_promotion(payload.product_id, payload.config)
        self._assert_offer_components(payload.reference_type, payload.components)
        self._assert_offer_period(payload.sales_starts_at, payload.sales_ends_at, campaign)
        data = payload.model_dump(exclude={"components", "selection_quantity"})
        if payload.selection_quantity is not None:
            data["config"] = {
                **(data.get("config") or {}),
                "selection_quantity": payload.selection_quantity,
            }
        row = StrategicOffer(id=f"so-{uuid.uuid4().hex[:12]}", tenant_id=self.tenant_id, campaign_id=campaign_id, **data)
        row.components = self._component_rows(row.id, payload.components)
        self.db.add(row)
        self.db.commit()
        return row

    def update_offer(self, offer_id: str, payload: StrategicOfferUpdate) -> StrategicOffer:
        row = self._offer(offer_id)
        self._assert_offer_not_archived(row)
        campaign = self._campaign(row.campaign_id)
        data = payload.model_dump(exclude_unset=True)
        if "selection_quantity" in data:
            selection_quantity = data.pop("selection_quantity")
            if selection_quantity is not None:
                data["config"] = {
                    **(row.config or {}),
                    **(data.get("config") or {}),
                    "selection_quantity": selection_quantity,
                }
        components = data.pop("components", None)
        reference_type = data.get("reference_type", row.reference_type)
        product_id = data.get("product_id", row.product_id)
        kit_id = data.get("kit_id", row.kit_id)
        effective_components = components if components is not None else row.components
        self._assert_reference_shape(reference_type, product_id, kit_id, effective_components)
        if "product_id" in data and product_id and not self.db.query(Product).filter(Product.tenant_id == self.tenant_id, Product.id == product_id, Product.active.is_(True)).first():
            raise DomainError("Produto da oferta nao encontrado.", code="StrategicOfferProductNotFound")
        if "kit_id" in data and kit_id and not self.db.query(PromotionalKit).filter(PromotionalKit.tenant_id == self.tenant_id, PromotionalKit.id == kit_id, PromotionalKit.active.is_(True)).first():
            raise DomainError("Kit da oferta nao encontrado.", code="StrategicOfferKitNotFound")
        original = data.get("price_original", row.price_original)
        promotional = data.get("price_promotional", row.price_promotional)
        if promotional > original:
            raise DomainError("O preço promocional não pode superar o preço original.", code="InvalidStrategicOfferPrice")
        self._assert_pricing_strategy(
            data.get("pricing_strategy", row.pricing_strategy),
            data.get("discount_percent", row.discount_percent),
            data.get("discount_amount", row.discount_amount),
            data.get("fixed_promotional_price", row.fixed_promotional_price),
        )
        if "config" in data and data["config"] is not None:
            self._assert_offer_promotion(product_id, data["config"])
        if components is not None:
            self._assert_offer_components(reference_type, components)
            row.components = self._component_rows(row.id, components)
            row.composition_revision += 1
        if any(key in data for key in {"reference_type", "product_id", "kit_id", "pricing_strategy", "discount_percent", "discount_amount", "fixed_promotional_price"}) and components is None:
            row.composition_revision += 1
        self._assert_offer_period(data.get("sales_starts_at", row.sales_starts_at), data.get("sales_ends_at", row.sales_ends_at), campaign)
        for key, value in data.items():
            setattr(row, key, value)
        self.db.commit()
        return row

    @staticmethod
    def _assert_pricing_strategy(
        strategy: str,
        discount_percent: Decimal | None,
        discount_amount: Decimal | None,
        fixed_promotional_price: Decimal | None,
    ) -> None:
        values = {
            "percentage": discount_percent,
            "fixed_discount": discount_amount,
            "fixed_price": fixed_promotional_price,
        }
        if strategy != "catalog" and values.get(strategy) is None:
            raise DomainError(
                "A estrategia de preco exige seu valor correspondente.",
                code="InvalidStrategicOfferPricingStrategy",
            )
        if strategy == "catalog" and any(value is not None for value in values.values()):
            raise DomainError(
                "A estrategia catalog nao aceita desconto estrategico.",
                code="InvalidStrategicOfferPricingStrategy",
            )
        if any(value is not None for key, value in values.items() if key != strategy):
            raise DomainError(
                "Informe somente o valor da estrategia de preco selecionada.",
                code="InvalidStrategicOfferPricingStrategy",
            )

    def duplicate_offer(self, offer_id: str, payload: StrategicOfferDuplicate) -> StrategicOffer:
        source = self._offer(offer_id)
        self._assert_offer_not_archived(source)
        campaign = self._campaign(source.campaign_id)
        code = payload.code or self._next_offer_code(source.campaign_id, source.code)
        if self._offer_code_exists(source.campaign_id, code):
            raise DomainError("Código de oferta já utilizado nesta campanha.", code="StrategicOfferCodeConflict")
        current_offers = [offer for offer in campaign.offers if offer.archived_at is None]
        display_order = max((offer.display_order for offer in current_offers), default=-1) + 1
        duplicate = self._copy_offer(
            source,
            source.campaign_id,
            code=code,
            title=payload.title or self._copy_label(source.title, 200),
            display_order=display_order,
        )
        self.db.add(duplicate)
        self.db.commit()
        return duplicate

    def reorder_offers(self, campaign_id: str, payload: StrategicOfferReorder) -> list[StrategicOffer]:
        campaign = self._campaign(campaign_id)
        offers = self.db.query(StrategicOffer).filter(
            StrategicOffer.tenant_id == self.tenant_id,
            StrategicOffer.campaign_id == campaign_id,
            StrategicOffer.archived_at.is_(None),
        ).with_for_update().all()
        current_ids = {offer.id for offer in offers}
        if set(payload.offer_ids) != current_ids:
            raise DomainError(
                "A ordenação deve conter exatamente todas as ofertas não arquivadas da campanha.",
                code="InvalidStrategicOfferOrder",
            )
        by_id = {offer.id: offer for offer in offers}
        for position, ordered_offer_id in enumerate(payload.offer_ids):
            by_id[ordered_offer_id].display_order = position
        self.db.commit()
        return [by_id[ordered_offer_id] for ordered_offer_id in payload.offer_ids]

    def archive_offer(self, offer_id: str) -> StrategicOffer:
        row = self._offer(offer_id)
        self._assert_offer_not_archived(row)
        self._campaign(row.campaign_id)
        row.active = False
        row.archived_at = datetime.now(timezone.utc)
        self.db.commit()
        return row

    def publish(self, campaign_id: str) -> StrategicCampaignVersion:
        row = self._campaign(campaign_id)
        active_offers = [offer for offer in row.offers if offer.active and offer.archived_at is None]
        if not active_offers:
            raise DomainError("Campanha precisa de ao menos uma oferta para publicar.", code="StrategicCampaignOfferRequired")
        version = (row.published_version or 0) + 1
        self._assert_public_slug_available(row.slug, row.id)
        snapshot = StrategicCampaignSnapshot(
            schema_version=STRATEGIC_CAMPAIGN_SNAPSHOT_SCHEMA_VERSION,
            campaign=StrategicCampaignSnapshotCampaign(
                id=row.id,
                name=row.name,
                commercial_name=row.commercial_name,
                slug=row.slug,
                description=row.description,
                status=StrategicCampaignStatus.active,
                starts_at=row.starts_at,
                ends_at=row.ends_at,
                visual_config=deepcopy(row.visual_config or {}),
                commercial_config=deepcopy(row.commercial_config or {}),
                marketing_config=deepcopy(row.marketing_config or {}),
                published_version=version,
            ),
            offers=[
                StrategicCampaignSnapshotOffer.model_validate(offer, from_attributes=True)
                for offer in sorted(active_offers, key=lambda item: (item.display_order, item.id))
            ],
        ).model_dump(mode="json")
        published = StrategicCampaignVersion(id=f"scv-{uuid.uuid4().hex[:12]}", tenant_id=self.tenant_id, campaign_id=row.id, version=version, snapshot=snapshot)
        row.published_version = version
        row.status = StrategicCampaignStatus.active
        self.db.add(published)
        self.db.commit()
        return published

    def _offer(self, offer_id: str) -> StrategicOffer:
        row = self.db.query(StrategicOffer).filter(StrategicOffer.tenant_id == self.tenant_id, StrategicOffer.id == offer_id).first()
        if not row:
            raise DomainError("Oferta estratégica não encontrada.", code="StrategicOfferNotFound")
        return row

    @staticmethod
    def _assert_offer_not_archived(offer: StrategicOffer) -> None:
        if offer.archived_at is not None:
            raise DomainError("Oferta estratégica já está arquivada.", code="StrategicOfferArchived")

    def _assert_offer_promotion(self, product_id: str | None, config: dict) -> None:
        promotion_id = config.get("product_promotion_id")
        if not promotion_id:
            return
        promotion = self.db.query(ProductPromotion.id).filter(
            ProductPromotion.id == promotion_id,
            ProductPromotion.product_id == product_id,
            ProductPromotion.tenant_id == self.tenant_id,
            ProductPromotion.active.is_(True),
        ).first()
        if not promotion:
            raise DomainError(
                "A promoção da oferta não pertence ao produto e tenant informados.",
                code="StrategicOfferPromotionNotFound",
            )

    def _next_campaign_slug(self, source_slug: str) -> str:
        number = 1
        while True:
            suffix = "-copy" if number == 1 else f"-copy-{number}"
            candidate = f"{source_slug[:180 - len(suffix)].rstrip('-')}{suffix}"
            exists = self.db.query(StrategicCampaign.id).filter(
                StrategicCampaign.tenant_id == self.tenant_id,
                StrategicCampaign.slug == candidate,
            ).first()
            if not exists:
                return candidate
            number += 1

    def _next_offer_code(self, campaign_id: str, source_code: str) -> str:
        number = 1
        while True:
            suffix = "-copy" if number == 1 else f"-copy-{number}"
            candidate = f"{source_code[:80 - len(suffix)].rstrip('-')}{suffix}"
            if not self._offer_code_exists(campaign_id, candidate):
                return candidate
            number += 1

    def _offer_code_exists(self, campaign_id: str, code: str) -> bool:
        return self.db.query(StrategicOffer.id).filter(
            StrategicOffer.tenant_id == self.tenant_id,
            StrategicOffer.campaign_id == campaign_id,
            StrategicOffer.code == code,
        ).first() is not None

    def _copy_offer(
        self,
        source: StrategicOffer,
        campaign_id: str,
        *,
        code: str,
        title: str,
        display_order: int | None = None,
    ) -> StrategicOffer:
        return StrategicOffer(
            id=f"so-{uuid.uuid4().hex[:12]}",
            tenant_id=self.tenant_id,
            campaign_id=campaign_id,
            code=code,
            title=title,
            description=source.description,
            product_id=source.product_id,
            kit_id=source.kit_id,
            reference_type=source.reference_type,
            pricing_strategy=source.pricing_strategy,
            discount_percent=source.discount_percent,
            discount_amount=source.discount_amount,
            fixed_promotional_price=source.fixed_promotional_price,
            composition_revision=source.composition_revision,
            price_original=source.price_original,
            price_promotional=source.price_promotional,
            active=source.active,
            display_order=source.display_order if display_order is None else display_order,
            quantity_limit=source.quantity_limit,
            max_per_customer=source.max_per_customer,
            sales_starts_at=source.sales_starts_at,
            sales_ends_at=source.sales_ends_at,
            show_when_sold_out=source.show_when_sold_out,
            button_text=source.button_text,
            image_desktop_url=source.image_desktop_url,
            image_mobile_url=source.image_mobile_url,
            badge_text=source.badge_text,
            highlighted=source.highlighted,
            config=deepcopy(source.config or {}),
            archived_at=None,
            components=[
                StrategicOfferComponent(
                    id=f"soc-{uuid.uuid4().hex[:12]}", tenant_id=self.tenant_id,
                    position=component.position, subcategory_id=component.subcategory_id,
                    quantity=component.quantity, allow_repeated_products=component.allow_repeated_products,
                    restrictions=deepcopy(component.restrictions or {}),
                )
                for component in source.components
            ],
        )

    def _assert_offer_components(self, reference_type: str, components) -> None:
        if reference_type not in {"subcategory", "mixed_subcategories"}:
            if components:
                raise DomainError("Produto e kit nao aceitam componentes por subcategoria.", code="StrategicOfferComponentsInvalid")
            return
        ids = [component.subcategory_id if hasattr(component, "subcategory_id") else component["subcategory_id"] for component in components]
        rows = self.db.query(ProductCategory).filter(
            ProductCategory.tenant_id == self.tenant_id,
            ProductCategory.id.in_(ids),
            ProductCategory.parent_id.is_not(None),
            ProductCategory.active.is_(True),
        ).all()
        if len(rows) != len(ids):
            raise DomainError("A composicao contem subcategoria invalida ou de outro tenant.", code="StrategicOfferSubcategoryNotFound")
        product_subcategories = {row[0] for row in self.db.query(Product.subcategory_id).filter(
            Product.tenant_id == self.tenant_id,
            Product.subcategory_id.in_(ids),
            Product.active.is_(True),
        ).distinct().all()}
        if product_subcategories != set(ids):
            raise DomainError("Todas as subcategorias precisam ter produtos ativos.", code="StrategicOfferSubcategoryEmpty")

    @staticmethod
    def _assert_reference_shape(reference_type: str, product_id: str | None, kit_id: str | None, components) -> None:
        count = len(components or [])
        valid = (
            reference_type == "product" and bool(product_id) and not kit_id and count == 0
            or reference_type == "kit" and bool(kit_id) and not product_id and count == 0
            or reference_type == "subcategory" and not product_id and not kit_id and count == 1
            or reference_type == "mixed_subcategories" and not product_id and not kit_id and count >= 2
        )
        if not valid:
            raise DomainError("Referencia e composicao da oferta sao inconsistentes.", code="StrategicOfferReferenceInvalid")

    def _component_rows(self, offer_id: str, components) -> list[StrategicOfferComponent]:
        return [StrategicOfferComponent(
            id=f"soc-{uuid.uuid4().hex[:12]}", tenant_id=self.tenant_id, offer_id=offer_id,
            position=position,
            subcategory_id=component.subcategory_id if hasattr(component, "subcategory_id") else component["subcategory_id"],
            quantity=component.quantity if hasattr(component, "quantity") else component["quantity"],
            allow_repeated_products=(component.allow_repeated_products if hasattr(component, "allow_repeated_products") else component.get("allow_repeated_products", True)),
            restrictions=((component.restrictions.model_dump(exclude_none=True) if component.restrictions else {}) if hasattr(component, "restrictions") else component.get("restrictions") or {}),
        ) for position, component in enumerate(components)]

    @staticmethod
    def _copy_label(value: str, max_length: int) -> str:
        suffix = " (cópia)"
        return f"{value[:max_length - len(suffix)].rstrip()}{suffix}"

    @staticmethod
    def _assert_offer_period(starts_at, ends_at, campaign: StrategicCampaign) -> None:
        if starts_at and ends_at and ends_at <= starts_at:
            raise DomainError("O encerramento da oferta deve ser posterior ao início.", code="InvalidStrategicOfferPeriod")
        if campaign.starts_at and starts_at and starts_at < campaign.starts_at:
            raise DomainError("A oferta não pode iniciar antes da campanha.", code="StrategicOfferOutsideCampaignPeriod")
        if campaign.ends_at and ends_at and ends_at > campaign.ends_at:
            raise DomainError("A oferta não pode terminar depois da campanha.", code="StrategicOfferOutsideCampaignPeriod")

    def _assert_slug(self, slug: str, current_id: str | None = None) -> None:
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise DomainError("Slug inválido. Use letras minúsculas, números e hífens.", code="InvalidStrategicCampaignSlug")
        query = self.db.query(StrategicCampaign).filter(StrategicCampaign.tenant_id == self.tenant_id, StrategicCampaign.slug == slug)
        if current_id:
            query = query.filter(StrategicCampaign.id != current_id)
        if query.first():
            raise DomainError("Slug já utilizado neste tenant.", code="StrategicCampaignSlugConflict")
        self._assert_public_slug_available(slug, current_id)

    def _assert_public_slug_available(self, slug: str, current_id: str | None = None) -> None:
        published_rows = self.db.query(StrategicCampaignVersion).join(
            StrategicCampaign,
            (StrategicCampaign.id == StrategicCampaignVersion.campaign_id)
            & (StrategicCampaign.tenant_id == StrategicCampaignVersion.tenant_id)
            & (StrategicCampaign.published_version == StrategicCampaignVersion.version),
        ).filter(StrategicCampaign.tenant_id == self.tenant_id).all()
        for published in published_rows:
            if current_id and published.campaign_id == current_id:
                continue
            if self._snapshot_document(published).campaign.slug == slug:
                raise DomainError("Slug já utilizado neste tenant.", code="StrategicCampaignSlugConflict")

    @staticmethod
    def _snapshot_document(version: StrategicCampaignVersion) -> StrategicCampaignSnapshot:
        try:
            snapshot = deepcopy(version.snapshot or {})
            snapshot.setdefault("schema_version", STRATEGIC_CAMPAIGN_SNAPSHOT_SCHEMA_VERSION)
            campaign = snapshot.get("campaign")
            if isinstance(campaign, dict):
                campaign.setdefault("status", StrategicCampaignStatus.active.value)
                campaign.setdefault("marketing_config", {})
                campaign.setdefault("published_version", version.version)
            offers = snapshot.get("offers")
            if isinstance(offers, list):
                for display_order, offer in enumerate(offers):
                    if isinstance(offer, dict):
                        offer.setdefault("campaign_id", version.campaign_id)
                        offer.setdefault("active", True)
                        offer.setdefault("display_order", display_order)
                        offer.setdefault("archived_at", None)
                        if "reference_type" not in offer:
                            offer["reference_type"] = "kit" if offer.get("kit_id") else "product"
                        offer.setdefault("components", [])
            return StrategicCampaignSnapshot.model_validate(snapshot)
        except Exception as exc:
            raise DomainError(
                "Snapshot publicado da campanha está inválido.",
                code="InvalidStrategicCampaignSnapshot",
            ) from exc

    @staticmethod
    def _assert_public_period(starts_at, ends_at) -> None:
        now = datetime.now(timezone.utc)
        if starts_at and starts_at > now or ends_at and ends_at <= now:
            raise DomainError(
                "Campanha estratégica fora do período de venda.",
                code="StrategicCampaignUnavailable",
            )

    @staticmethod
    def _assert_period(starts_at, ends_at) -> None:
        if starts_at and ends_at and ends_at <= starts_at:
            raise DomainError("O encerramento deve ser posterior ao início.", code="InvalidStrategicCampaignPeriod")

    @staticmethod
    def _assert_commercial_config(config: StrategicCommercialConfig | dict) -> None:
        try:
            StrategicCommercialConfig.model_validate(config)
        except Exception as exc:
            raise DomainError("ConfiguraÃ§Ã£o comercial invÃ¡lida.", code="InvalidStrategicCommercialConfig") from exc

    @staticmethod
    def _assert_transition(current, target) -> None:
        allowed = {"draft": {"scheduled", "active", "archived"}, "scheduled": {"active", "paused", "ended"}, "active": {"paused", "sold_out", "ended"}, "paused": {"active", "ended"}, "sold_out": {"ended"}, "ended": {"archived"}, "archived": set()}
        if current != target and target.value not in allowed.get(current.value, set()):
            raise DomainError(f"Transição de campanha inválida: {current.value} -> {target.value}.", code="InvalidStrategicCampaignTransition")

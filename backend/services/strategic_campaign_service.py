from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session, selectinload

from backend.core.exceptions import DomainError
from backend.models.product import Product
from backend.models.campaign import PromotionalKit
from backend.models.strategic_campaign import StrategicCampaign, StrategicCampaignStatus, StrategicCampaignVersion, StrategicOffer
from backend.schemas.strategic_campaign import StrategicCampaignCreate, StrategicCampaignUpdate, StrategicOfferCreate, StrategicOfferUpdate, StrategicCommercialConfig


class StrategicCampaignService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def _campaign(self, campaign_id: str) -> StrategicCampaign:
        row = self.db.query(StrategicCampaign).options(selectinload(StrategicCampaign.offers)).filter(
            StrategicCampaign.tenant_id == self.tenant_id, StrategicCampaign.id == campaign_id,
        ).first()
        if not row:
            raise DomainError("Campanha estratégica não encontrada.", code="StrategicCampaignNotFound")
        return row

    def list(self) -> list[StrategicCampaign]:
        return self.db.query(StrategicCampaign).options(selectinload(StrategicCampaign.offers)).filter(
            StrategicCampaign.tenant_id == self.tenant_id,
        ).order_by(StrategicCampaign.updated_at.desc()).all()

    def get_public(self, slug: str) -> StrategicCampaign:
        row = self.db.query(StrategicCampaign).options(selectinload(StrategicCampaign.offers)).filter(
            StrategicCampaign.tenant_id == self.tenant_id,
            StrategicCampaign.slug == slug,
            StrategicCampaign.status == StrategicCampaignStatus.active,
            StrategicCampaign.published_version.isnot(None),
        ).first()
        if not row:
            raise DomainError("Campanha estratégica não encontrada.", code="StrategicCampaignNotFound")
        now = datetime.now(timezone.utc)
        if row.starts_at and row.starts_at > now or row.ends_at and row.ends_at <= now:
            raise DomainError("Campanha estratégica fora do período de venda.", code="StrategicCampaignUnavailable")
        return row

    def resolve_checkout_offer(self, offer_id: str) -> tuple[StrategicCampaign, StrategicOffer]:
        offer = self._offer(offer_id)
        campaign = self.get_public_by_id(offer.campaign_id)
        if not offer.active:
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
        if row.published_version is not None and any(key in data for key in {"name", "commercial_name", "slug", "description", "starts_at", "ends_at", "visual_config", "commercial_config"}):
            raise DomainError("Campanha publicada exige nova versao para alterar seu conteudo.", code="PublishedCampaignImmutable")
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

    def add_offer(self, campaign_id: str, payload: StrategicOfferCreate) -> StrategicOffer:
        campaign = self._campaign(campaign_id)
        if campaign.published_version is not None:
            raise DomainError("Campanha publicada não pode receber oferta sem nova versão.", code="PublishedCampaignImmutable")
        if self.db.query(StrategicOffer).filter(StrategicOffer.tenant_id == self.tenant_id, StrategicOffer.campaign_id == campaign_id, StrategicOffer.code == payload.code).first():
            raise DomainError("Código de oferta já utilizado nesta campanha.", code="StrategicOfferCodeConflict")
        if payload.product_id and not self.db.query(Product).filter(Product.tenant_id == self.tenant_id, Product.id == payload.product_id, Product.active.is_(True)).first():
            raise DomainError("Produto da oferta não encontrado.", code="StrategicOfferProductNotFound")
        if payload.kit_id and not self.db.query(PromotionalKit).filter(PromotionalKit.tenant_id == self.tenant_id, PromotionalKit.id == payload.kit_id, PromotionalKit.active.is_(True)).first():
            raise DomainError("Kit da oferta não encontrado.", code="StrategicOfferKitNotFound")
        self._assert_offer_period(payload.sales_starts_at, payload.sales_ends_at, campaign)
        row = StrategicOffer(id=f"so-{uuid.uuid4().hex[:12]}", tenant_id=self.tenant_id, campaign_id=campaign_id, **payload.model_dump())
        self.db.add(row)
        self.db.commit()
        return row

    def update_offer(self, offer_id: str, payload: StrategicOfferUpdate) -> StrategicOffer:
        row = self._offer(offer_id)
        if self._campaign(row.campaign_id).published_version is not None:
            raise DomainError("Oferta publicada é imutável.", code="PublishedCampaignImmutable")
        data = payload.model_dump(exclude_unset=True)
        original = data.get("price_original", row.price_original)
        promotional = data.get("price_promotional", row.price_promotional)
        if promotional > original:
            raise DomainError("O preço promocional não pode superar o preço original.", code="InvalidStrategicOfferPrice")
        self._assert_offer_period(data.get("sales_starts_at", row.sales_starts_at), data.get("sales_ends_at", row.sales_ends_at), self._campaign(row.campaign_id))
        for key, value in data.items():
            setattr(row, key, value)
        self.db.commit()
        return row

    def publish(self, campaign_id: str) -> StrategicCampaignVersion:
        row = self._campaign(campaign_id)
        if not row.offers:
            raise DomainError("Campanha precisa de ao menos uma oferta para publicar.", code="StrategicCampaignOfferRequired")
        version = (row.published_version or 0) + 1
        snapshot = {
            "campaign": {"id": row.id, "name": row.name, "commercial_name": row.commercial_name, "slug": row.slug, "description": row.description, "starts_at": row.starts_at.isoformat() if row.starts_at else None, "ends_at": row.ends_at.isoformat() if row.ends_at else None, "visual_config": row.visual_config or {}, "commercial_config": row.commercial_config or {}},
            "offers": [{"id": o.id, "code": o.code, "title": o.title, "description": o.description, "product_id": o.product_id, "kit_id": o.kit_id, "price_original": str(o.price_original), "price_promotional": str(o.price_promotional), "quantity_limit": o.quantity_limit, "max_per_customer": o.max_per_customer, "sales_starts_at": o.sales_starts_at.isoformat() if o.sales_starts_at else None, "sales_ends_at": o.sales_ends_at.isoformat() if o.sales_ends_at else None, "show_when_sold_out": o.show_when_sold_out, "button_text": o.button_text, "image_desktop_url": o.image_desktop_url, "image_mobile_url": o.image_mobile_url, "badge_text": o.badge_text, "highlighted": o.highlighted, "config": o.config} for o in sorted(row.offers, key=lambda x: (x.display_order, x.id)) if o.active],
        }
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

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace
from typing import Iterable

from sqlalchemy.orm import Session, selectinload

from backend.core.exceptions import DomainError
from backend.models.product import Product, ProductCategory
from backend.models.order import Order, OrderCommercialGroup, OrderStatus
from backend.models.strategic_campaign import (
    StrategicCampaign,
    StrategicCampaignStatus,
    StrategicCampaignVersion,
    StrategicOffer,
    StrategicOfferComponent,
    StrategicOfferRedemption,
    StrategicReservation,
)
from backend.schemas.product import ProductOut
from backend.schemas.order import StrategicOfferGroupIn
from backend.schemas.strategic_campaign import StrategicCampaignSnapshot


CENT = Decimal("0.01")
ENTRY_CHANNELS = {"landing_page", "pdv", "operations", "phone", "whatsapp", "counter"}


@dataclass(frozen=True)
class ResolvedStrategicGroup:
    request: StrategicOfferGroupIn
    campaign: StrategicCampaign
    offer: StrategicOffer
    item_start: int
    item_count: int
    step_subcategories: tuple[str | None, ...]


class StrategicOfferCompositionService:
    """Fail-closed resolver for published strategic offer compositions."""

    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def available_campaigns(self, entry_channel: str) -> list[dict]:
        self._assert_channel(entry_channel)
        now = datetime.now(timezone.utc)
        campaigns = self.db.query(StrategicCampaign).filter(
            StrategicCampaign.tenant_id == self.tenant_id,
            StrategicCampaign.status == StrategicCampaignStatus.active,
            StrategicCampaign.published_version.is_not(None),
        ).all()
        result = []
        for live_campaign in campaigns:
            campaign, offers = self._published_snapshot(live_campaign)
            if not self._campaign_is_available(campaign, now):
                continue
            commercially_active = [offer for offer in offers if self._offer_is_available(offer, now)]
            visible = [offer for offer in commercially_active if self._has_global_capacity(offer) or offer.show_when_sold_out]
            available = [offer for offer in commercially_active if self._has_global_capacity(offer)]
            if visible:
                result.append({
                    "id": campaign.id,
                    "name": campaign.name,
                    "commercial_name": campaign.commercial_name or campaign.name,
                    "slug": campaign.slug,
                    "published_version": campaign.published_version,
                    "offers_available": len(available),
                })
        return sorted(result, key=lambda row: (row["commercial_name"].casefold(), row["id"]))

    def available_offers(self, campaign_id: str, entry_channel: str) -> list[dict]:
        self._assert_channel(entry_channel)
        live_campaign = self.db.query(StrategicCampaign).filter(
            StrategicCampaign.tenant_id == self.tenant_id,
            StrategicCampaign.id == campaign_id,
            StrategicCampaign.status == StrategicCampaignStatus.active,
            StrategicCampaign.published_version.is_not(None),
        ).first()
        if not live_campaign:
            raise DomainError("Campanha estrategica indisponivel.", code="StrategicCampaignUnavailable")
        campaign, rows = self._published_snapshot(live_campaign)
        now = datetime.now(timezone.utc)
        if not self._campaign_is_available(campaign, now):
            raise DomainError("Campanha estrategica indisponivel.", code="StrategicCampaignUnavailable")
        return [
            self._offer_document(campaign, offer)
            for offer in rows
            if self._offer_is_available(offer, now)
            and (self._has_global_capacity(offer) or offer.show_when_sold_out)
        ]

    def configuration(self, offer_id: str, campaign_version: int | None = None) -> dict:
        campaign, offer = self._published_offer(offer_id, campaign_version)
        steps = []
        minimum = Decimal("0.00")
        maximum = Decimal("0.00")
        if offer.reference_type in {"subcategory", "mixed_subcategories"}:
            for component in offer.components:
                products = self._eligible_products(component.subcategory_id)
                prices = [Decimal(str(product.price)).quantize(CENT) for product in products]
                minimum += min(prices) * component.quantity
                maximum += max(prices) * component.quantity
                for occurrence in range(1, component.quantity + 1):
                    steps.append({
                        "key": self._step_key(component.position, occurrence),
                        "step_key": self._step_key(component.position, occurrence),
                        "position": len(steps),
                        "subcategory_id": component.subcategory_id,
                        "eligible_products": [self._product_document(product) for product in products],
                        "restrictions": component.restrictions or {},
                    })
        elif offer.reference_type == "product":
            product = self._product(offer.product_id)
            if product is None:
                raise DomainError("Produto da oferta indisponivel.", code="StrategicOfferProductUnavailable")
            from backend.services.inventory_service import ProductInventoryAvailabilityService
            availability = ProductInventoryAvailabilityService(self.db, self.tenant_id).product_payloads([product.id])
            if availability.get(product.id, {}).get("inventory_available") is False:
                raise DomainError("Produto da oferta indisponivel no estoque.", code="StrategicOfferProductUnavailable")
            steps.append({
                "key": "product:1",
                "step_key": "product:1",
                "position": 0,
                "subcategory_id": product.subcategory_id,
                "eligible_products": [self._product_document(product)],
                "restrictions": (offer.config or {}).get("restrictions") or {},
            })
            base = Decimal(str(offer.price_original or product.price or 0)).quantize(CENT)
            minimum = maximum = base
        elif offer.reference_type == "kit":
            steps.append({
                "key": "kit:1",
                "step_key": "kit:1",
                "position": 0,
                "subcategory_id": None,
                "eligible_products": [],
                "kit_id": offer.kit_id,
                "restrictions": {},
            })
            base = Decimal(str(offer.price_original or 0)).quantize(CENT)
            minimum = maximum = base
        else:
            base = Decimal(str(offer.price_original or 0)).quantize(CENT)
            minimum = maximum = base
        promotional_min = self.promotional_total(offer, minimum)
        promotional_max = self.promotional_total(offer, maximum)
        return {
            "offer_id": offer.id,
            "campaign_id": campaign.id,
            "campaign_version": campaign.published_version,
            "composition_revision": offer.composition_revision,
            "reference_type": offer.reference_type,
            "pricing_strategy": offer.pricing_strategy,
            "price_range": {
                "minimum": promotional_min,
                "maximum": promotional_max,
                "original_minimum": minimum,
                "original_maximum": maximum,
                "fixed_promotional": offer.fixed_promotional_price,
            },
            "steps": steps,
        }

    def expand_groups(self, groups: Iterable[StrategicOfferGroupIn], *, item_start: int = 0, customer_id: str | None = None, consume_limits: bool = False, reservation_id: str | None = None) -> tuple[list, list[ResolvedStrategicGroup]]:
        requests = tuple(groups)
        requested_by_offer = Counter(request.offer_id for request in requests for _ in range(request.quantity))
        items = []
        resolved = []
        offset = item_start
        checked_limits: set[str] = set()
        for request in requests:
            campaign, offer = self._published_offer(request.offer_id, request.campaign_version, lock=consume_limits)
            if consume_limits and offer.id not in checked_limits:
                self._assert_purchase_limits(
                    offer, requested_by_offer[offer.id], customer_id,
                    reservation_id=reservation_id,
                    require_confirmed_reservation=consume_limits,
                )
                checked_limits.add(offer.id)
            if offer.composition_revision != request.composition_revision:
                raise DomainError("A composicao da oferta foi atualizada. Recarregue a campanha.", code="StrategicOfferCompositionChanged")
            expected, subcategories = self._expected_steps(offer, request.quantity)
            supplied = [selection.step_key for selection in request.selections]
            if supplied != expected:
                raise DomainError("As etapas da oferta estao incompletas ou fora de ordem.", code="StrategicOfferCompositionInvalid")
            seen: dict[tuple[int, int], set[str]] = {}
            for selection, subcategory_id in zip(request.selections, subcategories):
                item = selection.item
                if offer.reference_type == "kit":
                    if item.product_id or item.kit_id != offer.kit_id or item.quantity != 1:
                        raise DomainError("Cada etapa estrategica de combo exige exatamente o combo publicado.", code="StrategicOfferCompositionInvalid")
                    items.append(item)
                    continue
                if item.kit_id or not item.product_id or item.quantity != 1:
                    raise DomainError("Cada etapa estrategica exige exatamente um produto.", code="StrategicOfferCompositionInvalid")
                product = self._product(item.product_id, subcategory_id=subcategory_id)
                if offer.reference_type == "product" and product.id != offer.product_id:
                    product = None
                if not product:
                    raise DomainError("Produto nao pertence a subcategoria publicada.", code="StrategicOfferProductInvalid")
                if offer.reference_type == "product":
                    restrictions = (offer.config or {}).get("restrictions") or {}
                else:
                    component_position = int(selection.step_key.split("component-")[-1].split(":", 1)[0])
                    component = next(row for row in offer.components if row.position == component_position)
                    group_index = self._step_group_index(selection.step_key)
                    bucket = seen.setdefault((group_index, component_position), set())
                    if not component.allow_repeated_products and product.id in bucket:
                        raise DomainError("A oferta nao permite repetir produtos nesta subcategoria.", code="StrategicOfferRepeatedProduct")
                    bucket.add(product.id)
                    restrictions = component.restrictions or {}
                self._assert_item_restrictions(item, restrictions)
                items.append(item)
            offer._pricing_quantity = request.quantity
            resolved.append(ResolvedStrategicGroup(request, campaign, offer, offset, len(request.selections), tuple(subcategories)))
            offset += len(request.selections)
        return items, resolved

    def _assert_purchase_limits(
        self,
        offer: StrategicOffer,
        quantity: int,
        customer_id: str | None,
        *,
        reservation_id: str | None = None,
        require_confirmed_reservation: bool = False,
    ) -> None:
        consumed = self.db.query(StrategicOfferRedemption).filter(
            StrategicOfferRedemption.tenant_id == self.tenant_id,
            StrategicOfferRedemption.offer_id == offer.id,
            StrategicOfferRedemption.status == "confirmed",
        )
        reserved_quantity = 0
        reservation = None
        if reservation_id:
            reservation = self.db.query(StrategicReservation).filter(
                StrategicReservation.tenant_id == self.tenant_id,
                StrategicReservation.id == reservation_id,
            ).with_for_update().first()
            if not reservation:
                raise DomainError("Reserva estrategica nao encontrada.", code="StrategicReservationNotFound")
            if reservation.offer_id == offer.id:
                allowed_statuses = {"confirmed"} if require_confirmed_reservation else {"held", "confirmed"}
                if reservation.status not in allowed_statuses or reservation.order_id is not None:
                    raise DomainError("Reserva estrategica indisponivel para este pedido.", code="StrategicReservationUnavailable")
                if reservation.quantity != quantity:
                    raise DomainError("A quantidade do pedido difere da reserva.", code="StrategicReservationQuantityMismatch")
                if reservation.customer_reference and reservation.customer_reference != customer_id:
                    raise DomainError("A reserva pertence a outro cliente.", code="StrategicReservationCustomerMismatch")
                reserved_quantity = reservation.quantity
        total = self._consumed_quantity(offer) - reserved_quantity
        if offer.quantity_limit is not None and total + quantity > offer.quantity_limit:
            raise DomainError("Oferta estrategica esgotada.", code="StrategicOfferSoldOut")
        if offer.max_per_customer is not None:
            if not customer_id:
                raise DomainError("Esta oferta exige identificacao do cliente.", code="StrategicOfferCustomerRequired")
            customer_total = sum(row.quantity for row in consumed.filter(StrategicOfferRedemption.customer_id == customer_id).all())
            customer_total += sum(row.quantity for row in self.db.query(StrategicReservation).filter(
                StrategicReservation.tenant_id == self.tenant_id,
                StrategicReservation.offer_id == offer.id,
                StrategicReservation.customer_reference == customer_id,
                StrategicReservation.status.in_(("held", "confirmed")),
                StrategicReservation.order_id.is_(None),
            ).all() if row.id != reservation_id)
            if customer_total + quantity > offer.max_per_customer:
                raise DomainError("Limite por cliente excedido para esta oferta.", code="StrategicOfferCustomerLimit")

    def _consumed_quantity(self, offer: StrategicOffer) -> int:
        redeemed = sum(row.quantity for row in self.db.query(StrategicOfferRedemption).filter(
            StrategicOfferRedemption.tenant_id == self.tenant_id,
            StrategicOfferRedemption.offer_id == offer.id,
            StrategicOfferRedemption.status == "confirmed",
        ).all())
        reserved = sum(row.quantity for row in self.db.query(StrategicReservation).filter(
            StrategicReservation.tenant_id == self.tenant_id,
            StrategicReservation.offer_id == offer.id,
            StrategicReservation.status.in_(("held", "confirmed")),
            StrategicReservation.order_id.is_(None),
        ).all())
        return redeemed + reserved

    def _has_global_capacity(self, offer: StrategicOffer) -> bool:
        return offer.quantity_limit is None or self._consumed_quantity(offer) < offer.quantity_limit

    @staticmethod
    def promotional_total(offer: StrategicOffer, original: Decimal, quantity: int | None = None) -> Decimal:
        original = Decimal(original).quantize(CENT, rounding=ROUND_HALF_UP)
        units = quantity if quantity is not None else getattr(offer, "_pricing_quantity", 1)
        if units < 1:
            raise DomainError("Quantidade da oferta invalida.", code="StrategicOfferQuantityInvalid")
        if offer.pricing_strategy == "percentage":
            percent = Decimal(offer.discount_percent or 0)
            return max(Decimal("0.00"), original * (Decimal("100") - percent) / Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP)
        if offer.pricing_strategy == "fixed_discount":
            return max(Decimal("0.00"), original - Decimal(offer.discount_amount or 0) * units).quantize(CENT, rounding=ROUND_HALF_UP)
        if offer.pricing_strategy == "fixed_price":
            return (Decimal(offer.fixed_promotional_price or 0) * units).quantize(CENT, rounding=ROUND_HALF_UP)
        return original

    def _published_offer(self, offer_id: str, campaign_version: int | None, *, lock: bool = False) -> tuple[StrategicCampaign, StrategicOffer]:
        now = datetime.now(timezone.utc)
        offer_query = self.db.query(StrategicOffer).filter(
            StrategicOffer.tenant_id == self.tenant_id,
            StrategicOffer.id == offer_id,
        )
        if lock:
            offer_query = offer_query.with_for_update()
        live_offer = offer_query.first()
        if not live_offer:
            raise DomainError("Oferta estrategica nao encontrada.", code="StrategicOfferNotFound")
        campaign = self.db.query(StrategicCampaign).filter(
            StrategicCampaign.tenant_id == self.tenant_id,
            StrategicCampaign.id == live_offer.campaign_id,
        ).first()
        if not campaign or campaign.status != StrategicCampaignStatus.active or campaign.published_version is None:
            raise DomainError("Campanha estrategica indisponivel.", code="StrategicCampaignUnavailable")
        if campaign_version is not None and campaign.published_version != campaign_version:
            raise DomainError("A versao publicada da campanha foi atualizada.", code="StrategicCampaignVersionChanged")
        campaign, offers = self._published_snapshot(campaign)
        if not self._campaign_is_available(campaign, now):
            raise DomainError("Campanha estrategica indisponivel.", code="StrategicCampaignUnavailable")
        offer = next((row for row in offers if row.id == offer_id), None)
        if not offer:
            raise DomainError("Oferta nao pertence a versao publicada.", code="StrategicOfferUnavailable")
        if not self._offer_is_available(offer, now):
            raise DomainError("Oferta estrategica indisponivel.", code="StrategicOfferUnavailable")
        return campaign, offer

    def _published_snapshot(self, live_campaign: StrategicCampaign) -> tuple[SimpleNamespace, list[SimpleNamespace]]:
        version = self.db.query(StrategicCampaignVersion).filter(
            StrategicCampaignVersion.tenant_id == self.tenant_id,
            StrategicCampaignVersion.campaign_id == live_campaign.id,
            StrategicCampaignVersion.version == live_campaign.published_version,
        ).first()
        if not version:
            raise DomainError("Versao publicada da campanha nao encontrada.", code="StrategicCampaignVersionInvalid")
        try:
            raw_snapshot = deepcopy(version.snapshot or {})
            for document in raw_snapshot.get("offers", []):
                if isinstance(document, dict) and "reference_type" not in document:
                    document["reference_type"] = "kit" if document.get("kit_id") else "product"
            snapshot = StrategicCampaignSnapshot.model_validate(raw_snapshot)
        except (TypeError, ValueError) as exc:
            raise DomainError("Snapshot publicado da campanha e invalido.", code="StrategicCampaignVersionInvalid") from exc
        if snapshot.campaign.id != live_campaign.id or snapshot.campaign.published_version != live_campaign.published_version:
            raise DomainError("Snapshot publicado da campanha e inconsistente.", code="StrategicCampaignVersionInvalid")
        campaign = SimpleNamespace(**snapshot.campaign.model_dump(mode="python"), tenant_id=self.tenant_id)
        offers = []
        for document in snapshot.offers:
            data = document.model_dump(mode="python")
            components = [
                SimpleNamespace(position=position, **component)
                for position, component in enumerate(data.pop("components", []))
            ]
            offers.append(SimpleNamespace(**data, tenant_id=self.tenant_id, components=components))
        return campaign, sorted(offers, key=lambda row: (row.display_order, row.id))

    def _product(self, product_id: str | None, *, subcategory_id: str | None = None) -> Product | None:
        if not product_id:
            return None
        query = self.db.query(Product).filter(
            Product.tenant_id == self.tenant_id,
            Product.id == product_id,
            Product.active.is_(True),
        )
        if subcategory_id is not None:
            query = query.filter(Product.subcategory_id == subcategory_id)
        return query.first()

    @classmethod
    def _expected_steps(cls, offer, quantity: int) -> tuple[list[str], list[str | None]]:
        expected: list[str] = []
        subcategories: list[str | None] = []
        if offer.reference_type == "product":
            for group_index in range(1, quantity + 1):
                key = "product:1"
                if quantity > 1:
                    key = f"group-{group_index}:{key}"
                expected.append(key)
                subcategories.append(None)
            return expected, subcategories
        if offer.reference_type == "kit":
            for group_index in range(1, quantity + 1):
                key = "kit:1"
                if quantity > 1:
                    key = f"group-{group_index}:{key}"
                expected.append(key)
                subcategories.append(None)
            return expected, subcategories
        if offer.reference_type not in {"subcategory", "mixed_subcategories"}:
            raise DomainError("Tipo de referencia estrategica nao suportado.", code="StrategicOfferGroupInvalid")
        for group_index in range(1, quantity + 1):
            for component in offer.components:
                for occurrence in range(1, component.quantity + 1):
                    key = cls._step_key(component.position, occurrence)
                    if quantity > 1:
                        key = f"group-{group_index}:{key}"
                    expected.append(key)
                    subcategories.append(component.subcategory_id)
        return expected, subcategories

    @staticmethod
    def _step_group_index(step_key: str) -> int:
        if step_key.startswith("group-"):
            return int(step_key.split(":", 1)[0].removeprefix("group-"))
        return 1

    @staticmethod
    def _assert_item_restrictions(item, restrictions: dict) -> None:
        checks = (
            ("size_ids", item.selected_size_id),
            ("crust_ids", item.selected_crust_type_id),
            ("border_ids", item.selected_border_id),
            ("drink_ids", item.selected_drink_variant_id),
        )
        for key, selected in checks:
            allowed = restrictions.get(key)
            if allowed is not None and selected not in allowed:
                raise DomainError("Configuracao do produto nao atende as restricoes publicadas.", code="StrategicOfferRestrictionInvalid")
        allowed_options = restrictions.get("option_ids")
        if allowed_options is not None and any(selection.option_id not in allowed_options for selection in item.option_selections):
            raise DomainError("Opcao do produto nao atende as restricoes publicadas.", code="StrategicOfferRestrictionInvalid")
        flavor_count = restrictions.get("flavor_count")
        if flavor_count is not None and item.flavor_division != flavor_count:
            raise DomainError("Quantidade de sabores nao atende as restricoes publicadas.", code="StrategicOfferRestrictionInvalid")

    def _eligible_products(self, subcategory_id: str) -> list[Product]:
        category = self.db.query(ProductCategory).filter(
            ProductCategory.tenant_id == self.tenant_id,
            ProductCategory.id == subcategory_id,
            ProductCategory.parent_id.is_not(None),
            ProductCategory.active.is_(True),
        ).first()
        if not category:
            raise DomainError("Subcategoria da oferta nao encontrada.", code="StrategicOfferSubcategoryNotFound")
        products = self.db.query(Product).filter(
            Product.tenant_id == self.tenant_id,
            Product.subcategory_id == subcategory_id,
            Product.active.is_(True),
        ).order_by(Product.name, Product.id).all()
        if products:
            from backend.services.inventory_service import ProductInventoryAvailabilityService
            availability = ProductInventoryAvailabilityService(self.db, self.tenant_id).product_payloads(
                [product.id for product in products],
            )
            products = [
                product for product in products
                if availability.get(product.id, {}).get("inventory_available", True)
            ]
        if not products:
            raise DomainError("Subcategoria sem produtos vendaveis.", code="StrategicOfferSubcategoryEmpty")
        return products

    @staticmethod
    def _offer_is_available(offer: StrategicOffer, now: datetime) -> bool:
        return bool(
            offer.active
            and offer.archived_at is None
            and (offer.sales_starts_at is None or offer.sales_starts_at <= now)
            and (offer.sales_ends_at is None or offer.sales_ends_at > now)
        )

    @staticmethod
    def _campaign_is_available(campaign, now: datetime) -> bool:
        return bool(
            (campaign.starts_at is None or campaign.starts_at <= now)
            and (campaign.ends_at is None or campaign.ends_at > now)
        )

    @staticmethod
    def _step_key(position: int, occurrence: int) -> str:
        return f"component-{position}:{occurrence}"

    @staticmethod
    def _product_document(product: Product) -> dict:
        return ProductOut.model_validate(product).model_dump(mode="json")

    def _offer_document(self, campaign: StrategicCampaign, offer: StrategicOffer) -> dict:
        consumed = self._consumed_quantity(offer)
        remaining = None if offer.quantity_limit is None else max(0, offer.quantity_limit - consumed)
        return {
            "id": offer.id,
            "campaign_id": campaign.id,
            "campaign_version": campaign.published_version,
            "composition_revision": offer.composition_revision,
            "code": offer.code,
            "title": offer.title,
            "description": offer.description,
            "product_id": offer.product_id,
            "kit_id": offer.kit_id,
            "reference_type": offer.reference_type,
            "components": [
                {
                    "subcategory_id": component.subcategory_id,
                    "quantity": component.quantity,
                    "allow_repeated_products": component.allow_repeated_products,
                    "restrictions": component.restrictions or {},
                }
                for component in offer.components
            ],
            "pricing_strategy": offer.pricing_strategy,
            "discount_percent": offer.discount_percent,
            "discount_amount": offer.discount_amount,
            "fixed_promotional_price": offer.fixed_promotional_price,
            "price_original": offer.price_original,
            "price_promotional": offer.price_promotional,
            "active": offer.active,
            "display_order": offer.display_order,
            "quantity_limit": offer.quantity_limit,
            "max_per_customer": offer.max_per_customer,
            "sales_starts_at": offer.sales_starts_at,
            "sales_ends_at": offer.sales_ends_at,
            "show_when_sold_out": offer.show_when_sold_out,
            "button_text": offer.button_text,
            "image_desktop_url": offer.image_desktop_url,
            "image_mobile_url": offer.image_mobile_url,
            "badge_text": offer.badge_text,
            "highlighted": offer.highlighted,
            "config": offer.config or {},
            "archived_at": offer.archived_at,
            "available": remaining is None or remaining > 0,
            "remaining_quantity": remaining,
        }

    @staticmethod
    def _assert_channel(entry_channel: str) -> None:
        if entry_channel not in ENTRY_CHANNELS:
            raise DomainError("Canal de entrada invalido.", code="InvalidStrategicEntryChannel")

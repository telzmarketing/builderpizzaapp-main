"""Server-side resolution of closed promotional kits for checkout.

The checkout keeps using ``OrderItem`` as the physical/commercial line used by
KDS, inventory and CMV.  A closed kit is therefore expanded into immutable
component lines, while its price and identity are retained by the caller in
the existing order-item promotion snapshot fields.  No new persistence model
is needed for this contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from backend.core.exceptions import DomainError
from backend.core.tenant_context import TenantContext, TenantContextMissing
from backend.core.tenant_ownership import scope_query_to_tenant
from backend.models.campaign import PromotionalKit, PromotionalKitItem
from backend.models.product import Product
from backend.schemas.order import CartItemIn


@dataclass(frozen=True)
class ResolvedComboComponent:
    item: CartItemIn
    kit_id: str
    kit_name: str
    unit_price: float


class ComboService:
    """Resolve only active, tenant-owned kits and their current composition."""

    def __init__(self, db: Session, tenant_context: TenantContext | None):
        if tenant_context is None or not tenant_context.tenant_id:
            raise TenantContextMissing("Contexto de tenant obrigatorio para combos.")
        self.db = db
        self.tenant_context = tenant_context

    def _query(self, model):
        return scope_query_to_tenant(
            self.db.query(model), model, self.tenant_context, enabled=True
        )

    def expand(self, items: list[CartItemIn]) -> tuple[list[CartItemIn], dict[int, ResolvedComboComponent]]:
        """Expand combo lines and return metadata keyed by expanded item identity.

        The input line's quantity is the number of kits.  Component quantity is
        multiplied by that integer.  The kit promotional price is allocated in
        cents by catalog base-price weight, with the final component receiving
        the rounding remainder; the sum is therefore exactly the closed price.
        """
        expanded: list[CartItemIn] = []
        metadata: dict[int, ResolvedComboComponent] = {}
        for item in items:
            if not item.kit_id:
                expanded.append(item)
                continue
            if item.quantity < 1 or isinstance(item.quantity, bool) or not isinstance(item.quantity, int):
                raise DomainError("A quantidade do combo deve ser um inteiro positivo.", code="InvalidComboQuantity")
            if item.product_id:
                raise DomainError("Combo fechado nao aceita produto ou componente customizado.", code="ComboCustomizationNotAllowed")
            if (
                item.selected_size_id or item.flavors or item.add_ons or item.option_selections
                or item.selected_crust_type_id or item.selected_border_id
                or item.selected_drink_variant_id or item.notes
                or item.flavor_division != 1
            ):
                raise DomainError("Combo fechado nao aceita customizacao de componentes.", code="ComboCustomizationNotAllowed")
            kit = (
                self._query(PromotionalKit)
                .filter(PromotionalKit.id == item.kit_id, PromotionalKit.active.is_(True))
                .first()
            )
            now = datetime.now(timezone.utc)
            if not kit or (kit.valid_until and kit.valid_until < now):
                raise DomainError("Combo inexistente, inativo ou expirado.", code="ComboUnavailable")
            kit_items = self._query(PromotionalKitItem).filter(PromotionalKitItem.kit_id == kit.id).all()
            if not kit_items:
                raise DomainError("Combo sem composicao publicada.", code="ComboCompositionInvalid")
            if any(row.quantity < 1 or isinstance(row.quantity, bool) or not isinstance(row.quantity, int) for row in kit_items):
                raise DomainError("A composicao do combo possui quantidade invalida.", code="ComboCompositionInvalid")
            if len({row.product_id for row in kit_items}) != len(kit_items):
                raise DomainError("A composicao do combo possui componentes duplicados.", code="ComboCompositionInvalid")

            product_ids = [row.product_id for row in kit_items]
            products = {
                product.id: product
                for product in self._query(Product)
                .filter(Product.id.in_(product_ids), Product.active.is_(True))
                .all()
            }
            if len(products) != len(product_ids):
                raise DomainError("O combo possui produto inativo ou de outro tenant.", code="ComboCompositionInvalid")

            weights = [Decimal(str(products[row.product_id].price or 0)) * row.quantity for row in kit_items]
            weight_total = sum(weights, Decimal("0"))
            closed_price = (Decimal(str(kit.price_promotional or 0)) * item.quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if closed_price < 0 or weight_total <= 0:
                raise DomainError("O preco fechado do combo e invalido.", code="ComboPriceInvalid")
            allocated: list[Decimal] = []
            remaining = closed_price
            for index, weight in enumerate(weights):
                if index == len(weights) - 1:
                    amount = remaining
                else:
                    amount = (closed_price * weight / weight_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    remaining -= amount
                allocated.append(amount)

            for row, amount in zip(kit_items, allocated):
                product = products[row.product_id]
                component = CartItemIn(
                    product_id=product.id,
                    quantity=item.quantity * row.quantity,
                    selected_size="Combo",
                    flavor_division=1,
                    flavors=[{"product_id": product.id, "name": product.name, "price": product.price, "icon": product.icon or ""}],
                    final_price=float(amount / row.quantity),
                    notes=f"Combo fechado: {kit.name} ({kit.id})",
                )
                expanded.append(component)
                metadata[id(component)] = ResolvedComboComponent(
                    item=component,
                    kit_id=kit.id,
                    kit_name=kit.name,
                    unit_price=float(amount / (item.quantity * row.quantity)),
                )
        return expanded, metadata

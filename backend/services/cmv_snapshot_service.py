from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from backend.models.cmv import OrderCmvSnapshot, OrderItemCmvIngredientSnapshot, OrderItemCmvSnapshot
from backend.models.gestao import GestaoModuleSettings
from backend.models.inventory import InventoryItem, InventoryRecipeItem, InventoryRecipeVersion, InventoryStockMovement
from backend.models.order import Order, OrderItem
from backend.models.product import Product
from backend.schemas.order import CartItemIn

TENANT_ID = "default"


@dataclass(frozen=True)
class CmvOrderItemContext:
    order_item: OrderItem
    cart_item: CartItemIn | None = None


@dataclass(frozen=True)
class _RecipeUse:
    recipe: InventoryRecipeVersion
    multiplier: float


class OrderCmvSnapshotService:
    """Persists frozen CMV for real sales without mutating stock."""

    def __init__(self, db: Session, tenant_id: str = TENANT_ID):
        self._db = db
        self._tenant_id = tenant_id

    def module_enabled(self) -> bool:
        settings = (
            self._db.query(GestaoModuleSettings)
            .filter(
                GestaoModuleSettings.tenant_id == self._tenant_id,
                GestaoModuleSettings.module_key == "cmv",
            )
            .first()
        )
        return bool(settings and settings.enabled and settings.status != "disabled")

    def create_for_order(self, order: Order, contexts: list[CmvOrderItemContext] | None = None) -> OrderCmvSnapshot | None:
        if not self.module_enabled():
            return None
        if self._db.query(OrderCmvSnapshot).filter(OrderCmvSnapshot.order_id == order.id).first():
            return None

        contexts = contexts or [CmvOrderItemContext(order_item=item) for item in (order.items or [])]
        contexts = [context for context in contexts if context.order_item]
        if not contexts:
            return None

        product_ids = self._product_ids(contexts)
        products = self._product_map(product_ids)
        recipes = self._recipe_map(product_ids)
        unit_costs = self._unit_cost_map()

        snapshot = OrderCmvSnapshot(
            id=str(uuid.uuid4()),
            tenant_id=self._tenant_id,
            order_id=order.id,
            source="order_created",
            status="complete",
            sale_total=0.0,
            cost_total=0.0,
            cmv_percent=None,
            missing_recipe=False,
            missing_cost=False,
        )
        self._db.add(snapshot)
        self._db.flush()

        sale_total = 0.0
        cost_total = 0.0
        missing_recipe = False
        missing_cost = False
        for context in contexts:
            item_snapshot, ingredients = self._build_item_snapshot(snapshot, context, products, recipes, unit_costs)
            sale_total += item_snapshot.sale_total
            cost_total += item_snapshot.cost_total
            missing_recipe = missing_recipe or item_snapshot.missing_recipe
            missing_cost = missing_cost or item_snapshot.missing_cost
            self._db.add(item_snapshot)
            self._db.flush()
            for ingredient in ingredients:
                ingredient.item_snapshot_id = item_snapshot.id
                self._db.add(ingredient)

        snapshot.sale_total = round(sale_total, 2)
        snapshot.cost_total = round(cost_total, 4)
        snapshot.cmv_percent = round((cost_total / sale_total) * 100, 2) if sale_total > 0 else None
        snapshot.missing_recipe = missing_recipe
        snapshot.missing_cost = missing_cost
        if missing_recipe:
            snapshot.status = "missing_recipe"
        elif missing_cost:
            snapshot.status = "missing_cost"
        return snapshot

    def _product_ids(self, contexts: list[CmvOrderItemContext]) -> list[str]:
        ids: list[str] = []
        for context in contexts:
            if context.order_item.product_id:
                ids.append(context.order_item.product_id)
            if context.cart_item:
                ids.extend(flavor.product_id for flavor in context.cart_item.flavors)
        return list(dict.fromkeys(ids))

    def _product_map(self, product_ids: list[str]) -> dict[str, Product]:
        if not product_ids:
            return {}
        products = self._db.query(Product).filter(Product.id.in_(product_ids)).all()
        return {product.id: product for product in products}

    def _recipe_map(self, product_ids: list[str]) -> dict[str, list[InventoryRecipeVersion]]:
        if not product_ids:
            return {}
        rows = (
            self._db.query(InventoryRecipeVersion)
            .options(
                joinedload(InventoryRecipeVersion.items)
                .joinedload(InventoryRecipeItem.inventory_item)
                .joinedload(InventoryItem.unit)
            )
            .filter(
                InventoryRecipeVersion.tenant_id == self._tenant_id,
                InventoryRecipeVersion.product_id.in_(product_ids),
                InventoryRecipeVersion.active == True,  # noqa: E712
            )
            .all()
        )
        grouped: dict[str, list[InventoryRecipeVersion]] = {}
        for row in rows:
            grouped.setdefault(row.product_id, []).append(row)
        return grouped

    def _unit_cost_map(self) -> dict[str, dict]:
        rows = (
            self._db.query(
                InventoryStockMovement.item_id,
                func.coalesce(func.sum(InventoryStockMovement.quantity_delta), 0.0).label("quantity"),
                func.coalesce(func.sum(InventoryStockMovement.quantity_delta * InventoryStockMovement.unit_cost), 0.0).label("cost"),
            )
            .filter(
                InventoryStockMovement.tenant_id == self._tenant_id,
                InventoryStockMovement.quantity_delta > 0,
                InventoryStockMovement.unit_cost > 0,
            )
            .group_by(InventoryStockMovement.item_id)
            .all()
        )
        result: dict[str, dict] = {}
        for item_id, quantity, cost in rows:
            quantity_float = float(quantity or 0.0)
            unit_cost = float(cost or 0.0) / quantity_float if quantity_float > 0 else 0.0
            result[item_id] = {"unit_cost": round(unit_cost, 6), "source": "weighted_average"}
        return result

    def _build_item_snapshot(
        self,
        snapshot: OrderCmvSnapshot,
        context: CmvOrderItemContext,
        products: dict[str, Product],
        recipes: dict[str, list[InventoryRecipeVersion]],
        unit_costs: dict[str, dict],
    ) -> tuple[OrderItemCmvSnapshot, list[OrderItemCmvIngredientSnapshot]]:
        order_item = context.order_item
        product = products.get(order_item.product_id)
        recipe_uses = self._recipe_uses(context, recipes)
        sale_total = float(order_item.total_price or 0.0)
        cost_total = 0.0
        missing_cost = False
        ingredients: list[OrderItemCmvIngredientSnapshot] = []

        for recipe_use in recipe_uses:
            for recipe_item in recipe_use.recipe.items:
                cost = unit_costs.get(recipe_item.inventory_item_id, {"unit_cost": 0.0, "source": "missing"})
                unit_cost = float(cost["unit_cost"] or 0.0)
                waste_multiplier = 1 + (float(recipe_item.waste_percent or 0.0) / 100)
                quantity = float(recipe_item.quantity or 0.0) * waste_multiplier * recipe_use.multiplier
                total_cost = quantity * unit_cost
                item_missing_cost = unit_cost <= 0
                missing_cost = missing_cost or item_missing_cost
                cost_total += total_cost
                inventory_item = recipe_item.inventory_item
                ingredients.append(OrderItemCmvIngredientSnapshot(
                    id=str(uuid.uuid4()),
                    tenant_id=self._tenant_id,
                    item_snapshot_id="",
                    inventory_item_id=recipe_item.inventory_item_id,
                    inventory_item_name=inventory_item.name if inventory_item else recipe_item.inventory_item_id,
                    unit_symbol=inventory_item.unit.symbol if inventory_item and inventory_item.unit else None,
                    quantity=round(quantity, 6),
                    unit_cost=round(unit_cost, 6),
                    total_cost=round(total_cost, 4),
                    cost_source=cost["source"],
                    missing_cost=item_missing_cost,
                ))

        missing_recipe = not recipe_uses
        cmv_percent = round((cost_total / sale_total) * 100, 2) if sale_total > 0 else None
        item_snapshot = OrderItemCmvSnapshot(
            id=str(uuid.uuid4()),
            tenant_id=self._tenant_id,
            snapshot_id=snapshot.id,
            order_item_id=order_item.id,
            product_id=order_item.product_id,
            product_name=product.name if product else order_item.product_id,
            quantity=float(order_item.quantity or 0.0),
            sale_total=round(sale_total, 2),
            cost_total=round(cost_total, 4),
            cmv_percent=cmv_percent,
            missing_recipe=missing_recipe,
            missing_cost=missing_cost,
            recipe_version_ids=json.dumps([recipe_use.recipe.id for recipe_use in recipe_uses]),
        )
        return item_snapshot, ingredients

    def _recipe_uses(
        self,
        context: CmvOrderItemContext,
        recipes: dict[str, list[InventoryRecipeVersion]],
    ) -> list[_RecipeUse]:
        order_item = context.order_item
        cart_item = context.cart_item
        quantity = float(order_item.quantity or 0.0)
        uses = [
            _RecipeUse(recipe=recipe, multiplier=quantity)
            for recipe in self._matching_recipes(
                recipes.get(order_item.product_id, []),
                order_item.selected_size_id,
                order_item.selected_crust_type_id,
                cart_item.selected_drink_variant_id if cart_item else None,
            )
        ]
        if cart_item:
            flavor_multiplier = quantity / max(1, int(cart_item.flavor_division or 1))
            for flavor in cart_item.flavors:
                if flavor.product_id == order_item.product_id:
                    continue
                uses.extend(
                    _RecipeUse(recipe=recipe, multiplier=flavor_multiplier)
                    for recipe in self._matching_recipes(recipes.get(flavor.product_id, []), None, None, None)
                )
        return uses

    def _matching_recipes(
        self,
        recipes: list[InventoryRecipeVersion],
        size_id: str | None,
        crust_id: str | None,
        drink_variant_id: str | None,
    ) -> list[InventoryRecipeVersion]:
        matches = []
        for recipe in recipes:
            is_base = not recipe.product_size_id and not recipe.product_crust_type_id and not recipe.product_drink_variant_id and not recipe.complement_key
            is_selected_size = bool(size_id and recipe.product_size_id == size_id)
            is_selected_crust = bool(crust_id and recipe.product_crust_type_id == crust_id)
            is_selected_drink = bool(drink_variant_id and recipe.product_drink_variant_id == drink_variant_id)
            if is_base or is_selected_size or is_selected_crust or is_selected_drink:
                matches.append(recipe)
        return matches

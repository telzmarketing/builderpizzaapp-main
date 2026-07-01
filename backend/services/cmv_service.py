from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from backend.models.cmv import OrderCmvSnapshot
from backend.models.gestao import GestaoModuleSettings
from backend.models.inventory import InventoryItem, InventoryRecipeItem, InventoryRecipeVersion, InventoryStockMovement
from backend.models.order import Order, OrderStatus
from backend.models.product import Product

TENANT_ID = "default"


class CmvService:
    def __init__(self, db: Session, tenant_id: str = TENANT_ID):
        self._db = db
        self._tenant_id = tenant_id

    def overview(self) -> dict:
        settings = self._settings()
        module_enabled = bool(settings and settings.enabled and settings.status != "disabled")
        products = (
            self._db.query(Product)
            .filter(Product.active == True)  # noqa: E712
            .filter((Product.product_type == None) | (Product.product_type != "brinde"))  # noqa: E711
            .order_by(Product.name)
            .all()
        )
        recipe_map = self._recipe_map([product.id for product in products])
        unit_costs = self._unit_cost_map()
        rows = [self._product_cost(product, recipe_map.get(product.id, []), unit_costs) for product in products]

        products_with_recipe = sum(1 for row in rows if row["has_recipe"])
        missing_recipe = len(rows) - products_with_recipe
        missing_cost = sum(1 for row in rows if row["missing_cost"])
        cmv_values = [
            row["cmv_percent_max"]
            for row in rows
            if row["cmv_percent_max"] is not None and row["has_recipe"] and not row["missing_cost"]
        ]
        snapshot_summary = self._snapshot_summary()
        dre_status, dre_label = self._dre_status(
            module_enabled,
            missing_recipe,
            missing_cost,
            snapshot_summary["count"],
            snapshot_summary["pending_count"],
        )
        return {
            "module_enabled": module_enabled,
            "module_status": settings.status if settings else "disabled",
            "dre_status": dre_status,
            "dre_label": dre_label,
            "operational_snapshot_count": snapshot_summary["count"],
            "operational_sale_total": snapshot_summary["sale_total"],
            "operational_cost_total": snapshot_summary["cost_total"],
            "operational_cmv_percent": snapshot_summary["cmv_percent"],
            "operational_pending_count": snapshot_summary["pending_count"],
            "products_total": len(rows),
            "products_with_recipe": products_with_recipe,
            "products_missing_recipe": missing_recipe,
            "products_missing_cost": missing_cost,
            "average_cmv_percent": round(sum(cmv_values) / len(cmv_values), 2) if cmv_values else None,
            "products": rows,
        }

    def _settings(self) -> GestaoModuleSettings | None:
        return (
            self._db.query(GestaoModuleSettings)
            .filter(GestaoModuleSettings.tenant_id == self._tenant_id, GestaoModuleSettings.module_key == "cmv")
            .first()
        )

    def _recipe_map(self, product_ids: list[str]) -> dict[str, list[InventoryRecipeVersion]]:
        if not product_ids:
            return {}
        rows = (
            self._db.query(InventoryRecipeVersion)
            .options(
                joinedload(InventoryRecipeVersion.product_size),
                joinedload(InventoryRecipeVersion.product_crust_type),
                joinedload(InventoryRecipeVersion.product_drink_variant),
                joinedload(InventoryRecipeVersion.items).joinedload(InventoryRecipeItem.inventory_item).joinedload(InventoryItem.unit),
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
            result[item_id] = {
                "unit_cost": round(unit_cost, 6),
                "source": "weighted_average",
            }
        return result

    def _snapshot_summary(self) -> dict:
        effective_statuses = [
            OrderStatus.paid,
            OrderStatus.pago,
            OrderStatus.preparing,
            OrderStatus.ready_for_pickup,
            OrderStatus.on_the_way,
            OrderStatus.delivered,
        ]
        rows = (
            self._db.query(OrderCmvSnapshot)
            .join(Order, Order.id == OrderCmvSnapshot.order_id)
            .filter(OrderCmvSnapshot.tenant_id == self._tenant_id)
            .filter(Order.status.in_(effective_statuses))
            .all()
        )
        sale_total = sum(float(row.sale_total or 0.0) for row in rows)
        cost_total = sum(float(row.cost_total or 0.0) for row in rows)
        pending_count = sum(1 for row in rows if row.missing_recipe or row.missing_cost)
        return {
            "count": len(rows),
            "sale_total": round(sale_total, 2),
            "cost_total": round(cost_total, 4),
            "cmv_percent": round((cost_total / sale_total) * 100, 2) if sale_total > 0 else None,
            "pending_count": pending_count,
        }

    def _product_cost(self, product: Product, recipes: list[InventoryRecipeVersion], unit_costs: dict[str, dict]) -> dict:
        recipe_rows = [self._recipe_cost(recipe, unit_costs) for recipe in recipes]
        base_rows = [row for row in recipe_rows if row["scope_label"] == "Produto base"]
        scoped_rows = [row for row in recipe_rows if row["scope_label"] != "Produto base"]
        base_cost = sum(row["cost_total"] for row in base_rows)
        if scoped_rows:
            cost_min = base_cost + min(row["cost_total"] for row in scoped_rows)
            cost_max = base_cost + max(row["cost_total"] for row in scoped_rows)
        else:
            cost_min = base_cost
            cost_max = base_cost
        sale_price = float(product.price or 0.0)
        missing_cost = any(row["missing_cost"] for row in recipe_rows)
        has_recipe = bool(recipe_rows)
        status = "ok"
        if not has_recipe:
            status = "missing_recipe"
        elif missing_cost:
            status = "missing_cost"
        return {
            "product_id": product.id,
            "product_name": product.name,
            "product_type": product.product_type,
            "sale_price": round(sale_price, 2),
            "recipe_count": len(recipe_rows),
            "has_recipe": has_recipe,
            "missing_cost": missing_cost,
            "cost_min": round(cost_min, 4),
            "cost_max": round(cost_max, 4),
            "cmv_percent_min": round((cost_min / sale_price) * 100, 2) if sale_price > 0 and has_recipe else None,
            "cmv_percent_max": round((cost_max / sale_price) * 100, 2) if sale_price > 0 and has_recipe else None,
            "margin_min": round(sale_price - cost_max, 4),
            "margin_max": round(sale_price - cost_min, 4),
            "status": status,
            "recipes": recipe_rows,
        }

    def _recipe_cost(self, recipe: InventoryRecipeVersion, unit_costs: dict[str, dict]) -> dict:
        ingredients = []
        cost_total = 0.0
        missing_cost = False
        for item in recipe.items:
            cost = unit_costs.get(item.inventory_item_id, {"unit_cost": 0.0, "source": "missing"})
            unit_cost = float(cost["unit_cost"] or 0.0)
            waste_multiplier = 1 + (float(item.waste_percent or 0.0) / 100)
            total = float(item.quantity or 0.0) * waste_multiplier * unit_cost
            item_missing = unit_cost <= 0
            missing_cost = missing_cost or item_missing
            cost_total += total
            inventory_item = item.inventory_item
            ingredients.append({
                "inventory_item_id": item.inventory_item_id,
                "inventory_item_name": inventory_item.name if inventory_item else None,
                "unit_symbol": inventory_item.unit.symbol if inventory_item and inventory_item.unit else None,
                "quantity": item.quantity,
                "waste_percent": item.waste_percent,
                "unit_cost": round(unit_cost, 6),
                "total_cost": round(total, 4),
                "cost_source": cost["source"],
                "missing_cost": item_missing,
            })
        return {
            "recipe_id": recipe.id,
            "version_number": recipe.version_number,
            "scope_label": self._scope_label(recipe),
            "product_size_id": recipe.product_size_id,
            "product_crust_type_id": recipe.product_crust_type_id,
            "product_drink_variant_id": recipe.product_drink_variant_id,
            "complement_key": recipe.complement_key,
            "cost_total": round(cost_total, 4),
            "missing_cost": missing_cost,
            "ingredients": ingredients,
        }

    def _scope_label(self, recipe: InventoryRecipeVersion) -> str:
        labels = [
            recipe.product_size.label if recipe.product_size else None,
            recipe.product_crust_type.name if recipe.product_crust_type else None,
            recipe.product_drink_variant.name if recipe.product_drink_variant else None,
            recipe.complement_name,
        ]
        text = " / ".join(label for label in labels if label)
        return text or "Produto base"

    def _dre_status(
        self,
        module_enabled: bool,
        missing_recipe: int,
        missing_cost: int,
        snapshot_count: int,
        snapshot_pending_count: int,
    ) -> tuple[str, str]:
        if not module_enabled:
            return "partial_without_cmv", "DRE parcial sem CMV"
        if snapshot_count and snapshot_pending_count == 0:
            return "complete_with_operational_cmv", "DRE completa com CMV operacional"
        if snapshot_count:
            return "partial_with_operational_cmv_pending", "DRE parcial com CMV operacional pendente"
        if missing_recipe or missing_cost:
            return "partial_with_pending_cmv", "DRE parcial com CMV pendente"
        return "partial_operational_waiting_sales", "DRE aguardando vendas com CMV"

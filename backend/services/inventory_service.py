from __future__ import annotations

import json
import uuid
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from backend.core.exceptions import DomainError
from backend.core.events import InventoryPurchaseConfirmed, bus
from backend.core.tenant_context import TenantContext
from backend.core.wave7_tenant_orm import wave7_orm_enabled
from backend.models.cmv import OrderCmvSnapshot, OrderItemCmvSnapshot
from backend.models.gestao import GestaoModuleSettings
from backend.models.inventory import (
    InventoryCategory,
    InventoryItem,
    InventoryLocation,
    InventoryManualEntry,
    InventoryPurchase,
    InventoryPurchaseItem,
    InventoryRecipeItem,
    InventoryRecipeVersion,
    InventoryStockMovement,
    InventorySupplier,
    InventoryUnit,
)
from backend.models.order import Order, OrderItem
from backend.models.product import Product, ProductCrustType, ProductDrinkVariant, ProductSize
from backend.schemas.inventory import (
    InventoryCategoryIn,
    InventoryItemIn,
    InventoryLocationIn,
    InventoryManualEntryIn,
    InventoryPurchaseIn,
    InventoryRecipeVersionIn,
    InventorySupplierIn,
    InventoryUnitIn,
)
from backend.services.recipe_resolution import resolve_recipes, required_ingredients, required_decimal_ingredients

TENANT_ID = "default"
ZERO = Decimal("0")
QUANTITY_SCALE = Decimal("0.000001")


def decimal_value(value) -> Decimal:
    return Decimal(str(value)) if value is not None else ZERO


def required_decimal(resolution) -> dict[str, Decimal]:
    """One selected/customized composition, rounded only after consolidation."""
    return {key: value.quantize(QUANTITY_SCALE, rounding=ROUND_HALF_UP)
            for key, value in required_decimal_ingredients(resolution).items()}



class InventoryNotFound(DomainError):
    http_status = 404

    def __init__(self, entity: str):
        super().__init__(f"{entity} nao encontrado.", code="InventoryNotFound")


class InventoryInvalidReference(DomainError):
    def __init__(self, message: str):
        super().__init__(message, code="InventoryInvalidReference")


class InventoryUnavailable(DomainError):
    http_status = 409

    def __init__(self, product_name: str | None = None):
        message = "Indisponivel no momento."
        if product_name:
            message = f"{product_name} esta indisponivel no momento."
        super().__init__(message, code="InventoryUnavailable")


class InventoryService:
    def __init__(
        self,
        db: Session,
        tenant_id: str = TENANT_ID,
        tenant_context: TenantContext | None = None,
        actor_id: str | None = None,
    ):
        self._actor_id = actor_id or "system:legacy-order"
        self._db = db
        self._tenant_context = tenant_context
        self._tenant_id = self._resolve_tenant_id(tenant_id, tenant_context)

    @staticmethod
    def _resolve_tenant_id(tenant_id: str | None, context: TenantContext | None) -> str:
        """Keep the legacy default until Wave 7 is deliberately enabled.

        Once enabled, a raw tenant id is not a proof of ownership.  Every
        inventory read or write must originate from a verified HTTP/job context.
        """
        if not wave7_orm_enabled():
            return tenant_id or TENANT_ID
        if context is None:
            from backend.core.tenant_context import TenantContextMissing

            raise TenantContextMissing("Contexto confiavel obrigatorio para estoque da Wave 7.")
        if tenant_id not in {None, TENANT_ID, context.tenant_id}:
            context.assert_tenant(tenant_id)
        return context.tenant_id

    def overview(self) -> dict:
        return {
            "units": self.list_units(),
            "categories": self.list_categories(),
            "locations": self.list_locations(),
            "suppliers": self.list_suppliers(),
            "items": self.list_items(),
            "purchases": self.list_purchases(),
            "manual_entries": self.list_manual_entries(),
            "movements": self.list_movements(),
            "balances": self.list_balances(),
        }

    def list_units(self) -> list[InventoryUnit]:
        return self._list(InventoryUnit)

    def create_unit(self, payload: InventoryUnitIn) -> InventoryUnit:
        return self._create(InventoryUnit, payload.model_dump(), "unit")

    def update_unit(self, item_id: str, payload: InventoryUnitIn) -> InventoryUnit:
        row = self._get(InventoryUnit, item_id, "Unidade")
        if row.dimension is not None and (row.symbol != payload.symbol or row.unit_type != payload.unit_type):
            raise InventoryInvalidReference("Unidade classificada deve ser revisada pelo cadastro de conversoes.")
        return self._update(self._get(InventoryUnit, item_id, "Unidade"), payload.model_dump())

    def delete_unit(self, item_id: str) -> None:
        self._deactivate(self._get(InventoryUnit, item_id, "Unidade"))

    def list_categories(self) -> list[InventoryCategory]:
        return self._list(InventoryCategory)

    def create_category(self, payload: InventoryCategoryIn) -> InventoryCategory:
        return self._create(InventoryCategory, payload.model_dump(), "cat")

    def update_category(self, item_id: str, payload: InventoryCategoryIn) -> InventoryCategory:
        return self._update(self._get(InventoryCategory, item_id, "Categoria"), payload.model_dump())

    def delete_category(self, item_id: str) -> None:
        self._deactivate(self._get(InventoryCategory, item_id, "Categoria"))

    def list_locations(self) -> list[InventoryLocation]:
        return self._list(InventoryLocation)

    def create_location(self, payload: InventoryLocationIn) -> InventoryLocation:
        return self._create(InventoryLocation, payload.model_dump(), "loc")

    def update_location(self, item_id: str, payload: InventoryLocationIn) -> InventoryLocation:
        return self._update(self._get(InventoryLocation, item_id, "Local"), payload.model_dump())

    def delete_location(self, item_id: str) -> None:
        self._deactivate(self._get(InventoryLocation, item_id, "Local"))

    def list_suppliers(self) -> list[InventorySupplier]:
        return self._list(InventorySupplier)

    def create_supplier(self, payload: InventorySupplierIn) -> InventorySupplier:
        return self._create(InventorySupplier, payload.model_dump(), "sup")

    def update_supplier(self, item_id: str, payload: InventorySupplierIn) -> InventorySupplier:
        return self._update(self._get(InventorySupplier, item_id, "Fornecedor"), payload.model_dump())

    def delete_supplier(self, item_id: str) -> None:
        self._deactivate(self._get(InventorySupplier, item_id, "Fornecedor"))

    def list_items(self) -> list[dict]:
        rows = (
            self._db.query(InventoryItem)
            .options(
                joinedload(InventoryItem.category),
                joinedload(InventoryItem.unit),
                joinedload(InventoryItem.default_location),
            )
            .filter(InventoryItem.tenant_id == self._tenant_id)
            .filter(InventoryItem.active == True)  # noqa: E712
            .order_by(InventoryItem.name)
            .all()
        )
        balances = self._stock_balance_map()
        return [self._serialize_item(row, balances) for row in rows]

    def create_item(self, payload: InventoryItemIn) -> dict:
        data = payload.model_dump()
        self._validate_item_refs(data)
        row = self._create(InventoryItem, data, "item", commit=False)
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_item(row)

    def update_item(self, item_id: str, payload: InventoryItemIn) -> dict:
        data = payload.model_dump()
        self._validate_item_refs(data)
        row = self._db.query(InventoryItem).filter(InventoryItem.tenant_id == self._tenant_id, InventoryItem.id == item_id).populate_existing().with_for_update().first()
        if row is None:
            raise InventoryNotFound("Item")
        if row.unit_id != data.get("unit_id"):
            has_history = self._db.query(InventoryStockMovement.id).filter(InventoryStockMovement.tenant_id == self._tenant_id, InventoryStockMovement.item_id == row.id).first()
            from backend.models.inventory_foundation import InventoryItemPackaging, InventoryLot, InventoryReservation
            has_foundation = any(self._db.query(model.id).filter(model.tenant_id == self._tenant_id, model.item_id == row.id).first() is not None for model in (InventoryItemPackaging, InventoryLot, InventoryReservation))
            if has_history or has_foundation:
                raise InventoryInvalidReference("Unidade de insumo movimentado/configurado exige conversao e reconciliacao explicitas.")
        for key, value in data.items():
            setattr(row, key, value)
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_item(row)

    def delete_item(self, item_id: str) -> None:
        self._deactivate(self._get(InventoryItem, item_id, "Item"))

    def list_purchases(self) -> list[dict]:
        rows = (
            self._db.query(InventoryPurchase)
            .options(joinedload(InventoryPurchase.supplier), joinedload(InventoryPurchase.items).joinedload(InventoryPurchaseItem.item))
            .filter(InventoryPurchase.tenant_id == self._tenant_id)
            .order_by(InventoryPurchase.created_at.desc())
            .all()
        )
        return [self._serialize_purchase(row) for row in rows]

    def create_purchase(self, payload: InventoryPurchaseIn) -> dict:
        data = payload.model_dump()
        items = data.pop("items", [])
        if data.get("supplier_id"):
            self._ensure(InventorySupplier, data["supplier_id"], "Fornecedor")
        purchase = InventoryPurchase(
            id=f"inv-pur-{uuid.uuid4().hex[:12]}",
            tenant_id=self._tenant_id,
            **data,
        )
        self._db.add(purchase)
        self._replace_purchase_items(purchase, items)
        self._db.commit()
        self._db.refresh(purchase)
        if purchase.status == "confirmed":
            self._publish_purchase_confirmed(purchase)
        return self._serialize_purchase(purchase)

    def update_purchase(self, purchase_id: str, payload: InventoryPurchaseIn) -> dict:
        purchase = self._get_purchase(purchase_id)
        previous_status = purchase.status
        if previous_status == "confirmed":
            raise InventoryInvalidReference("Compra confirmada nao pode ser alterada.")
        data = payload.model_dump()
        items = data.pop("items", [])
        if data.get("supplier_id"):
            self._ensure(InventorySupplier, data["supplier_id"], "Fornecedor")
        for key, value in data.items():
            setattr(purchase, key, value)
        self._db.query(InventoryPurchaseItem).filter(InventoryPurchaseItem.purchase_id == purchase.id).delete(synchronize_session=False)
        self._replace_purchase_items(purchase, items)
        self._db.commit()
        self._db.refresh(purchase)
        if previous_status != "confirmed" and purchase.status == "confirmed":
            self._publish_purchase_confirmed(purchase)
        return self._serialize_purchase(purchase)

    def delete_purchase(self, purchase_id: str) -> None:
        purchase = self._get_purchase(purchase_id)
        if purchase.status == "confirmed":
            raise InventoryInvalidReference("Compra confirmada nao pode ser removida.")
        self._delete(purchase)

    def _publish_purchase_confirmed(self, purchase: InventoryPurchase) -> None:
        try:
            bus.publish(InventoryPurchaseConfirmed(
                purchase_id=purchase.id,
                supplier_id=purchase.supplier_id,
                total_amount=float(purchase.total_amount or 0.0),
                invoice_number=purchase.invoice_number,
                expected_date=purchase.expected_date,
                tenant_id=purchase.tenant_id,
            ))
        except Exception:
            pass

    def list_manual_entries(self) -> list[dict]:
        rows = (
            self._db.query(InventoryManualEntry)
            .options(joinedload(InventoryManualEntry.item), joinedload(InventoryManualEntry.location))
            .filter(InventoryManualEntry.tenant_id == self._tenant_id)
            .order_by(InventoryManualEntry.created_at.desc())
            .all()
        )
        return [self._serialize_manual_entry(row) for row in rows]

    def create_manual_entry(self, payload: InventoryManualEntryIn) -> dict:
        data = payload.model_dump()
        self._ensure(InventoryItem, data["item_id"], "Item")
        self._db.query(InventoryItem).filter(InventoryItem.tenant_id == self._tenant_id, InventoryItem.id == data["item_id"]).with_for_update().one()
        from backend.services.inventory_foundation_service import InventoryFoundationService
        foundation = InventoryFoundationService(self._db, self._tenant_id, self._actor_id, self._tenant_context)
        if data["movement_type"] == "out":
            foundation.validate_legacy_out(data["item_id"], data.get("location_id"), decimal_value(data["quantity"]))
        if data.get("location_id"):
            self._ensure(InventoryLocation, data["location_id"], "Local")
        row = InventoryManualEntry(
            id=f"inv-ent-{uuid.uuid4().hex[:12]}",
            tenant_id=self._tenant_id,
            **data,
        )
        self._db.add(row)
        self._db.flush()
        self._create_stock_movement_from_manual_entry(row)
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_manual_entry(row)

    def delete_manual_entry(self, entry_id: str) -> None:
        row = self._get(InventoryManualEntry, entry_id, "Entrada manual")
        self._db.query(InventoryItem).filter(InventoryItem.tenant_id == self._tenant_id, InventoryItem.id == row.item_id).with_for_update().one()
        existing = self._db.query(InventoryStockMovement.id).filter(
            InventoryStockMovement.tenant_id == self._tenant_id,
            InventoryStockMovement.source_type == "manual_entry_reversal",
            InventoryStockMovement.source_id == row.id,
        ).first()
        if existing:
            return
        original = self._db.query(InventoryStockMovement).filter(
            InventoryStockMovement.tenant_id == self._tenant_id,
            InventoryStockMovement.source_type == "manual_entry",
            InventoryStockMovement.source_id == row.id,
        ).all()
        from backend.services.inventory_foundation_service import InventoryFoundationService
        foundation = InventoryFoundationService(self._db, self._tenant_id, self._actor_id, self._tenant_context)
        for movement in original:
            if movement.operation_id or movement.lot_id:
                raise InventoryInvalidReference("Movimento rastreado exige compensacao pela operacao de origem.")
            delta = -decimal_value(movement.quantity_delta)
            if delta < 0:
                foundation.validate_legacy_out(row.item_id, row.location_id, -delta)
            self._db.add(InventoryStockMovement(
                id=f"inv-rev-{uuid.uuid4().hex[:12]}", tenant_id=self._tenant_id,
                item_id=row.item_id, location_id=row.location_id,
                source_type="manual_entry_reversal", source_id=row.id,
                movement_type="in" if delta > 0 else "out", quantity_delta=delta,
                unit_cost=movement.unit_cost, reason="manual_entry_reversal",
                notes=json.dumps({"actor_id":self._actor_id,"compensated_entry_id":row.id,"reason":"manual_entry_reversal"}),
            ))
        self._db.commit()

    def list_movements(self) -> list[dict]:
        rows = (
            self._db.query(InventoryStockMovement)
            .options(joinedload(InventoryStockMovement.item).joinedload(InventoryItem.unit), joinedload(InventoryStockMovement.location))
            .filter(InventoryStockMovement.tenant_id == self._tenant_id)
            .order_by(InventoryStockMovement.created_at.desc())
            .limit(200)
            .all()
        )
        return [self._serialize_movement(row) for row in rows]

    def list_balances(self) -> list[dict]:
        balances = self._stock_balance_map()
        items = (
            self._db.query(InventoryItem)
            .options(joinedload(InventoryItem.unit))
            .filter(InventoryItem.tenant_id == self._tenant_id)
            .filter(InventoryItem.active == True)  # noqa: E712
            .order_by(InventoryItem.name)
            .all()
        )
        return [
            {
                "item_id": item.id,
                "item_name": item.name,
                "unit_symbol": item.unit.symbol if item.unit else None,
                "current_stock": round(balances.get(item.id, 0.0), 6),
                "min_stock": item.min_stock,
                "below_min_stock": balances.get(item.id, 0.0) <= item.min_stock,
                "active": item.active,
            }
            for item in items
        ]

    def automatic_deduction_enabled(self) -> bool:
        settings = self._module_settings()
        if not settings:
            return False
        return bool(settings.get("sales_control_enabled")) and bool(settings.get("auto_consume_on_preparing"))

    def consume_order_sale(self, order_id: str) -> dict:
        if not self.automatic_deduction_enabled():
            return {"deducted": False, "reason": "disabled", "movements": 0}
        # Serialize retries and concurrent starts for the same tenant order.
        order = self._db.query(Order).filter(Order.id == order_id, Order.tenant_id == self._tenant_id).with_for_update().first()
        if not order:
            raise InventoryInvalidReference("Pedido nao encontrado para baixa de estoque.")
        status = getattr(order.status, "value", order.status)
        if status != "preparing":
            return {"deducted": False, "reason": "not_preparing", "movements": 0}
        # Persistent physical units choose the unit writer. Never charge the same
        # commercial order again when its stock gate/tentative writer is active.
        from backend.models.kds_production import ProductionUnit
        if self._db.query(ProductionUnit.id).filter_by(
            tenant_id=self._tenant_id, order_id=order_id,
        ).first():
            return {"deducted": False, "reason": "kds_units", "movements": 0}
        existing = (
            self._db.query(InventoryStockMovement.id)
            .filter(
                InventoryStockMovement.tenant_id == self._tenant_id,
                InventoryStockMovement.source_type.in_(["order_sale", "foundation_order_sale"]),
                InventoryStockMovement.source_id == order_id,
            )
            .first()
        )
        if existing:
            return {"deducted": False, "reason": "already_deducted", "movements": 0}

        order = (
            self._db.query(Order)
            .options(
                joinedload(Order.items)
                .joinedload(OrderItem.flavors),
            )
            .filter(Order.id == order_id, Order.tenant_id == self._tenant_id)
            .first()
        )
        if not order:
            raise InventoryInvalidReference("Pedido nao encontrado para baixa de estoque.")

        snapshot = self._db.query(OrderCmvSnapshot).filter(OrderCmvSnapshot.order_id == order.id, OrderCmvSnapshot.tenant_id == self._tenant_id).first()
        required = self._required_items_from_cmv_snapshot(order.id) if snapshot else self._required_items_for_order(order)
        if snapshot and snapshot.missing_recipe and required:
            raise InventoryInvalidReference("Ficha tecnica incompleta para a composicao do pedido.")
        if not required:
            return {"deducted": False, "reason": "no_recipe", "movements": 0}

        unit_costs = self._average_unit_cost_map()
        inventory_items = {
            item.id: item
            for item in self._db.query(InventoryItem).filter(InventoryItem.tenant_id == self._tenant_id, InventoryItem.id.in_(required.keys())).order_by(InventoryItem.id).with_for_update().all()
        }
        balances = self._stock_balance_map()
        if any(quantity > balances.get(item_id, ZERO) for item_id, quantity in required.items()):
            raise InventoryUnavailable()
        from backend.services.inventory_foundation_service import InventoryFoundationService
        handled = InventoryFoundationService(self._db, self._tenant_id, self._actor_id, self._tenant_context).consume_legacy_sale(order.id, required, unit_costs)
        movements = len(handled)
        for item_id, quantity in required.items():
            if item_id in handled:
                continue
            if quantity <= 0:
                continue
            inventory_item = inventory_items.get(item_id)
            self._db.add(InventoryStockMovement(
                id=f"inv-mov-{uuid.uuid4().hex[:12]}",
                tenant_id=self._tenant_id,
                item_id=item_id,
                location_id=inventory_item.default_location_id if inventory_item else None,
                source_type="order_sale",
                source_id=order.id,
                movement_type="out",
                quantity_delta=round(-abs(quantity), 6),
                unit_cost=unit_costs.get(item_id, 0.0),
                reason="order_sale",
                notes=f"Baixa automatica do pedido {order.order_code or order.id}",
            ))
            movements += 1
        self._db.flush()
        return {"deducted": movements > 0, "reason": "ok", "movements": movements}

    def reverse_order_sale(self, order_id: str) -> dict:
        order = self._db.query(Order).filter(Order.id == order_id, Order.tenant_id == self._tenant_id).with_for_update().first()
        if not order:
            raise InventoryInvalidReference("Pedido nao encontrado para registrar cancelamento.")
        from backend.services.inventory_foundation_service import InventoryFoundationService
        InventoryFoundationService(self._db, self._tenant_id, self._actor_id, self._tenant_context).release_order_reservations(order_id)
        sale_movements = (
            self._db.query(InventoryStockMovement)
            .filter(
                InventoryStockMovement.tenant_id == self._tenant_id,
                InventoryStockMovement.source_type.in_(["order_sale", "foundation_order_sale"]),
                InventoryStockMovement.source_id == order_id,
                InventoryStockMovement.quantity_delta < 0,
            )
            .all()
        )
        if not sale_movements:
            return {"reversed": False, "reason": "no_sale_movements", "movements": 0}

        # Production already consumed the ingredients. Cancellation records
        # an audit event with zero delta, never an automatic stock return.
        if order.preparation_started_at or any(m.source_type == "foundation_order_sale" for m in sale_movements):
            existing = self._db.query(InventoryStockMovement.id).filter(
                InventoryStockMovement.tenant_id == self._tenant_id,
                InventoryStockMovement.source_type == "order_sale_loss",
                InventoryStockMovement.source_id == order_id,
            ).first()
            if existing:
                return {"reversed": False, "reason": "loss_already_recorded", "movements": 0}
            losses = {}
            for movement in sale_movements:
                losses.setdefault(movement.item_id, []).append(movement)
            for item_id, rows in losses.items():
                movement = rows[0]
                self._db.add(InventoryStockMovement(
                    id=f"inv-loss-{uuid.uuid4().hex[:12]}", tenant_id=self._tenant_id,
                    item_id=movement.item_id, location_id=movement.location_id,
                    source_type="order_sale_loss", source_id=order_id, movement_type="out",
                    quantity_delta=0.0, unit_cost=movement.unit_cost, reason="production_loss",
                    notes=json.dumps({"order_id": order_id, "consumed_quantity": float(sum((-decimal_value(row.quantity_delta) for row in rows), ZERO)), "consumed_quantity_decimal": str(sum((-decimal_value(row.quantity_delta) for row in rows), ZERO)), "consumption_movement_id": movement.id, "consumption_movement_ids": [row.id for row in rows]}),
                ))
            self._db.flush()
            return {"reversed": False, "reason": "production_loss_recorded", "movements": len(losses)}

        existing_reversal = (
            self._db.query(InventoryStockMovement.id)
            .filter(
                InventoryStockMovement.tenant_id == self._tenant_id,
                InventoryStockMovement.source_type == "order_sale_reversal",
                InventoryStockMovement.source_id == order_id,
            )
            .first()
        )
        if existing_reversal:
            return {"reversed": False, "reason": "already_reversed", "movements": 0}

        movements = 0
        for movement in sale_movements:
            self._db.add(InventoryStockMovement(
                id=f"inv-mov-{uuid.uuid4().hex[:12]}",
                tenant_id=self._tenant_id,
                item_id=movement.item_id,
                location_id=movement.location_id,
                source_type="order_sale_reversal",
                source_id=order_id,
                movement_type="in",
                quantity_delta=round(abs(decimal_value(movement.quantity_delta)), 6),
                unit_cost=movement.unit_cost,
                reason="order_sale_reversal",
                notes=f"Estorno automatico da baixa do pedido {order_id}",
            ))
            movements += 1
        return {"reversed": movements > 0, "reason": "ok", "movements": movements}

    def list_product_recipes(self, product_id: str) -> list[dict]:
        self._ensure_product(product_id)
        rows = (
            self._db.query(InventoryRecipeVersion)
            .options(
                joinedload(InventoryRecipeVersion.product),
                joinedload(InventoryRecipeVersion.product_size),
                joinedload(InventoryRecipeVersion.product_crust_type),
                joinedload(InventoryRecipeVersion.product_drink_variant),
                joinedload(InventoryRecipeVersion.items).joinedload(InventoryRecipeItem.inventory_item).joinedload(InventoryItem.unit),
            )
            .filter(
                InventoryRecipeVersion.tenant_id == self._tenant_id,
                InventoryRecipeVersion.product_id == product_id,
            )
            .order_by(InventoryRecipeVersion.active.desc(), InventoryRecipeVersion.version_number.desc())
            .all()
        )
        return [self._serialize_recipe(row) for row in rows]

    def create_product_recipe(self, product_id: str, payload: InventoryRecipeVersionIn) -> dict:
        self._db.query(Product).filter(Product.id == product_id, Product.tenant_id == self._tenant_id).with_for_update().first()
        data = payload.model_dump()
        items = data.pop("items", [])
        self._validate_recipe_refs(product_id, data, items)
        current_version = (
            self._db.query(InventoryRecipeVersion.version_number)
            .filter(
                InventoryRecipeVersion.tenant_id == self._tenant_id,
                InventoryRecipeVersion.product_id == product_id,
            )
            .order_by(InventoryRecipeVersion.version_number.desc())
            .first()
        )
        version_number = int(current_version[0]) + 1 if current_version else 1
        recipe = InventoryRecipeVersion(
            id=f"inv-rec-{uuid.uuid4().hex[:12]}",
            tenant_id=self._tenant_id,
            product_id=product_id,
            version_number=version_number,
            **data,
        )
        if recipe.active:
            self._deactivate_matching_recipe_scope(product_id, data)
        self._db.add(recipe)
        self._replace_recipe_items(recipe, items)
        self._db.commit()
        self._db.refresh(recipe)
        return self._serialize_recipe(recipe)

    def update_product_recipe(self, product_id: str, recipe_id: str, payload: InventoryRecipeVersionIn) -> dict:
        recipe = self._get_recipe(product_id, recipe_id)
        # A published version and its items remain immutable for old snapshots.
        self._validate_recipe_refs(product_id, payload.model_dump(exclude={"items"}), [i.model_dump() for i in payload.items])
        recipe.active = False
        return self.create_product_recipe(product_id, payload)

    def delete_product_recipe(self, product_id: str, recipe_id: str) -> None:
        recipe = self._get_recipe(product_id, recipe_id)
        recipe.active = False
        self._db.commit()

    def _list(self, model):
        return (
            self._db.query(model)
            .filter(model.tenant_id == self._tenant_id)
            .filter(model.active == True)  # noqa: E712
            .order_by(model.name)
            .all()
        )

    def _create(self, model, data: dict, prefix: str, *, commit: bool = True):
        row = model(id=f"inv-{prefix}-{uuid.uuid4().hex[:12]}", tenant_id=self._tenant_id, **data)
        self._db.add(row)
        if commit:
            self._db.commit()
            self._db.refresh(row)
        return row

    def _update(self, row, data: dict):
        for key, value in data.items():
            setattr(row, key, value)
        self._db.commit()
        self._db.refresh(row)
        return row

    def _delete(self, row) -> None:
        self._db.delete(row)
        self._db.commit()

    def _deactivate(self, row) -> None:
        row.active = False
        self._db.commit()

    def _get(self, model, row_id: str, label: str):
        row = (
            self._db.query(model)
            .filter(model.id == row_id, model.tenant_id == self._tenant_id)
            .first()
        )
        if not row:
            raise InventoryNotFound(label)
        return row

    def _ensure(self, model, row_id: str, label: str):
        return self._get(model, row_id, label)

    def _get_purchase(self, purchase_id: str) -> InventoryPurchase:
        return self._get(InventoryPurchase, purchase_id, "Compra")

    def _validate_item_refs(self, data: dict) -> None:
        if data.get("category_id"):
            self._ensure(InventoryCategory, data["category_id"], "Categoria")
        if data.get("unit_id"):
            self._ensure(InventoryUnit, data["unit_id"], "Unidade")
        if data.get("default_location_id"):
            self._ensure(InventoryLocation, data["default_location_id"], "Local")

    def _stock_balance_map(self) -> dict[str, float]:
        rows = (
            self._db.query(
                InventoryStockMovement.item_id,
                func.coalesce(func.sum(InventoryStockMovement.quantity_delta), 0.0),
            )
            .filter(InventoryStockMovement.tenant_id == self._tenant_id)
            .group_by(InventoryStockMovement.item_id)
            .all()
        )
        return {item_id: decimal_value(total) for item_id, total in rows}

    def _module_settings(self) -> dict:
        item = (
            self._db.query(GestaoModuleSettings)
            .filter(
                GestaoModuleSettings.tenant_id == self._tenant_id,
                GestaoModuleSettings.module_key == "inventory",
            )
            .first()
        )
        if not item or not item.enabled or item.status == "disabled":
            return {}
        try:
            return json.loads(item.settings_json or "{}")
        except json.JSONDecodeError:
            return {}

    def _average_unit_cost_map(self) -> dict[str, float]:
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
        result: dict[str, float] = {}
        for item_id, quantity, cost in rows:
            quantity_decimal = decimal_value(quantity)
            result[item_id] = round(decimal_value(cost) / quantity_decimal, 8) if quantity_decimal > 0 else ZERO
        return result

    def _required_items_for_order(self, order: Order) -> dict[str, float]:
        items = list(order.items)
        ids = list({pid for item in items for pid in [item.product_id, *[f.product_id for f in item.flavors]]})
        recipes = ProductInventoryAvailabilityService(self._db, self._tenant_id, self._tenant_context)._active_recipes(ids)
        required: dict[str, float] = {}
        for item in items:
            resolution = resolve_recipes(item, recipes)
            if resolution.missing and resolution.uses:
                raise InventoryInvalidReference("Ficha tecnica incompleta para a composicao do pedido.")
            for key, amount in required_decimal(resolution).items():
                required[key] = required.get(key, ZERO) + amount
        return required

    def _required_items_from_cmv_snapshot(self, order_id: str) -> dict[str, float]:
        snapshot = (
            self._db.query(OrderCmvSnapshot)
            .options(
                joinedload(OrderCmvSnapshot.items)
                .joinedload(OrderItemCmvSnapshot.ingredients),
            )
            .filter(
                OrderCmvSnapshot.tenant_id == self._tenant_id,
                OrderCmvSnapshot.order_id == order_id,
            )
            .first()
        )
        if not snapshot:
            return {}

        required: dict[str, float] = {}
        for item_snapshot in snapshot.items:
            frozen = getattr(item_snapshot, "composition_json", None)
            if frozen is not None:
                if not isinstance(frozen, dict) or not isinstance(frozen.get("ingredients"), list):
                    raise InventoryInvalidReference("Composicao congelada invalida; reconciliacao necessaria.")
                for ingredient in frozen["ingredients"]:
                    ingredient_id = ingredient["inventory_item_id"]
                    required[ingredient_id] = required.get(ingredient_id, ZERO) + decimal_value(ingredient["quantity"])
                continue
            # Explicit historical fallback: old CMV ingredient rows are frozen,
            # never recompute an old order from currently active recipes.
            for ingredient in item_snapshot.ingredients:
                if not ingredient.inventory_item_id:
                    continue
                required[ingredient.inventory_item_id] = (
                    required.get(ingredient.inventory_item_id, ZERO)
                    + decimal_value(ingredient.quantity)
                )
        return required

    def _matching_recipes_for_product(
        self,
        product_id: str,
        size_id: str | None,
        crust_id: str | None,
        drink_variant_id: str | None,
    ) -> list[InventoryRecipeVersion]:
        recipes = (
            self._db.query(InventoryRecipeVersion)
            .options(joinedload(InventoryRecipeVersion.items))
            .filter(
                InventoryRecipeVersion.tenant_id == self._tenant_id,
                InventoryRecipeVersion.product_id == product_id,
                InventoryRecipeVersion.active == True,  # noqa: E712
            )
            .all()
        )
        matches: list[InventoryRecipeVersion] = []
        for recipe in recipes:
            is_base = not recipe.product_size_id and not recipe.product_crust_type_id and not recipe.product_drink_variant_id and not recipe.complement_key
            is_selected_size = bool(size_id and recipe.product_size_id == size_id)
            is_selected_crust = bool(crust_id and recipe.product_crust_type_id == crust_id)
            is_selected_drink = bool(drink_variant_id and recipe.product_drink_variant_id == drink_variant_id)
            if is_base or is_selected_size or is_selected_crust or is_selected_drink:
                matches.append(recipe)
        return matches

    def _accumulate_required(self, target: dict[str, float], recipes: list[InventoryRecipeVersion], multiplier: float) -> None:
        for recipe in recipes:
            for item in recipe.items:
                waste_multiplier = 1 + (decimal_value(item.waste_percent) / 100)
                reference = decimal_value(getattr(recipe, "reference_fraction", None) or 1)
                target[item.inventory_item_id] = target.get(item.inventory_item_id, ZERO) + (decimal_value(item.quantity) * waste_multiplier * decimal_value(multiplier) / reference)

    def _ensure_product(self, product_id: str) -> Product:
        product = self._db.query(Product).filter(
            Product.id == product_id,
            Product.tenant_id == self._tenant_id,
        ).first()
        if not product:
            raise InventoryInvalidReference("Produto do catalogo nao encontrado.")
        return product

    def _validate_recipe_refs(self, product_id: str, data: dict, items: list[dict]) -> None:
        from backend.services.recipe_details import normalize_recipe_line
        if data.get("reference_image_url"):
            from backend.services.recipe_image_service import RecipeImageService
            data["reference_image_url"] = RecipeImageService(self._db, self._tenant_id, self._actor_id).validate_reference(data["reference_image_url"])
        self._ensure_product(product_id)
        if data.get("product_size_id"):
            self._ensure_product_child(ProductSize, data["product_size_id"], product_id, "Tamanho")
        if data.get("product_crust_type_id"):
            self._ensure_product_child(ProductCrustType, data["product_crust_type_id"], product_id, "Massa/borda")
        if data.get("product_drink_variant_id"):
            self._ensure_product_child(ProductDrinkVariant, data["product_drink_variant_id"], product_id, "Variante")
        if data.get("complement_key") and not data.get("complement_name"):
            raise InventoryInvalidReference("Informe o nome do complemento interno.")
        for index, item in enumerate(items):
            inventory_item = self._ensure(InventoryItem, item["inventory_item_id"], "Insumo")
            if not inventory_item.active:
                raise InventoryInvalidReference(f"Insumo inativo: {inventory_item.name}.")
            items[index] = normalize_recipe_line(self._db, self._tenant_id, item)

    def _ensure_product_child(self, model, row_id: str, product_id: str, label: str):
        row = (
            self._db.query(model)
            .filter(model.id == row_id, model.product_id == product_id, model.tenant_id == self._tenant_id)
            .first()
        )
        if not row:
            raise InventoryInvalidReference(f"{label} nao pertence ao produto selecionado.")
        return row

    def _get_recipe(self, product_id: str, recipe_id: str) -> InventoryRecipeVersion:
        row = (
            self._db.query(InventoryRecipeVersion)
            .filter(
                InventoryRecipeVersion.id == recipe_id,
                InventoryRecipeVersion.product_id == product_id,
                InventoryRecipeVersion.tenant_id == self._tenant_id,
            )
            .first()
        )
        if not row:
            raise InventoryNotFound("Ficha tecnica")
        return row

    def _deactivate_matching_recipe_scope(self, product_id: str, data: dict, exclude_recipe_id: str | None = None) -> None:
        query = self._db.query(InventoryRecipeVersion).filter(
            InventoryRecipeVersion.tenant_id == self._tenant_id,
            InventoryRecipeVersion.product_id == product_id,
            InventoryRecipeVersion.active == True,  # noqa: E712
            InventoryRecipeVersion.component_role == data.get("component_role", "flavor"),
        )
        if exclude_recipe_id:
            query = query.filter(InventoryRecipeVersion.id != exclude_recipe_id)
        for key, column in (
            ("product_size_id", InventoryRecipeVersion.product_size_id),
            ("product_crust_type_id", InventoryRecipeVersion.product_crust_type_id),
            ("product_drink_variant_id", InventoryRecipeVersion.product_drink_variant_id),
            ("complement_key", InventoryRecipeVersion.complement_key),
        ):
            value = data.get(key)
            query = query.filter(column == value) if value else query.filter(column.is_(None))
        for recipe in query.all():
            recipe.active = False

    def _replace_purchase_items(self, purchase: InventoryPurchase, items: list[dict]) -> None:
        total = ZERO
        for item in items:
            self._ensure(InventoryItem, item["item_id"], "Item")
            total_cost = round(decimal_value(item["quantity"]) * decimal_value(item["unit_cost"]), 8)
            total += total_cost
            self._db.add(InventoryPurchaseItem(
                id=f"inv-pit-{uuid.uuid4().hex[:12]}",
                tenant_id=self._tenant_id,
                purchase_id=purchase.id,
                item_id=item["item_id"],
                quantity=item["quantity"],
                unit_cost=item["unit_cost"],
                total_cost=total_cost,
            ))
        purchase.total_amount = round(total, 8)

    def _replace_recipe_items(self, recipe: InventoryRecipeVersion, items: list[dict]) -> None:
        for item in items:
            self._db.add(InventoryRecipeItem(
                id=f"inv-rci-{uuid.uuid4().hex[:12]}",
                tenant_id=self._tenant_id,
                recipe_id=recipe.id,
                inventory_item_id=item["inventory_item_id"],
                quantity=round(decimal_value(item["quantity"]), 6),
                waste_percent=decimal_value(item.get("waste_percent")),
                notes=item.get("notes"),
                unit_id=item.get("unit_id"), entered_unit_id=item.get("entered_unit_id"),
                entered_quantity=item.get("entered_quantity"), conversion_factor_snapshot=item.get("conversion_factor_snapshot"),
                position=item.get("position", 0), public_name=item.get("public_name"), show_public=item.get("show_public", False),
                allow_removal=item.get("allow_removal", False),
            ))

    def _create_stock_movement_from_manual_entry(self, entry: InventoryManualEntry) -> None:
        quantity = decimal_value(entry.quantity)
        quantity_delta = -quantity if entry.movement_type == "out" else quantity
        self._db.add(InventoryStockMovement(
            id=f"inv-mov-{uuid.uuid4().hex[:12]}",
            tenant_id=self._tenant_id,
            item_id=entry.item_id,
            location_id=entry.location_id,
            source_type="manual_entry",
            source_id=entry.id,
            movement_type=entry.movement_type,
            quantity_delta=round(quantity_delta, 6),
            unit_cost=entry.unit_cost,
            reason=entry.reason,
            notes=json.dumps({"actor_id": self._actor_id, "notes": entry.notes}),
        ))

    def _serialize_item(self, item: InventoryItem, balances: dict[str, float] | None = None) -> dict:
        stock = (balances or self._stock_balance_map()).get(item.id, 0.0)
        return {
            "id": item.id,
            "tenant_id": item.tenant_id,
            "name": item.name,
            "sku": item.sku,
            "item_type": item.item_type,
            "portionable": bool(item.portionable),
            "category_id": item.category_id,
            "category_name": item.category.name if item.category else None,
            "unit_id": item.unit_id,
            "unit_name": item.unit.name if item.unit else None,
            "unit_symbol": item.unit.symbol if item.unit else None,
            "default_location_id": item.default_location_id,
            "default_location_name": item.default_location.name if item.default_location else None,
            "min_stock": item.min_stock,
            "current_stock": round(stock, 6),
            "available_stock": round(max(stock, 0.0), 6),
            "notes": item.notes,
            "active": item.active,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }

    def _serialize_purchase(self, purchase: InventoryPurchase) -> dict:
        return {
            "id": purchase.id,
            "tenant_id": purchase.tenant_id,
            "supplier_id": purchase.supplier_id,
            "supplier_name": purchase.supplier.name if purchase.supplier else None,
            "status": purchase.status,
            "invoice_number": purchase.invoice_number,
            "expected_date": purchase.expected_date,
            "notes": purchase.notes,
            "total_amount": purchase.total_amount,
            "items": [
                {
                    "id": item.id,
                    "purchase_id": item.purchase_id,
                    "item_id": item.item_id,
                    "item_name": item.item.name if item.item else None,
                    "quantity": item.quantity,
                    "unit_cost": item.unit_cost,
                    "total_cost": item.total_cost,
                }
                for item in purchase.items
            ],
            "created_at": purchase.created_at,
            "updated_at": purchase.updated_at,
        }

    def _serialize_manual_entry(self, entry: InventoryManualEntry) -> dict:
        return {
            "id": entry.id,
            "tenant_id": entry.tenant_id,
            "item_id": entry.item_id,
            "item_name": entry.item.name if entry.item else None,
            "location_id": entry.location_id,
            "location_name": entry.location.name if entry.location else None,
            "reversed": self._db.query(InventoryStockMovement.id).filter(
                InventoryStockMovement.tenant_id == self._tenant_id,
                InventoryStockMovement.source_type == "manual_entry_reversal",
                InventoryStockMovement.source_id == entry.id,
            ).first() is not None,
            "movement_type": entry.movement_type,
            "quantity": entry.quantity,
            "unit_cost": entry.unit_cost,
            "reason": entry.reason,
            "notes": entry.notes,
            "created_at": entry.created_at,
        }

    def _serialize_movement(self, movement: InventoryStockMovement) -> dict:
        return {
            "id": movement.id,
            "tenant_id": movement.tenant_id,
            "item_id": movement.item_id,
            "item_name": movement.item.name if movement.item else None,
            "location_id": movement.location_id,
            "location_name": movement.location.name if movement.location else None,
            "source_type": movement.source_type,
            "source_id": movement.source_id,
            "movement_type": movement.movement_type,
            "quantity_delta": movement.quantity_delta,
            "unit_cost": movement.unit_cost,
            "reason": movement.reason,
            "notes": movement.notes,
            "created_at": movement.created_at,
        }

    def _serialize_recipe(self, recipe: InventoryRecipeVersion) -> dict:
        return {
            "id": recipe.id,
            "tenant_id": recipe.tenant_id,
            "product_id": recipe.product_id,
            "product_name": recipe.product.name if recipe.product else None,
            "product_size_id": recipe.product_size_id,
            "product_size_label": recipe.product_size.label if recipe.product_size else None,
            "product_crust_type_id": recipe.product_crust_type_id,
            "product_crust_type_name": recipe.product_crust_type.name if recipe.product_crust_type else None,
            "product_drink_variant_id": recipe.product_drink_variant_id,
            "product_drink_variant_name": recipe.product_drink_variant.name if recipe.product_drink_variant else None,
            "complement_key": recipe.complement_key,
            "complement_name": recipe.complement_name,
            "version_number": recipe.version_number,
            "component_role": recipe.component_role,
            "reference_fraction": recipe.reference_fraction,
            "active": recipe.active,
            "notes": recipe.notes,
            "instructions": recipe.instructions, "preparation_steps": recipe.preparation_steps or [],
            "reference_image_url": recipe.reference_image_url,
            "items": [
                {
                    "id": item.id,
                    "recipe_id": item.recipe_id,
                    "inventory_item_id": item.inventory_item_id,
                    "inventory_item_name": item.inventory_item.name if item.inventory_item else None,
                    "unit_symbol": item.inventory_item.unit.symbol if item.inventory_item and item.inventory_item.unit else None,
                    "quantity": item.quantity,
                    "waste_percent": item.waste_percent,
                    "notes": item.notes,
                    "unit_id": item.unit_id, "entered_unit_id": item.entered_unit_id,
                    "entered_quantity": item.entered_quantity, "conversion_factor_snapshot": item.conversion_factor_snapshot,
                    "position": item.position, "public_name": item.public_name, "show_public": item.show_public,
                    "allow_removal": item.allow_removal,
                }
                for item in recipe.items
            ],
            "created_at": recipe.created_at,
            "updated_at": recipe.updated_at,
        }


class ProductInventoryAvailabilityService:
    def __init__(
        self,
        db: Session,
        tenant_id: str = TENANT_ID,
        tenant_context: TenantContext | None = None,
    ):
        self._db = db
        self._tenant_context = tenant_context
        self._tenant_id = InventoryService._resolve_tenant_id(tenant_id, tenant_context)

    def sales_control_enabled(self) -> bool:
        item = (
            self._db.query(GestaoModuleSettings)
            .filter(
                GestaoModuleSettings.tenant_id == self._tenant_id,
                GestaoModuleSettings.module_key == "inventory",
            )
            .first()
        )
        if not item or not item.enabled or item.status == "disabled":
            return False
        try:
            settings = json.loads(item.settings_json or "{}")
        except json.JSONDecodeError:
            settings = {}
        return bool(settings.get("sales_control_enabled")) and settings.get("out_of_stock_behavior", "show_unavailable") == "show_unavailable"

    def product_payloads(self, product_ids: list[str]) -> dict[str, dict]:
        if not product_ids:
            return {}
        if not self.sales_control_enabled():
            return {
                product_id: {
                    "inventory_available": True,
                    "inventory_status": "disabled",
                    "inventory_unavailable_message": None,
                }
                for product_id in product_ids
            }
        from backend.services.inventory_foundation_service import InventoryFoundationService
        balance_rows = InventoryFoundationService(self._db, self._tenant_id, "system:availability", self._tenant_context).balances()["items"]
        balances = {}
        for row in balance_rows:
            balances[row["item_id"]] = balances.get(row["item_id"], ZERO) + decimal_value(row["available"])
        recipes = self._active_recipes(product_ids)
        return {
            product_id: self._availability_for_product(product_id, recipes.get(product_id, []), balances)
            for product_id in product_ids
        }

    def validate_cart_item(self, item) -> None:
        self.validate_cart_items([item])

    def validate_cart_items(self, items) -> None:
        if not self.sales_control_enabled():
            return
        items = list(items)
        product_ids = list({pid for item in items for pid in [item.product_id, *[f.product_id for f in item.flavors]]})
        recipes = self._active_recipes(product_ids)
        required: dict[str, float] = {}
        for item in items:
            resolution = resolve_recipes(item, recipes)
            if resolution.missing and resolution.uses:
                raise InventoryInvalidReference("Ficha tecnica incompleta para a composicao do pedido.")
            for key, amount in required_decimal(resolution).items():
                required[key] = required.get(key, ZERO) + amount
        # Use the same inventory row lock order as production consumption.
        self._db.query(InventoryItem).filter(
            InventoryItem.tenant_id == self._tenant_id,
            InventoryItem.id.in_(required),
        ).order_by(InventoryItem.id).with_for_update().all()
        from backend.services.inventory_foundation_service import InventoryFoundationService
        balance_rows = InventoryFoundationService(self._db, self._tenant_id, "system:availability", self._tenant_context).balances()["items"]
        balances = {}
        for row in balance_rows:
            balances[row["item_id"]] = balances.get(row["item_id"], ZERO) + decimal_value(row["available"])
        if any(amount > balances.get(key, ZERO) for key, amount in required.items()):
            raise InventoryUnavailable()

    def _active_recipes(self, product_ids: list[str]) -> dict[str, list[InventoryRecipeVersion]]:
        rows = (
            self._db.query(InventoryRecipeVersion)
            .options(joinedload(InventoryRecipeVersion.items))
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

    def _matching_recipes(
        self,
        product_id: str,
        size_id: str | None,
        crust_id: str | None,
        drink_variant_id: str | None,
    ) -> list[InventoryRecipeVersion]:
        recipes = self._active_recipes([product_id]).get(product_id, [])
        matches = []
        for recipe in recipes:
            is_base = not recipe.product_size_id and not recipe.product_crust_type_id and not recipe.product_drink_variant_id and not recipe.complement_key
            is_selected_size = size_id and recipe.product_size_id == size_id
            is_selected_crust = crust_id and recipe.product_crust_type_id == crust_id
            is_selected_drink = drink_variant_id and recipe.product_drink_variant_id == drink_variant_id
            if is_base or is_selected_size or is_selected_crust or is_selected_drink:
                matches.append(recipe)
        return matches

    def _availability_for_product(self, product_id: str, recipes: list[InventoryRecipeVersion], balances: dict[str, float]) -> dict:
        if not recipes:
            return {
                "inventory_available": True,
                "inventory_status": "not_configured",
                "inventory_unavailable_message": None,
            }
        base_recipes = [recipe for recipe in recipes if self._is_base_recipe(recipe)]
        scoped_recipes = [recipe for recipe in recipes if not self._is_base_recipe(recipe)]
        if any(not self._recipe_has_stock(recipe, balances) for recipe in base_recipes):
            return self._unavailable_payload()
        if scoped_recipes and not any(self._recipe_has_stock(recipe, balances) for recipe in scoped_recipes):
            return self._unavailable_payload()
        return {
            "inventory_available": True,
            "inventory_status": "available",
            "inventory_unavailable_message": None,
        }

    def _recipe_has_stock(self, recipe: InventoryRecipeVersion, balances: dict[str, float]) -> bool:
        required: dict[str, float] = {}
        self._accumulate_required(required, [recipe], 1.0)
        return all(required_qty <= balances.get(item_id, ZERO) for item_id, required_qty in required.items())

    def _accumulate_required(self, target: dict[str, float], recipes: list[InventoryRecipeVersion], multiplier: float) -> None:
        for recipe in recipes:
            for item in recipe.items:
                waste_multiplier = 1 + (decimal_value(item.waste_percent) / 100)
                reference = decimal_value(getattr(recipe, "reference_fraction", None) or 1)
                target[item.inventory_item_id] = target.get(item.inventory_item_id, ZERO) + (decimal_value(item.quantity) * waste_multiplier * decimal_value(multiplier) / reference)

    def _is_base_recipe(self, recipe: InventoryRecipeVersion) -> bool:
        return not recipe.product_size_id and not recipe.product_crust_type_id and not recipe.product_drink_variant_id and not recipe.complement_key

    def _unavailable_payload(self) -> dict:
        return {
            "inventory_available": False,
            "inventory_status": "unavailable",
            "inventory_unavailable_message": "Indisponivel no momento.",
        }

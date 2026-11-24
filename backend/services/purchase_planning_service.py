from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.core.tenant_context import TenantContext
from backend.models.inventory import InventoryItem, InventoryPurchase, InventoryPurchaseItem, InventoryStockMovement
from backend.models.inventory_foundation import InventoryReservation
from backend.models.inventory_portion import InventoryPortionConfig
from backend.schemas.purchase_planning import PurchasePlanningOut
from backend.services.inventory_portion_service import InventoryPortionConfigService


ZERO = Decimal("0")
SCALE = Decimal("0.000001")


def dec(value) -> Decimal:
    return Decimal(str(value or 0))


def positive(value: Decimal) -> Decimal:
    return max(ZERO, value).quantize(SCALE, rounding=ROUND_HALF_UP)


class PurchasePlanningService:
    """Read-only need calculation; it never creates stock or purchase effects."""

    def __init__(self, db: Session, tenant_context: TenantContext):
        self.db = db
        self.tenant_id = tenant_context.tenant_id

    def plan(self) -> dict:
        stock = self._stock_map()
        reserved = self._reserved_map()
        in_transit = self._in_transit_map()
        portion_configs = self.db.query(InventoryPortionConfig).filter(
            InventoryPortionConfig.tenant_id == self.tenant_id,
            InventoryPortionConfig.active.is_(True),
        ).all()
        portion_outputs = {row.output_item_id for row in portion_configs}
        rows = []

        items = self.db.query(InventoryItem).filter(
            InventoryItem.tenant_id == self.tenant_id,
            InventoryItem.active.is_(True),
            InventoryItem.item_type != "finished_good",
        ).order_by(InventoryItem.name, InventoryItem.id).all()
        for item in items:
            if item.id in portion_outputs:
                continue
            current = dec(stock.get(item.id))
            reserved_value = dec(reserved.get(item.id))
            available = positive(current - reserved_value)
            minimum = dec(item.min_stock)
            target = minimum
            suggested = positive(target - available - dec(in_transit.get(item.id)))
            state, action, reason = self._direct_state(item, suggested, in_transit.get(item.id, ZERO))
            rows.append(self._row(item, "direct", current, reserved_value, available, dec(in_transit.get(item.id)), minimum, target, suggested, state, action, reason))

        portion_rows = self._portion_rows(portion_configs, stock, reserved, in_transit)
        rows.extend(portion_rows)
        rows.sort(key=lambda row: (row["action"] != "purchase_required", row["item_name"].casefold(), row["item_id"]))
        totals = {
            "total": len(rows),
            "purchase_required": sum(row["action"] == "purchase_required" for row in rows),
            "covered": sum(row["action"] == "covered" for row in rows),
            "review_required": sum(row["action"] == "review_required" for row in rows),
        }
        return PurchasePlanningOut(tenant_id=self.tenant_id, generated_at=datetime.now(timezone.utc).isoformat(), items=rows, totals=totals).model_dump(mode="json")

    def _portion_rows(self, configs, stock, reserved, in_transit) -> list[dict]:
        if not configs:
            return []
        alerts = {row["config_id"]: row for row in InventoryPortionConfigService(self.db, self.tenant_id, "system:purchase-planning").replenishment_alerts()}
        items = {row.id: row for row in self.db.query(InventoryItem).filter(InventoryItem.tenant_id == self.tenant_id, InventoryItem.id.in_({c.output_item_id for c in configs} | {c.source_item_id for c in configs})).all()}
        rows = []
        for config in configs:
            alert = alerts.get(config.id)
            output = items.get(config.output_item_id)
            source = items.get(config.source_item_id)
            if not alert or not output or not source:
                continue
            current = dec(alert.get("physical_stock"))
            reserved_value = dec(alert.get("reserved_stock"))
            available = positive(current - reserved_value)
            source_quantity = alert.get("estimated_source_quantity")
            source_in_transit = dec(in_transit.get(source.id))
            suggested = positive(dec(source_quantity) - source_in_transit) if source_quantity is not None else ZERO
            if alert.get("conversion_error"):
                state, action, reason = "blocked", "review_required", f"Conversao de porcao bloqueada: {alert['conversion_error']}"
            elif getattr(config, "usage", "mandatory") != "mandatory":
                state, action, reason = "pending", "review_required", "Porcao nao obrigatoria; exige confirmacao operacional antes da compra."
            elif suggested > ZERO:
                state, action, reason = "estimated", "purchase_required", "Necessidade estimada a partir da configuracao de porcionamento publicada."
            else:
                state, action, reason = "confirmed", "covered", "Estoque de porcao, preparo ou compra confirmada cobre a necessidade."
            rows.append({
                "item_id": output.id,
                "item_name": output.name,
                "unit_id": output.unit_id,
                "unit_symbol": output.unit.symbol if output.unit else None,
                "source": "portion",
                "source_item_id": source.id,
                "source_item_name": source.name,
                "current_stock": current,
                "reserved_stock": reserved_value,
                "available_stock": available,
                "in_transit": source_in_transit,
                "minimum_stock": dec(config.min_stock),
                "target_stock": dec(config.target_stock),
                "suggested_quantity": suggested,
                "state": state,
                "action": action,
                "reason": reason,
            })
        return rows

    @staticmethod
    def _direct_state(item, suggested: Decimal, transit: Decimal):
        if item.unit_id is None:
            return "blocked", "review_required", "Insumo sem unidade-base cadastrada."
        if suggested > ZERO:
            if transit > ZERO:
                return "estimated", "purchase_required", "Estoque abaixo do minimo; parte da necessidade esta em compra confirmada em transito."
            return "confirmed", "purchase_required", "Estoque disponivel abaixo do minimo."
        if transit > ZERO:
            return "pending", "covered", "Necessidade coberta por compra confirmada em transito."
        return "confirmed", "covered", "Estoque disponivel atende ao minimo."

    @staticmethod
    def _row(item, source, current, reserved, available, transit, minimum, target, suggested, state, action, reason):
        return {
            "item_id": item.id, "item_name": item.name, "unit_id": item.unit_id,
            "unit_symbol": item.unit.symbol if item.unit else None, "source": source,
            "source_item_id": None, "source_item_name": None,
            "current_stock": current, "reserved_stock": reserved, "available_stock": available,
            "in_transit": transit, "minimum_stock": minimum, "target_stock": target,
            "suggested_quantity": suggested, "state": state, "action": action, "reason": reason,
        }

    def _stock_map(self):
        return dict(self.db.query(InventoryStockMovement.item_id, func.coalesce(func.sum(InventoryStockMovement.quantity_delta), 0)).filter(InventoryStockMovement.tenant_id == self.tenant_id).group_by(InventoryStockMovement.item_id).all())

    def _reserved_map(self):
        now = datetime.now(timezone.utc)
        return dict(self.db.query(InventoryReservation.item_id, func.coalesce(func.sum(InventoryReservation.quantity), 0)).filter(InventoryReservation.tenant_id == self.tenant_id, InventoryReservation.status == "active", or_(InventoryReservation.expires_at.is_(None), InventoryReservation.expires_at > now)).group_by(InventoryReservation.item_id).all())

    def _in_transit_map(self):
        rows = self.db.query(InventoryPurchaseItem.item_id, func.coalesce(func.sum(InventoryPurchaseItem.quantity), 0)).join(InventoryPurchase, InventoryPurchase.id == InventoryPurchaseItem.purchase_id).filter(InventoryPurchase.tenant_id == self.tenant_id, InventoryPurchaseItem.tenant_id == self.tenant_id, InventoryPurchase.status == "confirmed").group_by(InventoryPurchaseItem.item_id).all()
        return dict(rows)

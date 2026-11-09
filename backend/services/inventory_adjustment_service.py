"""Count corrections and losses on the canonical tenant-owned movement ledger."""
from __future__ import annotations

import json
import uuid
from decimal import Decimal

from sqlalchemy import func

from backend.models.inventory import InventoryItem, InventoryLocation, InventoryStockMovement, InventoryUnit
from backend.models.inventory_foundation import InventoryLot
from backend.models.inventory_portion import InventoryPortionConfig
from backend.services.inventory_foundation_service import (
    FoundationConflict, FoundationInvalid, InventoryFoundationService, ZERO,
)


class InventoryAdjustmentService(InventoryFoundationService):
    def _buckets(self, item):
        grouped = self._query(InventoryStockMovement).filter(
            InventoryStockMovement.item_id == item.id,
        ).with_entities(
            InventoryStockMovement.location_id, InventoryStockMovement.lot_id,
            func.sum(InventoryStockMovement.quantity_delta),
        ).group_by(
            InventoryStockMovement.location_id, InventoryStockMovement.lot_id,
        ).all()
        quantities = {(location_id, lot_id): Decimal(physical) for location_id, lot_id, physical in grouped}
        lots = self._query(InventoryLot).filter(InventoryLot.item_id == item.id).all()
        for lot in lots:
            quantities.setdefault((lot.location_id, lot.id), ZERO)
        reservations = self._active_reservations(item.id)
        for reservation in reservations:
            quantities.setdefault((reservation.location_id, reservation.lot_id), ZERO)
        if not quantities:
            quantities[(item.default_location_id, None)] = ZERO
        location_ids = {location_id for location_id, _ in quantities if location_id}
        locations = self._query(InventoryLocation).filter(InventoryLocation.id.in_(location_ids)).all() if location_ids else []
        names = {row.id: row.name for row in locations}
        lot_codes = {row.id: row.lot_code for row in lots}
        reserved = {}
        for row in reservations:
            key = (row.location_id, row.lot_id)
            reserved[key] = reserved.get(key, ZERO) + Decimal(row.quantity)
        return [{
            "location_id": location_id, "location_name": names.get(location_id),
            "lot_id": lot_id, "lot_code": lot_codes.get(lot_id),
            "physical": format(physical, "f"),
            "reserved": format(reserved.get((location_id, lot_id), ZERO), "f"),
            "available": format(physical - reserved.get((location_id, lot_id), ZERO), "f"),
            "unit_symbol": item.unit.symbol,
        } for (location_id, lot_id), physical in sorted(quantities.items(), key=lambda entry: (entry[0][0] or "", entry[0][1] or ""))]

    def buckets(self, item_id):
        item = self._get(InventoryItem, item_id)
        if not item.unit_id:
            raise FoundationInvalid("Item sem unidade base.")
        unit = self._get(InventoryUnit, item.unit_id)
        item.unit = unit
        return self._buckets(item)

    def adjust(self, item_id, body, key):
        scope = f"items/{item_id}/adjustments"
        business_key = str(body.business_key)

        def execute(operation):
            item = self._lock_items([item_id])[0]
            if not item.unit_id:
                raise FoundationInvalid("Item sem unidade base.")
            unit = self._get(InventoryUnit, item.unit_id)
            item.unit = unit
            is_portion_output = self._query(InventoryPortionConfig).filter(
                InventoryPortionConfig.output_item_id == item.id,
            ).first() is not None
            if unit.code == "portion_count" or unit.symbol.upper() == "PRQ" or is_portion_output:
                if any(value != value.to_integral_value() for value in (body.quantity, body.expected_physical)):
                    raise FoundationInvalid("PRQ exige quantidades inteiras.", code="InvalidQuantityPrecision")
            buckets = self._buckets(item)
            if body.location_id:
                self._get(InventoryLocation, body.location_id)
            selected_location_id = body.location_id
            if body.lot_id:
                lot = self._get(InventoryLot, body.lot_id, lock=True)
                if lot.item_id != item.id or (body.location_id and lot.location_id != body.location_id):
                    raise FoundationInvalid("Lote nao pertence ao item/local informado.")
                selected_location_id = lot.location_id
            elif body.location_id is None and not any(
                row["location_id"] is None and row["lot_id"] is None for row in buckets
            ) and len(buckets) == 1:
                selected_location_id = buckets[0]["location_id"]
                if buckets[0]["lot_id"] is not None:
                    raise FoundationInvalid("Informe lot_id para ajustar estoque de lote.")
            matches = [row for row in buckets
                       if (row["location_id"], row["lot_id"]) == (selected_location_id, body.lot_id)]
            if len(matches) != 1:
                raise FoundationInvalid("Selecione um unico bucket de local/lote existente.", code="AmbiguousAdjustmentBucket")
            bucket = matches[0]
            current = Decimal(bucket["physical"])
            reserved = Decimal(bucket["reserved"])
            if current != body.expected_physical:
                raise FoundationConflict("Saldo fisico mudou desde a leitura.", code="VersionConflict")
            delta = body.quantity - current if body.kind == "correction" else -body.quantity
            result = current + delta
            if result < 0 or result < reserved:
                raise FoundationConflict("Ajuste ficaria abaixo de zero ou das reservas ativas.", code="InventoryUnavailable")
            movement_id = None
            if delta:
                movement_id = str(uuid.uuid4())
                self.db.add(InventoryStockMovement(
                    id=movement_id, tenant_id=self.tenant_id, item_id=item.id,
                    location_id=bucket["location_id"], lot_id=bucket["lot_id"],
                    operation_id=operation.id, operation_sequence=1,
                    logical_line_id="1", source_type="inventory_adjustment",
                    source_id=operation.id, movement_type="in" if delta > 0 else "out",
                    quantity_delta=delta, unit_cost=ZERO, reason=body.reason,
                    notes=json.dumps({"actor_id": self.actor_id, "kind": body.kind,
                                      "reason": body.reason, "notes": body.notes,
                                      "delta": format(delta, "f")}),
                ))
                self.db.flush()
            return {
                "operation_id": operation.id, "movement_id": movement_id,
                "item_id": item.id, "kind": body.kind,
                "location_id": bucket["location_id"], "lot_id": bucket["lot_id"],
                "previous_physical": format(current, "f"), "physical": format(result, "f"),
                "reserved": format(reserved, "f"), "available": format(result - reserved, "f"),
                "delta": format(delta, "f"), "unit_symbol": unit.symbol,
                "unit_cost": "0", "cost_status": "unvalued",
            }

        return self._command(scope, key, body, "loss" if body.kind == "loss" else "compensation", business_key, execute)

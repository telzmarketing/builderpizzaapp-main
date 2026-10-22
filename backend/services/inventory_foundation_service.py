"""One Decimal movement ledger, explicit lots/reservations, no checkout policy.

Public commands own their commit. Legacy bridge methods only flush and must run
in the caller's already locked order/item transaction.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP, localcontext
from zoneinfo import ZoneInfo

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError

from backend.core.exceptions import DomainError
from backend.models.inventory import (
    InventoryItem, InventoryLocation, InventoryStockMovement, InventorySupplier, InventoryUnit,
)
from backend.models.inventory_foundation import (
    InventoryItemPackaging, InventoryLot, InventoryOperation, InventoryReservation,
)
from backend.models.tenant import Tenant

Q = Decimal("0.000001")
C = Decimal("0.00000001")
ZERO = Decimal(0)


class FoundationInvalid(DomainError):
    http_status = 422


class FoundationConflict(DomainError):
    http_status = 409


class FoundationNotFound(DomainError):
    http_status = 404


def normalized_quantity(value: Decimal) -> Decimal:
    with localcontext() as context:
        context.prec = 50
        result = value.quantize(Q, rounding=ROUND_HALF_UP)
    if not result.is_finite() or abs(result) >= Decimal("100000000000000"):
        raise FoundationInvalid("Quantidade fora da precisao suportada.")
    if value > 0 and result <= 0:
        raise FoundationInvalid("Quantidade convertida inferior a precisao suportada.")
    return result


def convert_decimal(quantity, source_factor, target_factor):
    with localcontext() as context:
        context.prec = 50
        return normalized_quantity(Decimal(quantity) * Decimal(source_factor) / Decimal(target_factor))


def output(value):
    """Explicit decimal strings; never pass Decimal through jsonable_encoder."""
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: output(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [output(item) for item in value]
    return value


def utcnow():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


class InventoryFoundationService:
    def __init__(self, db, tenant_id: str, actor_id: str, tenant_context=None):
        if not tenant_id or not actor_id:
            raise FoundationInvalid("Contexto confiavel de tenant/ator obrigatorio.")
        if tenant_context is not None and tenant_context.tenant_id != tenant_id:
            raise FoundationInvalid("Contexto de tenant divergente.")
        self.db, self.tenant_id, self.actor_id = db, tenant_id, actor_id

    def _query(self, model):
        return self.db.query(model).filter(model.tenant_id == self.tenant_id)

    def _get(self, model, resource_id, *, lock=False):
        query = self._query(model).filter(model.id == resource_id)
        if lock:
            query = query.populate_existing().with_for_update()
        row = query.first()
        if row is None:
            raise FoundationNotFound("Referencia nao encontrada neste tenant.")
        return row

    def _lock_items(self, item_ids):
        item_ids = set(item_ids)
        found = self._query(InventoryItem).filter(InventoryItem.id.in_(item_ids)).order_by(InventoryItem.id).populate_existing().with_for_update().all()
        if len(found) != len(item_ids):
            raise FoundationNotFound("Insumo nao encontrado neste tenant.")
        return found

    def _lock_units(self, unit_ids):
        ids = {value for value in unit_ids if value}
        rows = self._query(InventoryUnit).filter(InventoryUnit.id.in_(ids)).order_by(InventoryUnit.id).populate_existing().with_for_update().all()
        if len(rows) != len(ids):
            raise FoundationNotFound("Unidade nao encontrada neste tenant.")

    def _serialize_key(self, scope, key):
        if self.db.get_bind().dialect.name == "postgresql":
            value = int.from_bytes(hashlib.sha256(f"{self.tenant_id}:{scope}:{key}".encode()).digest()[:8], "big", signed=True)
            self.db.execute(text("SELECT pg_advisory_xact_lock(:value)"), {"value": value})

    def _command(self, scope, key, body, kind, business_key, execute):
        if not key or len(key) > 200:
            raise FoundationInvalid("Idempotency-Key obrigatoria, maximo 200 caracteres.")
        raw = body.model_dump(mode="json")
        request_hash = hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        try:
            self._serialize_key(scope, key)
            prior = self._query(InventoryOperation).filter(
                InventoryOperation.idempotency_scope == scope,
                InventoryOperation.idempotency_key == key,
            ).first()
            if prior:
                if prior.request_hash != request_hash:
                    raise FoundationConflict("Chave reutilizada com conteudo diferente.", code="IdempotencyConflict")
                result = {name: value for name, value in prior.result_json.items() if name != "_request_snapshot"}
                self.db.commit()
                return result
            if self._query(InventoryOperation).filter(InventoryOperation.kind == kind, InventoryOperation.business_key == business_key).first():
                raise FoundationConflict("Identidade de negocio ja utilizada.", code="BusinessIdentityConflict")
            operation = InventoryOperation(
                id=str(uuid.uuid4()), tenant_id=self.tenant_id, actor_id=self.actor_id,
                kind=kind, business_key=business_key, idempotency_scope=scope,
                idempotency_key=key, request_hash=request_hash, status="pending", version=1,
            )
            self.db.add(operation)
            self.db.flush()
            result = output(execute(operation))
            operation.status, operation.result_json, operation.committed_at = "committed", {**result, "_request_snapshot": raw}, utcnow()
            self.db.commit()
            return result
        except IntegrityError as exc:
            self.db.rollback()
            raise FoundationConflict("Conflito de identidade ou referencia concorrente.") from exc
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _new(body):
        if body.expected_version != 0:
            raise FoundationConflict("Criacao exige expected_version zero.", code="VersionConflict")

    def _unit(self, unit_id):
        unit = self._get(InventoryUnit, unit_id)
        if not unit.active or not unit.dimension or not unit.conversion_factor:
            raise FoundationInvalid("Unidade exige dimensao e fator confirmados.", code="UnconfirmedUnit")
        return unit

    def preview(self, body):
        item = self._get(InventoryItem, body.item_id)
        if not item.active or not item.unit_id:
            raise FoundationInvalid("Insumo sem unidade base ativa.")
        source, target = self._unit(body.unit_id), self._unit(item.unit_id)
        if {source.dimension, target.dimension} == {"mass", "volume"}:
            raise FoundationInvalid("Conversao massa/volume exige densidade cadastrada; nao disponivel nesta fase.", code="DensityRequired")
        packaging = None
        if body.packaging_id:
            packaging = self._get(InventoryItemPackaging, body.packaging_id)
            if not packaging.active or packaging.item_id != item.id or packaging.commercial_unit_id != source.id or packaging.base_unit_id != target.id:
                raise FoundationInvalid("Embalagem incompativel com item/unidades.")
            if packaging.variable_weight:
                if body.measured_quantity is None or body.measured_unit_id is None:
                    raise FoundationInvalid("Peso variavel exige quantidade total efetivamente medida.")
                measured = self._unit(body.measured_unit_id)
                if measured.dimension != target.dimension:
                    raise FoundationInvalid("Dimensoes da medicao incompativeis.")
                quantity = convert_decimal(body.measured_quantity, measured.conversion_factor, target.conversion_factor)
            else:
                if body.measured_quantity is not None:
                    raise FoundationInvalid("Medicao permitida somente para embalagem variavel.")
                quantity = convert_decimal(body.quantity, packaging.factor, Decimal(1))
        else:
            if body.measured_quantity is not None:
                raise FoundationInvalid("Medicao exige embalagem variavel confirmada.")
            if source.dimension != target.dimension:
                raise FoundationInvalid("Conversao entre dimensoes exige embalagem confirmada.", code="IncompatibleDimensions")
            quantity = convert_decimal(body.quantity, source.conversion_factor, target.conversion_factor)
        return output({"item_id": item.id, "original_quantity": body.quantity, "original_unit_id": source.id,
                       "quantity": quantity, "unit_id": target.id, "packaging_id": packaging.id if packaging else None,
                       "packaging_version": packaging.version if packaging else None,
                       "rounding": "ROUND_HALF_UP", "scale": 6})

    def _page(self, query, model, serializer, cursor=None, limit=500):
        if cursor:
            query = query.filter(model.id > cursor)
        rows = query.order_by(model.id).limit(limit + 1).all()
        return {"items": [serializer(row) for row in rows[:limit]],
                "next_cursor": rows[limit-1].id if len(rows) > limit else None}

    def list_units(self, cursor=None, limit=500):
        return self._page(self._query(InventoryUnit), InventoryUnit, self._unit_output, cursor, limit)

    @staticmethod
    def _unit_output(row):
        return output({"id": row.id, "name": row.name, "symbol": row.symbol, "code": row.code,
                       "dimension": row.dimension, "conversion_factor": row.conversion_factor, "active": row.active, "version": row.version})

    def create_unit(self, body, key):
        def execute(op):
            self._new(body)
            if self._query(InventoryUnit).filter(InventoryUnit.code == body.code).first():
                raise FoundationConflict("Codigo de unidade ja utilizado.")
            row = InventoryUnit(id=str(uuid.uuid4()), tenant_id=self.tenant_id, name=body.name, symbol=body.symbol,
                                code=body.code, dimension=body.dimension, conversion_factor=body.conversion_factor,
                                unit_type={"mass": "weight", "volume": "volume", "count": "unit"}[body.dimension], active=True, version=1)
            self.db.add(row)
            self.db.flush()
            return self._unit_output(row)
        return self._command("units", key, body, "unit_definition", body.code, execute)

    def update_unit(self, unit_id, body, key):
        def execute(op):
            row = self._get(InventoryUnit, unit_id, lock=True)
            if row.version != body.expected_version:
                raise FoundationConflict("Versao da unidade divergente.", code="VersionConflict")
            if row.symbol != body.symbol:
                raise FoundationInvalid("Classificacao preserva simbolo existente.")
            if row.dimension and row.conversion_factor and (row.dimension != body.dimension or row.conversion_factor != body.conversion_factor or row.code != body.code):
                used_packaging = self._query(InventoryItemPackaging).filter(
                    (InventoryItemPackaging.base_unit_id == row.id) | (InventoryItemPackaging.commercial_unit_id == row.id)).first()
                used_movement = self._query(InventoryStockMovement).join(InventoryItem, InventoryItem.id == InventoryStockMovement.item_id).filter(InventoryItem.tenant_id == self.tenant_id, InventoryItem.unit_id == row.id).first()
                if used_packaging or used_movement:
                    raise FoundationConflict("Unidade utilizada possui classificacao imutavel.")
            other = self._query(InventoryUnit).filter(InventoryUnit.code == body.code, InventoryUnit.id != row.id).first()
            if other:
                raise FoundationConflict("Codigo de unidade ja utilizado.")
            row.name, row.code, row.dimension, row.conversion_factor = body.name, body.code, body.dimension, body.conversion_factor
            row.version += 1
            self.db.flush()
            return self._unit_output(row)
        return self._command(f"units/{unit_id}", key, body, "unit_definition", f"{unit_id}:{body.expected_version}", execute)

    def create_packaging(self, body, key):
        def execute(op):
            self._new(body)
            item = self._lock_items([body.item_id])[0]
            self._lock_units([body.commercial_unit_id, body.base_unit_id])
            source = self._unit(body.commercial_unit_id)
            target = self._unit(body.base_unit_id)
            if {source.dimension, target.dimension} == {"mass", "volume"}:
                raise FoundationInvalid("Conversao massa/volume exige densidade cadastrada; nao disponivel nesta fase.", code="DensityRequired")
            if target.id != item.unit_id:
                raise FoundationInvalid("Unidade base da embalagem deve ser a do item.")
            if body.supplier_id:
                self._get(InventorySupplier, body.supplier_id)
            row = InventoryItemPackaging(id=str(uuid.uuid4()), tenant_id=self.tenant_id, actor_id=self.actor_id,
                **body.model_dump(exclude={"expected_version"}), version=1, active=True)
            self.db.add(row)
            self.db.flush()
            return self._packaging_output(row)
        return self._command("packagings", key, body, "packaging_definition", key, execute)

    @staticmethod
    def _packaging_output(row):
        return output({name: getattr(row, name) for name in ("id", "name", "item_id", "supplier_id", "commercial_unit_id", "base_unit_id", "factor", "variable_weight", "version", "active")})

    def list_packagings(self, item_id=None, cursor=None, limit=500):
        query = self._query(InventoryItemPackaging)
        if item_id:
            self._get(InventoryItem, item_id)
            query = query.filter(InventoryItemPackaging.item_id == item_id)
        return self._page(query, InventoryItemPackaging, self._packaging_output, cursor, limit)

    def create_lot(self, body, key):
        def execute(op):
            self._new(body)
            self._lock_items([body.item_id])
            self._get(InventoryLocation, body.location_id)
            if body.supplier_id:
                self._get(InventorySupplier, body.supplier_id)
            row = InventoryLot(id=str(uuid.uuid4()), tenant_id=self.tenant_id, actor_id=self.actor_id,
                               **body.model_dump(exclude={"expected_version"}),
                               status="available" if body.expires_on or body.effective_expires_at else "quarantine", version=1)
            self.db.add(row)
            self.db.flush()
            return self._lot_output(row)
        return self._command("lots", key, body, "lot_definition", key, execute)

    @staticmethod
    def _lot_output(row):
        return output({name: getattr(row, name) for name in ("id", "item_id", "location_id", "supplier_id", "lot_code", "received_at", "manufactured_on", "expires_on", "effective_expires_at", "status", "version")})

    def list_lots(self, item_id=None, cursor=None, limit=500):
        query = self._query(InventoryLot)
        if item_id:
            self._get(InventoryItem, item_id)
            query = query.filter(InventoryLot.item_id == item_id)
        return self._page(query, InventoryLot, self._lot_output, cursor, limit)

    def set_lot_state(self, lot_id, body, key):
        def execute(op):
            initial = self._get(InventoryLot, lot_id)
            self._lock_items([initial.item_id])
            lot = self._get(InventoryLot, lot_id, lock=True)
            if lot.version != body.expected_version:
                raise FoundationConflict("Versao do lote divergente.", code="VersionConflict")
            if lot.status in ("consumed", "discarded"):
                raise FoundationConflict("Lote terminal nao pode ser reaberto.")
            if body.status == "available" and not lot.expires_on and not lot.effective_expires_at:
                raise FoundationInvalid("Lote sem validade confirmada permanece em quarentena.")
            lot.status, lot.version = body.status, lot.version + 1
            # Blocking never releases reservations or changes physical stock.
            self.db.flush()
            return self._lot_output(lot)
        return self._command(f"lots/{lot_id}/state", key, body, "lot_state", f"{lot_id}:{body.expected_version}", execute)

    def _tenant_timezone(self):
        tenant = self.db.query(Tenant).filter(Tenant.id == self.tenant_id).first()
        if not tenant or not tenant.timezone:
            raise FoundationInvalid("Timezone do tenant obrigatorio para validade por data.")
        try:
            return ZoneInfo(tenant.timezone)
        except (KeyError, ValueError) as exc:
            raise FoundationInvalid("Timezone do tenant invalido.") from exc

    def _lot_deadline(self, lot):
        deadlines = [aware(lot.effective_expires_at)] if lot.effective_expires_at else []
        if lot.expires_on:
            # Original date remains effective throughout its local calendar day.
            deadlines.append(datetime.combine(lot.expires_on + timedelta(days=1), datetime.min.time(), self._tenant_timezone()).astimezone(timezone.utc))
        return min(deadlines) if deadlines else None

    def _eligible(self, lot, now=None):
        now = now or utcnow()
        if lot.status != "available":
            return False
        if not lot.effective_expires_at and not lot.expires_on:
            return False
        if lot.effective_expires_at and aware(lot.effective_expires_at) <= now:
            return False
        if lot.expires_on:
            if lot.expires_on < now.astimezone(self._tenant_timezone()).date():
                return False
        return True

    def _active_reservations(self, item_id=None):
        query = self._query(InventoryReservation).filter(InventoryReservation.status == "active")
        if item_id:
            query = query.filter(InventoryReservation.item_id == item_id)
        now = utcnow()
        return [row for row in query.all() if row.expires_at is None or aware(row.expires_at) > now]

    def _physical(self, item_id, location_id=None, lot_id=None):
        query = self._query(InventoryStockMovement).filter(InventoryStockMovement.item_id == item_id)
        query = query.filter(InventoryStockMovement.location_id == location_id)
        query = query.filter(InventoryStockMovement.lot_id == lot_id)
        return Decimal(query.with_entities(func.coalesce(func.sum(InventoryStockMovement.quantity_delta), 0)).scalar())

    def _available(self, item_id, location_id, lot_id, own_order=None):
        physical = self._physical(item_id, location_id, lot_id)
        reserved = sum((row.quantity for row in self._active_reservations(item_id)
                        if row.location_id == location_id and row.lot_id == lot_id
                        and not (own_order and row.source_type == "order" and row.source_id == own_order)), ZERO)
        return physical - reserved

    def _movement(self, op, line, sequence, item_id, location_id, lot_id, delta, cost, source_type, source_id, reason):
        movement = InventoryStockMovement(id=str(uuid.uuid4()), tenant_id=self.tenant_id, item_id=item_id,
            location_id=location_id, lot_id=lot_id, operation_id=op.id, operation_sequence=sequence,
            logical_line_id=str(line), source_type=source_type, source_id=source_id,
            movement_type="in" if delta > 0 else "out", quantity_delta=delta,
            unit_cost=cost, reason=reason, notes=json.dumps({"actor_id": self.actor_id}))
        self.db.add(movement)
        self.db.flush()
        return movement.id

    def create_operation(self, body, key):
        def execute(op):
            self._new(body)
            item_rows = self._lock_items(line.item_id for line in body.lines)
            self._lock_units([item.unit_id for item in item_rows] + [unit for line in body.lines for unit in (line.unit_id, line.measured_unit_id)])
            ids, normalized = [], []
            for index, line in enumerate(body.lines, 1):
                self._get(InventoryLocation, line.location_id)
                quantity = Decimal(self.preview(line)["quantity"])
                lot = self._get(InventoryLot, line.lot_id, lock=True) if line.lot_id else None
                if lot and (lot.item_id != line.item_id or lot.location_id != line.location_id):
                    raise FoundationInvalid("Lote nao pertence ao item/local informado.")
                incoming = body.kind in ("manual_in", "adjustment_in")
                if not incoming:
                    if lot and not self._eligible(lot) and body.kind != "loss":
                        raise FoundationConflict("Lote bloqueado ou vencido.", code="LotUnavailable")
                    if self._available(line.item_id, line.location_id, line.lot_id) < quantity:
                        raise FoundationConflict("Saldo livre insuficiente.", code="InventoryUnavailable")
                if body.kind == "transfer":
                    if not line.target_location_id or line.target_location_id == line.location_id:
                        raise FoundationInvalid("Transferencia exige local destino distinto.")
                    self._get(InventoryLocation, line.target_location_id)
                    if lot:
                        # A lot has one canonical location in F1: move only a full unreserved lot.
                        if quantity != self._physical(line.item_id, line.location_id, lot.id) or any(r.lot_id == lot.id for r in self._active_reservations(line.item_id)):
                            raise FoundationConflict("F1 transfere lote inteiro sem reservas; parcial exige subdivisao futura.")
                    ids.append(self._movement(op, index, len(ids)+1, line.item_id, line.location_id, line.lot_id, -quantity, line.unit_cost, "foundation_manual", op.id, body.reason))
                    ids.append(self._movement(op, index, len(ids)+1, line.item_id, line.target_location_id, line.lot_id, quantity, line.unit_cost, "foundation_manual", op.id, body.reason))
                    if lot:
                        lot.location_id, lot.version = line.target_location_id, lot.version + 1
                else:
                    if line.target_location_id:
                        raise FoundationInvalid("Destino permitido apenas em transferencia.")
                    ids.append(self._movement(op, index, len(ids)+1, line.item_id, line.location_id, line.lot_id,
                        quantity if incoming else -quantity, line.unit_cost, "foundation_manual", op.id, body.reason))
                normalized.append({"line": index, "quantity": quantity, "item_id": line.item_id, "lot_id": line.lot_id})
            return {"id": op.id, "kind": body.kind, "business_key": body.business_key, "version": 1, "status": "committed", "movement_ids": ids, "lines": normalized}
        return self._command("operations", key, body, body.kind, body.business_key, execute)

    def reserve(self, body, key):
        def execute(op):
            self._new(body)
            if body.source_type == "order":
                from backend.models.order import Order
                order = self._get(Order, body.source_id, lock=True)
                if getattr(order.status, "value", order.status) in ("cancelled", "refunded", "delivered", "on_the_way", "ready_for_pickup"):
                    raise FoundationConflict("Pedido nao aceita nova reserva.", code="OrderNotReservable")
            item = self._lock_items([body.item_id])[0]
            self._get(InventoryLocation, body.location_id)
            if body.unit_id != item.unit_id:
                raise FoundationInvalid("Reserva exige quantidade na unidade base do item.")
            self._lock_units([body.unit_id])
            self._unit(body.unit_id)
            if body.expires_at and body.expires_at <= utcnow():
                raise FoundationInvalid("Expiracao precisa ser futura.")
            lot = self._get(InventoryLot, body.lot_id, lock=True) if body.lot_id else None
            if lot and (lot.item_id != item.id or lot.location_id != body.location_id or not self._eligible(lot)):
                raise FoundationConflict("Lote indisponivel para reserva.")
            # Unallocated reservation in F1 refers to the explicit legacy no-lot bucket.
            if self._available(item.id, body.location_id, body.lot_id) < body.quantity:
                raise FoundationConflict("Saldo livre insuficiente para reserva.")
            row = InventoryReservation(id=str(uuid.uuid4()), tenant_id=self.tenant_id, actor_id=self.actor_id,
                business_key=body.business_key, item_id=item.id, lot_id=body.lot_id, location_id=body.location_id,
                operation_id=op.id, source_type=body.source_type, source_id=body.source_id,
                quantity=body.quantity, expires_at=body.expires_at, status="active", version=1)
            self.db.add(row)
            self.db.flush()
            return self._reservation_output(row)
        return self._command("reservations", key, body, "reservation", body.business_key, execute)

    @staticmethod
    def _reservation_output(row):
        return output({name: getattr(row, name) for name in ("id", "item_id", "lot_id", "location_id", "business_key", "source_type", "source_id", "quantity", "expires_at", "status", "version")})

    def release(self, reservation_id, body, key):
        def execute(op):
            initial = self._get(InventoryReservation, reservation_id)
            self._lock_items([initial.item_id])
            row = self._get(InventoryReservation, reservation_id, lock=True)
            if row.version != body.expected_version:
                raise FoundationConflict("Versao da reserva divergente.", code="VersionConflict")
            if row.status != "active":
                raise FoundationConflict("Reserva nao esta ativa.")
            row.status, row.version = "released", row.version + 1
            self.db.flush()
            return self._reservation_output(row)
        return self._command(f"reservations/{reservation_id}/release", key, body, "reservation_release", f"{reservation_id}:{body.expected_version}", execute)

    def list_reservations(self, cursor=None, limit=500):
        return self._page(self._query(InventoryReservation), InventoryReservation, self._reservation_output, cursor, limit)

    def balances(self, item_id=None):
        query = self._query(InventoryStockMovement)
        if item_id:
            self._get(InventoryItem, item_id)
            query = query.filter(InventoryStockMovement.item_id == item_id)
        grouped = query.with_entities(InventoryStockMovement.item_id, InventoryStockMovement.location_id,
            InventoryStockMovement.lot_id, func.sum(InventoryStockMovement.quantity_delta)).group_by(
            InventoryStockMovement.item_id, InventoryStockMovement.location_id, InventoryStockMovement.lot_id).all()
        reservations = self._active_reservations(item_id)
        items = []
        for item, location, lot_id, physical in grouped:
            lot = self._get(InventoryLot, lot_id) if lot_id else None
            reserved = sum((r.quantity for r in reservations if r.item_id == item and r.location_id == location and r.lot_id == lot_id), ZERO)
            usable = Decimal(physical) if lot is None or self._eligible(lot) else ZERO
            items.append({"item_id": item, "location_id": location, "lot_id": lot_id,
                "physical": Decimal(physical), "usable": usable, "reserved": reserved,
                "available": max(ZERO, usable-reserved), "legacy_without_lot": lot_id is None,
                "unit_id": self._get(InventoryItem, item).unit_id})
        return output({"items": items, "next_cursor": None})

    def reconciliation(self):
        balances = self.balances()["items"]
        return {"items": [{**row, "issues": [name for name, condition in (
            ("negative_physical", Decimal(row["physical"]) < 0),
            ("reserved_exceeds_usable", Decimal(row["reserved"]) > Decimal(row["usable"])),
            ("legacy_without_lot", row["legacy_without_lot"] and Decimal(row["physical"]) != 0),
        ) if condition]} for row in balances], "next_cursor": None, "read_only": True}

    def validate_legacy_out(self, item_id, location_id, quantity):
        """Caller must hold item lock; legacy operations can only touch no-lot stock."""
        if self._available(item_id, location_id, None) < Decimal(str(quantity)):
            raise FoundationConflict("Movimento legado excede saldo sem lote livre de reservas.", code="InventoryUnavailable")

    def release_order_reservations(self, order_id):
        """Flush-only cancellation bridge. Caller holds the order lock."""
        reservations = self._query(InventoryReservation).filter(
            InventoryReservation.source_type == "order", InventoryReservation.source_id == order_id,
            InventoryReservation.status == "active").all()
        if not reservations:
            return
        self._lock_items(row.item_id for row in reservations)
        rows = self._query(InventoryReservation).filter(
            InventoryReservation.source_type == "order", InventoryReservation.source_id == order_id,
            InventoryReservation.status == "active").order_by(InventoryReservation.id).with_for_update().all()
        for row in rows:
            version = row.version
            business = f"cancel:{order_id}:{row.id}:{version}"
            self.db.add(InventoryOperation(id=str(uuid.uuid4()), tenant_id=self.tenant_id,
                actor_id=self.actor_id, kind="reservation_release", business_key=business,
                idempotency_scope="legacy-order-cancel", idempotency_key=business,
                request_hash=hashlib.sha256(business.encode()).hexdigest(), status="committed", version=1,
                result_json={"reservation_id":row.id,"reason":"order_cancelled","released_quantity":format(row.quantity,"f")},
                committed_at=utcnow()))
            row.status, row.version = "released", version+1
        self.db.flush()

    def consume_legacy_sale(self, order_id, requirements, unit_costs, *, source_type="foundation_order_sale", operation_kind="order_sale", identity_scope="legacy-order"):
        """Flush-only bridge, caller owns order/item locks and commit/rollback."""
        handled = set()
        now = utcnow()
        for item_id, required in sorted(requirements.items()):
            lots = self._query(InventoryLot).filter(InventoryLot.item_id == item_id).with_for_update().all()
            reservations = self._active_reservations(item_id)
            if not lots and not reservations:
                continue
            handled.add(item_id)
            prior = self._query(InventoryOperation).filter(InventoryOperation.kind == operation_kind, InventoryOperation.business_key == f"{order_id}:{item_id}").first()
            if prior:
                continue
            op = InventoryOperation(id=str(uuid.uuid4()), tenant_id=self.tenant_id, actor_id=self.actor_id,
                kind=operation_kind, business_key=f"{order_id}:{item_id}", idempotency_scope=identity_scope,
                idempotency_key=f"{order_id}:{item_id}", request_hash=hashlib.sha256(f"{order_id}:{item_id}".encode()).hexdigest(), status="pending", version=1)
            self.db.add(op)
            self.db.flush()
            eligible = [lot for lot in lots if self._eligible(lot, now)]
            def fefo(lot):
                return self._lot_deadline(lot), aware(lot.received_at), lot.id
            eligible.sort(key=fefo)
            buckets = [(lot.location_id, lot.id) for lot in eligible]
            legacy_locations = self._query(InventoryStockMovement).filter(InventoryStockMovement.item_id == item_id, InventoryStockMovement.lot_id.is_(None)).with_entities(InventoryStockMovement.location_id).distinct().all()
            buckets += [(row[0], None) for row in legacy_locations]
            own = [r for r in reservations if r.source_type == "order" and r.source_id == order_id]
            # Explicitly allocated reservations precede otherwise free FEFO stock.
            buckets.sort(key=lambda bucket: not any(r.location_id == bucket[0] and r.lot_id == bucket[1] for r in own))
            remaining, ids, used, reservation_consumptions = Decimal(str(required)), [], {}, []
            for location_id, lot_id in buckets:
                free = max(ZERO, self._available(item_id, location_id, lot_id, own_order=order_id))
                allocated = min(remaining, free)
                if allocated <= 0:
                    continue
                ids.append(self._movement(op, item_id, len(ids)+1, item_id, location_id, lot_id, -allocated,
                    Decimal(str(unit_costs.get(item_id, 0))), source_type, order_id, operation_kind))
                used[(location_id, lot_id)] = allocated
                remaining -= allocated
                if remaining <= 0:
                    break
            if remaining > 0:
                raise FoundationConflict("Saldo utilizavel livre insuficiente para pedido.", code="InventoryUnavailable")
            for reservation in own:
                bucket = (reservation.location_id, reservation.lot_id)
                taken = min(reservation.quantity, used.get(bucket, ZERO))
                if taken <= 0:
                    continue
                reservation_consumptions.append({"reservation_id": reservation.id, "quantity": format(taken, "f")})
                used[bucket] -= taken
                if taken == reservation.quantity:
                    reservation.status = "consumed"
                else:
                    reservation.quantity -= taken
                reservation.version += 1
            op.status, op.result_json, op.committed_at = "committed", {"movement_ids": ids, "reservation_consumptions": reservation_consumptions}, now
            self.db.flush()
        return handled

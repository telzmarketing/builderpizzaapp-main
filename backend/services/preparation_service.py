from decimal import Decimal
import hashlib
import json
import uuid
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from backend.core.exceptions import DomainError
from backend.models.preparation import InventoryOperationRecipe, InventoryOperationRecipeItem, PreparationOrder, PreparationExecution
from backend.models.inventory import InventoryItem, InventoryLocation, InventoryStockMovement, InventoryUnit
from backend.models.inventory_foundation import InventoryOperation, InventoryLot, InventoryReservation
from backend.services.inventory_foundation_service import InventoryFoundationService, utcnow

class PreparationInvalid(DomainError): http_status = 422
class PreparationConflict(DomainError): http_status = 409
class PreparationNotFound(DomainError): http_status = 404

def _d(v): return format(Decimal(v or 0), "f")
class PreparationService:
    transitions = {"approve": {"draft":"approved"}, "schedule":{"approved":"scheduled"}, "start":{"waiting":"in_progress","scheduled":"in_progress"}, "pause":{"in_progress":"paused","partially_completed":"paused"}, "resume":{"paused":"in_progress"}, "block":{"scheduled":"blocked","waiting":"blocked","in_progress":"blocked","paused":"blocked","partially_completed":"blocked"}, "unblock":{"blocked":"waiting"}, "cancel":{"draft":"cancelled","approved":"cancelled","scheduled":"cancelled","waiting":"cancelled","in_progress":"cancelled","paused":"cancelled","partially_completed":"cancelled","blocked":"cancelled"}}
    def __init__(self, db, tenant_id, actor_id): self.db,self.tenant_id,self.actor_id=db,tenant_id,actor_id
    def _q(self, model): return self.db.query(model).filter(model.tenant_id == self.tenant_id)
    def _order(self, oid, lock=False):
        q=self._q(PreparationOrder).filter(PreparationOrder.id==oid)
        if lock:q=q.with_for_update()
        row=q.first()
        if not row: raise PreparationNotFound("Ordem nao encontrada neste tenant.")
        return row
    def _out(self,o, execution_id=None):
        if execution_id is None:
            latest = self._q(PreparationExecution).filter_by(order_id=o.id).order_by(PreparationExecution.created_at.desc()).first()
            execution_id = latest.id if latest else None
        return {"id":o.id,"recipe_id":o.recipe_id,"target_quantity":_d(o.target_quantity),"produced_quantity":_d(o.produced_quantity),"lost_quantity":_d(o.lost_quantity),"discarded_quantity":_d(o.discarded_quantity),"status":o.status,"version":o.version,"execution_id":execution_id}
    def _recipe_out(self, recipe):
        return {
            "id": recipe.id,
            "name": recipe.name,
            "output_item_id": recipe.output_item_id,
            "output_unit_id": recipe.output_unit_id,
            "yield_quantity": _d(recipe.yield_quantity),
            "version_number": recipe.version_number,
            "active": recipe.active,
        }
    def create_recipe(self,b):
        if b.expected_version != 0: raise PreparationConflict("Criacao exige expected_version zero.")
        if not self._q(InventoryOperationRecipe).filter_by(name=b.name,version_number=1).first():
            r=InventoryOperationRecipe(id=uuid.uuid4().hex,tenant_id=self.tenant_id,name=b.name,output_item_id=b.output_item_id,output_unit_id=b.output_unit_id,yield_quantity=b.yield_quantity,version_number=1,instructions=b.instructions,created_by=self.actor_id)
            self.db.add(r); self.db.flush()
            for i in b.items:self.db.add(InventoryOperationRecipeItem(id=uuid.uuid4().hex,tenant_id=self.tenant_id,recipe_id=r.id,item_id=i.item_id,unit_id=i.unit_id,quantity=i.quantity,position=i.position))
            try:self.db.commit()
            except IntegrityError as e:self.db.rollback();raise PreparationConflict("Receita concorrente ou referencia invalida.") from e
            return self._recipe_out(r)
        raise PreparationConflict("Receita operacional ja existe.")
    def list_recipes(self, active=True):
        """List operational recipes available to this tenant's preparation plan."""
        query = self._q(InventoryOperationRecipe)
        if active is not None:
            query = query.filter(InventoryOperationRecipe.active.is_(active))
        recipes = query.order_by(
            InventoryOperationRecipe.name.asc(),
            InventoryOperationRecipe.version_number.desc(),
            InventoryOperationRecipe.id.asc(),
        ).all()
        return [self._recipe_out(recipe) for recipe in recipes]
    def create_order(self,b,key):
        if not key: raise PreparationInvalid("Idempotency-Key obrigatoria.")
        recipe=self._q(InventoryOperationRecipe).filter_by(id=b.recipe_id,active=True).first()
        if not recipe: raise PreparationNotFound("Receita operacional nao encontrada.")
        prior=self._q(PreparationOrder).filter_by(idempotency_key=key).first()
        if prior:return self._out(prior)
        o=PreparationOrder(id=uuid.uuid4().hex,tenant_id=self.tenant_id,recipe_id=recipe.id,target_quantity=b.target_quantity,status="draft",scheduled_for=b.scheduled_for,version=1,idempotency_key=key,actor_id=self.actor_id,notes=b.notes,created_at=datetime.now(timezone.utc),updated_at=datetime.now(timezone.utc))
        self.db.add(o)
        try:self.db.commit()
        except IntegrityError as e:self.db.rollback();raise PreparationConflict("Ordem concorrente.") from e
        return self._out(o)
    def list_orders(self,status=None):
        q=self._q(PreparationOrder)
        if status:q=q.filter(PreparationOrder.status==status)
        return {"items":[self._out(x) for x in q.order_by(PreparationOrder.created_at.desc()).limit(200).all()]}
    def get_order(self, oid):
        """Return the published order projection, constrained to this tenant."""
        return self._out(self._order(oid))
    def _weighted_input_cost(self, item_id, lot_id=None):
        """Return quantity-weighted cost from positive stock entries only.

        The calculation is deliberately tenant-scoped and ignores any cost
        supplied by the caller.  A lot filter is applied only when the
        allocation explicitly identifies a lot.
        """
        q = self._q(InventoryStockMovement).filter(
            InventoryStockMovement.item_id == item_id,
            InventoryStockMovement.quantity_delta > 0,
            InventoryStockMovement.unit_cost > 0,
        )
        if lot_id:
            q = q.filter(InventoryStockMovement.lot_id == lot_id)
        rows = q.with_for_update().all()
        quantity = sum((Decimal(row.quantity_delta) for row in rows), Decimal("0"))
        total_cost = sum(
            (Decimal(row.quantity_delta) * Decimal(row.unit_cost) for row in rows),
            Decimal("0"),
        )
        if quantity <= 0 or total_cost <= 0:
            raise PreparationInvalid(
                f"Custo positivo insuficiente para o insumo {item_id}"
                + (f" no lote {lot_id}." if lot_id else ".")
            )
        return quantity, total_cost, total_cost / quantity
    def recipe(self, oid):
        order = self._order(oid)
        recipe = self._q(InventoryOperationRecipe).filter_by(id=order.recipe_id, active=True).first()
        if not recipe:
            raise PreparationNotFound("Ficha operacional nao encontrada.")
        return {
            "preparation_order_id": order.id,
            "recipe_version_id": recipe.id,
            "executable": bool(recipe.items),
            "output_item_id": recipe.output_item_id,
            "target_quantity": _d(order.target_quantity),
            "output_unit_id": recipe.output_unit_id,
            "instructions": recipe.instructions,
            "preparation_steps": [],
            "ingredients": [{
                "inventory_item_id": item.item_id,
                "quantity": _d(item.quantity),
                "unit_id": item.unit_id,
                "inventory_item_name": None,
                "unit_symbol": None,
            } for item in recipe.items],
            "warnings": [],
        }
    def _validate_input_allocations(self, recipe, allocations, processed_quantity, foundation):
        """Validate the physical inputs against the operational recipe.

        The report payload is intentionally kept as the public ``list[dict]``
        contract, but it is not trusted as a source of recipe membership or
        quantity.  An allocation must identify the exact recipe item/unit
        pair, and a lot (when supplied) must belong to that item and location.
        The complete report must consume the recipe quantity scaled by the
        quantity processed in this report.
        """
        recipe_quantities = {}
        for recipe_item in recipe.items:
            key = (recipe_item.item_id, recipe_item.unit_id)
            recipe_quantities[key] = recipe_quantities.get(key, Decimal("0")) + Decimal(recipe_item.quantity)

        allocated_quantities = {}
        for allocation in allocations:
            if not isinstance(allocation, dict):
                raise PreparationInvalid("Cada consumo deve ser um objeto de alocacao.")
            item_id = allocation.get("item_id")
            unit_id = allocation.get("unit_id")
            try:
                quantity = Decimal(str(allocation.get("quantity") or 0))
            except (ArithmeticError, TypeError, ValueError) as exc:
                raise PreparationInvalid("Quantidade de consumo invalida.") from exc
            location_id = allocation.get("location_id")
            lot_id = allocation.get("lot_id")
            if not item_id or not unit_id or not quantity.is_finite() or quantity <= 0 or not location_id:
                raise PreparationInvalid("Cada consumo exige item, unidade, quantidade e local.")

            key = (item_id, unit_id)
            if key not in recipe_quantities:
                raise PreparationInvalid("Item e unidade do consumo nao pertencem a receita operacional.")

            item = foundation._get(InventoryItem, item_id, lock=True)
            unit = foundation._get(InventoryUnit, unit_id, lock=True)
            if item.id != item_id or unit.id != unit_id:
                raise PreparationInvalid("Item ou unidade do consumo nao pertence a este tenant.")
            foundation._get(InventoryLocation, location_id)
            if lot_id:
                lot = foundation._get(InventoryLot, lot_id, lock=True)
                if lot.item_id != item_id:
                    raise PreparationInvalid("Lote do consumo nao pertence ao item da receita.")
                if lot.location_id != location_id:
                    raise PreparationInvalid("Lote do consumo nao pertence ao local informado.")

            allocated_quantities[key] = allocated_quantities.get(key, Decimal("0")) + quantity

        scale = Decimal(processed_quantity) / Decimal(recipe.yield_quantity)
        for key, recipe_quantity in recipe_quantities.items():
            expected = recipe_quantity * scale
            actual = allocated_quantities.get(key, Decimal("0"))
            if actual != expected:
                raise PreparationInvalid(
                    "Quantidade consumida nao respeita a receita operacional "
                    f"para o item {key[0]} e unidade {key[1]}."
                )
        unexpected = set(allocated_quantities) - set(recipe_quantities)
        if unexpected:
            raise PreparationInvalid("Existe consumo de item ou unidade fora da receita operacional.")

    def command(self,oid,command,b,key):
        if not key: raise PreparationInvalid("Idempotency-Key obrigatoria.")
        o=self._order(oid,True)
        if b.expected_version != o.version: raise PreparationConflict("Versao da ordem divergente.")
        target=self.transitions.get(command,{}).get(o.status)
        if not target: raise PreparationConflict("Transicao de ordem invalida.")
        if command in {"block","cancel"} and not (b.reason or "").strip(): raise PreparationInvalid("Motivo obrigatorio.")
        if command == "approve":
            recipe = self._q(InventoryOperationRecipe).filter_by(id=o.recipe_id, active=True).first()
            if not recipe:
                raise PreparationNotFound("Receita operacional nao encontrada.")
            self._reserve_order_inputs(o, recipe)
        if command == "cancel":
            self._release_order_reservations(o)
        o.status=target;o.version+=1;o.notes=((o.notes or "")+"\n"+b.reason) if b.reason else o.notes
        self.db.commit();return self._out(o)

    def _reserve_order_inputs(self, order, recipe):
        """Reserve the recipe inputs atomically when the order is approved."""
        if self._q(InventoryReservation).filter(
            InventoryReservation.source_type == "preparation",
            InventoryReservation.source_id == order.id,
            InventoryReservation.status == "active",
        ).first():
            return
        quantities = {}
        scale = Decimal(order.target_quantity) / Decimal(recipe.yield_quantity)
        for recipe_item in recipe.items:
            key = (recipe_item.item_id, recipe_item.unit_id)
            quantities[key] = quantities.get(key, Decimal("0")) + Decimal(recipe_item.quantity) * scale
        item_ids = sorted({item_id for item_id, _ in quantities})
        foundation = InventoryFoundationService(self.db, self.tenant_id, self.actor_id)
        items = {item.id: item for item in foundation._lock_items(item_ids)}
        for item_id, unit_id in quantities:
            item = items[item_id]
            if item.unit_id != unit_id:
                raise PreparationInvalid("Unidade da receita nao corresponde a unidade-base do insumo.")
            location_id = item.default_location_id
            if not location_id:
                raise PreparationInvalid(f"O insumo {item_id} precisa de local padrao para reservar o preparo.")
            available = foundation._available(item_id, location_id, None)
            if available < quantities[(item_id, unit_id)]:
                raise PreparationConflict(f"Saldo insuficiente para reservar o insumo {item_id}.")
        operation_key = f"preparation-reservation:{order.id}"
        operation = InventoryOperation(
            id=uuid.uuid4().hex, tenant_id=self.tenant_id, kind="reservation",
            business_key=operation_key, idempotency_scope="preparation-reservation",
            idempotency_key=operation_key,
            request_hash=hashlib.sha256(operation_key.encode()).hexdigest(),
            status="committed", actor_id=self.actor_id, version=1,
            result_json={"order_id": order.id, "items": {item_id: _d(quantity) for (item_id, _), quantity in quantities.items()},
                         "reason": "preparation_order_approved"}, committed_at=utcnow(),
        )
        self.db.add(operation)
        for (item_id, unit_id), quantity in quantities.items():
            item = items[item_id]
            self.db.add(InventoryReservation(
                id=uuid.uuid4().hex, tenant_id=self.tenant_id,
                business_key=f"{operation_key}:{item_id}", item_id=item_id,
                location_id=item.default_location_id, lot_id=None, operation_id=operation.id,
                source_type="preparation", source_id=order.id, quantity=quantity,
                status="active", version=1, actor_id=self.actor_id,
            ))
        self.db.flush()

    def _release_order_reservations(self, order):
        reservations = self._q(InventoryReservation).filter(
            InventoryReservation.source_type == "preparation",
            InventoryReservation.source_id == order.id,
            InventoryReservation.status == "active",
        ).with_for_update().all()
        if not reservations:
            return
        operation_key = f"preparation-reservation-release:{order.id}:{order.version}"
        operation = InventoryOperation(
            id=uuid.uuid4().hex, tenant_id=self.tenant_id, kind="reservation_release",
            business_key=operation_key, idempotency_scope="preparation-reservation-release",
            idempotency_key=operation_key,
            request_hash=hashlib.sha256(operation_key.encode()).hexdigest(),
            status="committed", actor_id=self.actor_id, version=1,
            result_json={"order_id": order.id, "released": [row.id for row in reservations]}, committed_at=utcnow(),
        )
        self.db.add(operation)
        for row in reservations:
            row.status = "released"
            row.version += 1
        self.db.flush()

    def _consume_order_reservations(self, order_id, allocations):
        quantities = {}
        for allocation in allocations:
            item_id = allocation.get("item_id")
            quantities[item_id] = quantities.get(item_id, Decimal("0")) + Decimal(str(allocation.get("quantity") or 0))
        for item_id, quantity in quantities.items():
            rows = self._q(InventoryReservation).filter(
                InventoryReservation.source_type == "preparation",
                InventoryReservation.source_id == order_id,
                InventoryReservation.item_id == item_id,
                InventoryReservation.status == "active",
            ).order_by(InventoryReservation.id).with_for_update().all()
            if not rows:
                # Legacy orders created before reservation integration remain
                # executable; new approved orders always have these rows.
                continue
            remaining = quantity
            for row in rows:
                consumed = min(Decimal(row.quantity), remaining)
                row.quantity = Decimal(row.quantity) - consumed
                row.version += 1
                if row.quantity == 0:
                    row.status = "consumed"
                remaining -= consumed
                if remaining <= 0:
                    break
            if remaining > 0:
                raise PreparationConflict(f"Reserva insuficiente para consumir o insumo {item_id}.")
    def report(self,oid,b,key):
        if not key: raise PreparationInvalid("Idempotency-Key obrigatoria.")
        o=self._order(oid,True)
        existing = self._q(PreparationExecution).filter_by(order_id=oid,idempotency_key=key).first()
        if existing: return self._out(o, existing.id)
        if b.expected_version != o.version: raise PreparationConflict("Versao da ordem divergente.")
        if o.status not in {"in_progress","partially_completed"}: raise PreparationConflict("Ordem nao esta em execucao.")
        if b.produced_quantity+b.lost_quantity+b.discarded_quantity <= 0: raise PreparationInvalid("Apontamento vazio.")
        produced=Decimal(o.produced_quantity or 0)+b.produced_quantity; lost=Decimal(o.lost_quantity or 0)+b.lost_quantity; disc=Decimal(o.discarded_quantity or 0)+b.discarded_quantity
        if produced+lost+disc > Decimal(o.target_quantity): raise PreparationConflict("Apontamento supera quantidade alvo.")
        if not b.input_allocations:
            raise PreparationInvalid("Informe os consumos dos insumos para concluir a transformacao.")
        recipe = self._q(InventoryOperationRecipe).filter_by(id=o.recipe_id, active=True).first()
        if not recipe:
            raise PreparationNotFound("Receita operacional nao encontrada.")
        foundation = InventoryFoundationService(self.db, self.tenant_id, self.actor_id)
        processed_quantity = b.produced_quantity + b.lost_quantity + b.discarded_quantity
        self._validate_input_allocations(recipe, b.input_allocations, processed_quantity, foundation)
        output_lot = None
        try:
            output_item = foundation._get(InventoryItem, recipe.output_item_id, lock=True)
            if b.output_lot_id:
                output_lot = foundation._get(InventoryLot, b.output_lot_id, lock=True)
                if output_lot.item_id != output_item.id:
                    raise PreparationInvalid("Lote de saida nao pertence ao produto preparado.")
            else:
                if not b.output_location_id or not b.output_lot_code:
                    raise PreparationInvalid("Informe local e lote da preparacao.")
                foundation._get(InventoryLocation, b.output_location_id)
                output_lot = InventoryLot(
                    id=uuid.uuid4().hex, tenant_id=self.tenant_id, item_id=output_item.id,
                    location_id=b.output_location_id, lot_code=b.output_lot_code,
                    expires_on=b.expires_on.date() if b.expires_on else None,
                    actor_id=self.actor_id, status="available", version=1,
                )
                self.db.add(output_lot); self.db.flush()
            operation_key = f"preparation:{oid}:{key}"
            operation = InventoryOperation(
                id=uuid.uuid4().hex, tenant_id=self.tenant_id, kind="preparation",
                business_key=operation_key, idempotency_scope="preparation",
                idempotency_key=operation_key,
                request_hash=hashlib.sha256(json.dumps(b.model_dump(mode="json"), sort_keys=True).encode()).hexdigest(),
                status="pending", actor_id=self.actor_id, version=1,
            )
            self.db.add(operation); self.db.flush()
            movement_ids = []
            allocation_breakdown = []
            total_input_cost = Decimal("0")
            for index, allocation in enumerate(b.input_allocations, 1):
                item_id = allocation.get("item_id")
                quantity = Decimal(str(allocation.get("quantity") or 0))
                location_id = allocation.get("location_id")
                lot_id = allocation.get("lot_id")
                if not item_id or quantity <= 0 or not location_id:
                    raise PreparationInvalid("Cada consumo exige item, quantidade e local.")
                foundation._get(InventoryItem, item_id, lock=True)
                available = foundation._available(item_id, location_id, lot_id)
                if available < quantity:
                    raise PreparationConflict("Saldo insuficiente para a transformacao.")
                _, _, unit_cost = self._weighted_input_cost(item_id, lot_id)
                allocation_cost = quantity * unit_cost
                total_input_cost += allocation_cost
                allocation_breakdown.append({
                    "item_id": item_id,
                    "location_id": location_id,
                    "lot_id": lot_id,
                    "quantity": _d(quantity),
                    "unit_cost": _d(unit_cost),
                    "total_cost": _d(allocation_cost),
                })
                movement = InventoryStockMovement(
                    id=uuid.uuid4().hex, tenant_id=self.tenant_id, item_id=item_id,
                    location_id=location_id, lot_id=lot_id, operation_id=operation.id,
                    operation_sequence=index, logical_line_id=str(index),
                    source_type="preparation", source_id=oid, movement_type="out",
                    quantity_delta=-quantity, unit_cost=unit_cost,
                    reason="preparation_consumption", notes=json.dumps({"actor_id": self.actor_id}),
                )
                self.db.add(movement); movement_ids.append(movement.id)
            output_qty = Decimal(b.produced_quantity or 0)
            output_unit_cost = total_input_cost / output_qty if output_qty > 0 else Decimal("0")
            output_cost_total = output_qty * output_unit_cost
            output_movement = InventoryStockMovement(
                id=uuid.uuid4().hex, tenant_id=self.tenant_id, item_id=output_item.id,
                location_id=output_lot.location_id, lot_id=output_lot.id, operation_id=operation.id,
                operation_sequence=len(movement_ids) + 1, logical_line_id="output",
                source_type="preparation", source_id=oid, movement_type="in",
                quantity_delta=output_qty, unit_cost=output_unit_cost, reason="preparation_output",
                notes=json.dumps({"actor_id": self.actor_id, "portion_grams": str(b.portion_grams) if b.portion_grams else None}),
            )
            self.db.add(output_movement); movement_ids.append(output_movement.id)
            self._consume_order_reservations(oid, b.input_allocations)
            now = utcnow()
            operation.status, operation.committed_at = "committed", now
            operation.result_json = {
                "movement_ids": movement_ids,
                "output_lot_id": output_lot.id,
                "input_cost_total": _d(total_input_cost),
                "output_cost_total": _d(output_cost_total),
                "output_unit_cost": _d(output_unit_cost),
                "allocations": allocation_breakdown,
            }
            e=PreparationExecution(id=uuid.uuid4().hex,tenant_id=self.tenant_id,order_id=oid,produced_quantity=b.produced_quantity,lost_quantity=b.lost_quantity,discarded_quantity=b.discarded_quantity,output_lot_id=output_lot.id,output_lot_code=output_lot.lot_code,expires_on=output_lot.expires_on,portion_grams=b.portion_grams,prepared_at=b.prepared_at or now,idempotency_key=key,actor_id=self.actor_id,notes=b.notes,operation_id=operation.id)
            self.db.add(e);o.produced_quantity=produced;o.lost_quantity=lost;o.discarded_quantity=disc;o.status="partially_completed";o.version+=1
            self.db.commit();return self._out(o, e.id)
        except Exception:
            self.db.rollback()
            raise
    def complete(self,oid,b,key):
        o=self._order(oid,True)
        if b.expected_version != o.version: raise PreparationConflict("Versao da ordem divergente.")
        if Decimal(o.produced_quantity or 0)+Decimal(o.lost_quantity or 0)+Decimal(o.discarded_quantity or 0) != Decimal(o.target_quantity): raise PreparationConflict("Pendencia de producao exige apontamento ou reducao aprovada.")
        o.status="completed";o.version+=1;self.db.commit();return self._out(o)

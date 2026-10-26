from decimal import Decimal
import hashlib
import json
import uuid
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from backend.core.exceptions import DomainError
from backend.models.preparation import InventoryOperationRecipe, InventoryOperationRecipeItem, PreparationOrder, PreparationExecution
from backend.models.inventory import InventoryItem, InventoryLocation, InventoryStockMovement
from backend.models.inventory_foundation import InventoryOperation, InventoryLot
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
    def create_recipe(self,b):
        if b.expected_version != 0: raise PreparationConflict("Criacao exige expected_version zero.")
        if not self._q(InventoryOperationRecipe).filter_by(name=b.name,version_number=1).first():
            r=InventoryOperationRecipe(id=uuid.uuid4().hex,tenant_id=self.tenant_id,name=b.name,output_item_id=b.output_item_id,output_unit_id=b.output_unit_id,yield_quantity=b.yield_quantity,version_number=1,instructions=b.instructions,created_by=self.actor_id)
            self.db.add(r); self.db.flush()
            for i in b.items:self.db.add(InventoryOperationRecipeItem(id=uuid.uuid4().hex,tenant_id=self.tenant_id,recipe_id=r.id,item_id=i.item_id,unit_id=i.unit_id,quantity=i.quantity,position=i.position))
            try:self.db.commit()
            except IntegrityError as e:self.db.rollback();raise PreparationConflict("Receita concorrente ou referencia invalida.") from e
            return {"id":r.id,"name":r.name,"output_item_id":r.output_item_id,"output_unit_id":r.output_unit_id,"yield_quantity":_d(r.yield_quantity),"version_number":r.version_number,"active":r.active}
        raise PreparationConflict("Receita operacional ja existe.")
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
    def command(self,oid,command,b,key):
        if not key: raise PreparationInvalid("Idempotency-Key obrigatoria.")
        o=self._order(oid,True)
        if b.expected_version != o.version: raise PreparationConflict("Versao da ordem divergente.")
        target=self.transitions.get(command,{}).get(o.status)
        if not target: raise PreparationConflict("Transicao de ordem invalida.")
        if command in {"block","cancel"} and not (b.reason or "").strip(): raise PreparationInvalid("Motivo obrigatorio.")
        o.status=target;o.version+=1;o.notes=((o.notes or "")+"\n"+b.reason) if b.reason else o.notes
        self.db.commit();return self._out(o)
    def report(self,oid,b,key):
        if not key: raise PreparationInvalid("Idempotency-Key obrigatoria.")
        o=self._order(oid,True)
        if b.expected_version != o.version: raise PreparationConflict("Versao da ordem divergente.")
        if o.status not in {"in_progress","partially_completed"}: raise PreparationConflict("Ordem nao esta em execucao.")
        if b.produced_quantity+b.lost_quantity+b.discarded_quantity <= 0: raise PreparationInvalid("Apontamento vazio.")
        existing = self._q(PreparationExecution).filter_by(order_id=oid,idempotency_key=key).first()
        if existing: return self._out(o, existing.id)
        produced=Decimal(o.produced_quantity or 0)+b.produced_quantity; lost=Decimal(o.lost_quantity or 0)+b.lost_quantity; disc=Decimal(o.discarded_quantity or 0)+b.discarded_quantity
        if produced+lost+disc > Decimal(o.target_quantity): raise PreparationConflict("Apontamento supera quantidade alvo.")
        if not b.input_allocations:
            raise PreparationInvalid("Informe os consumos dos insumos para concluir a transformacao.")
        recipe = self._q(InventoryOperationRecipe).filter_by(id=o.recipe_id, active=True).first()
        if not recipe:
            raise PreparationNotFound("Receita operacional nao encontrada.")
        foundation = InventoryFoundationService(self.db, self.tenant_id, self.actor_id)
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
                movement = InventoryStockMovement(
                    id=uuid.uuid4().hex, tenant_id=self.tenant_id, item_id=item_id,
                    location_id=location_id, lot_id=lot_id, operation_id=operation.id,
                    operation_sequence=index, logical_line_id=str(index),
                    source_type="preparation", source_id=oid, movement_type="out",
                    quantity_delta=-quantity, unit_cost=Decimal(str(allocation.get("unit_cost") or 0)),
                    reason="preparation_consumption", notes=json.dumps({"actor_id": self.actor_id}),
                )
                self.db.add(movement); movement_ids.append(movement.id)
            output_qty = Decimal(b.produced_quantity or 0)
            output_movement = InventoryStockMovement(
                id=uuid.uuid4().hex, tenant_id=self.tenant_id, item_id=output_item.id,
                location_id=output_lot.location_id, lot_id=output_lot.id, operation_id=operation.id,
                operation_sequence=len(movement_ids) + 1, logical_line_id="output",
                source_type="preparation", source_id=oid, movement_type="in",
                quantity_delta=output_qty, unit_cost=Decimal("0"), reason="preparation_output",
                notes=json.dumps({"actor_id": self.actor_id, "portion_grams": str(b.portion_grams) if b.portion_grams else None}),
            )
            self.db.add(output_movement); movement_ids.append(output_movement.id)
            now = utcnow()
            operation.status, operation.committed_at = "committed", now
            operation.result_json = {"movement_ids": movement_ids, "output_lot_id": output_lot.id}
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

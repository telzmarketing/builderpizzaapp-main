from decimal import Decimal
import uuid
from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from backend.core.exceptions import DomainError
from backend.models.preparation import InventoryOperationRecipe, InventoryOperationRecipeItem, PreparationOrder, PreparationExecution

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
    def _out(self,o): return {"id":o.id,"recipe_id":o.recipe_id,"target_quantity":_d(o.target_quantity),"produced_quantity":_d(o.produced_quantity),"lost_quantity":_d(o.lost_quantity),"discarded_quantity":_d(o.discarded_quantity),"status":o.status,"version":o.version}
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
        if self._q(PreparationExecution).filter_by(order_id=oid,idempotency_key=key).first(): return self._out(o)
        produced=Decimal(o.produced_quantity or 0)+b.produced_quantity; lost=Decimal(o.lost_quantity or 0)+b.lost_quantity; disc=Decimal(o.discarded_quantity or 0)+b.discarded_quantity
        if produced+lost+disc > Decimal(o.target_quantity): raise PreparationConflict("Apontamento supera quantidade alvo.")
        e=PreparationExecution(id=uuid.uuid4().hex,tenant_id=self.tenant_id,order_id=oid,produced_quantity=b.produced_quantity,lost_quantity=b.lost_quantity,discarded_quantity=b.discarded_quantity,output_lot_id=b.output_lot_id,idempotency_key=key,actor_id=self.actor_id,notes=b.notes)
        self.db.add(e);o.produced_quantity=produced;o.lost_quantity=lost;o.discarded_quantity=disc;o.status="partially_completed";o.version+=1;self.db.commit();return self._out(o)
    def complete(self,oid,b,key):
        o=self._order(oid,True)
        if b.expected_version != o.version: raise PreparationConflict("Versao da ordem divergente.")
        if Decimal(o.produced_quantity or 0)+Decimal(o.lost_quantity or 0)+Decimal(o.discarded_quantity or 0) != Decimal(o.target_quantity): raise PreparationConflict("Pendencia de producao exige apontamento ou reducao aprovada.")
        o.status="completed";o.version+=1;self.db.commit();return self._out(o)

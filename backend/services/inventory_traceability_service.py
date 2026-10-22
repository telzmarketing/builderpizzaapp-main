from datetime import datetime, timezone
from decimal import Decimal
import uuid
from sqlalchemy.exc import IntegrityError
from backend.core.exceptions import DomainError
from backend.models.inventory_foundation import InventoryLot, InventoryOperation
from backend.models.inventory import InventoryUnit
from backend.models.inventory_traceability import InventoryLotOpening, InventoryLotGenealogy

class TraceabilityInvalid(DomainError):
    http_status = 422
class TraceabilityConflict(DomainError):
    http_status = 409
class TraceabilityNotFound(DomainError):
    http_status = 404

def iso(value): return value.isoformat() if value else None

class InventoryTraceabilityService:
    def __init__(self, db, tenant_id, actor_id): self.db, self.tenant_id, self.actor_id = db, tenant_id, actor_id
    def _lot(self, lot_id, lock=False):
        q = self.db.query(InventoryLot).filter(InventoryLot.tenant_id == self.tenant_id, InventoryLot.id == lot_id)
        if lock: q = q.with_for_update()
        row = q.first()
        if not row: raise TraceabilityNotFound("Lote nao encontrado neste tenant.")
        return row
    def open_lot(self, lot_id, body, key):
        if not key or len(key) > 200: raise TraceabilityInvalid("Idempotency-Key obrigatoria.")
        if body.opened_at.tzinfo is None or body.opened_at.utcoffset() is None: raise TraceabilityInvalid("Abertura exige fuso horario.")
        if body.resulting_expires_at and (body.resulting_expires_at.tzinfo is None or body.resulting_expires_at.utcoffset() is None): raise TraceabilityInvalid("Validade resultante exige fuso horario.")
        lot = self._lot(lot_id, True)
        previous = self.db.query(InventoryLotOpening).filter_by(tenant_id=self.tenant_id, lot_id=lot_id, idempotency_key=key).first()
        if previous: return self._opening(previous)
        if body.resulting_expires_at and body.resulting_expires_at < body.opened_at: raise TraceabilityInvalid("Validade resultante anterior a abertura.")
        if lot.expires_on and body.resulting_expires_at and body.resulting_expires_at.date() > lot.expires_on: raise TraceabilityInvalid("Abertura nao pode ampliar validade original.")
        if body.expected_version and lot.version != body.expected_version: raise TraceabilityConflict("Versao do lote divergente.")
        row = InventoryLotOpening(id=str(uuid.uuid4()), tenant_id=self.tenant_id, lot_id=lot_id, opened_at=body.opened_at, rule_code=body.effective_rule_code, resulting_expires_at=body.resulting_expires_at, idempotency_key=key, actor_id=self.actor_id, notes=body.notes or body.container_code)
        self.db.add(row)
        if body.resulting_expires_at and (lot.effective_expires_at is None or body.resulting_expires_at < lot.effective_expires_at): lot.effective_expires_at = body.resulting_expires_at
        lot.version += 1
        try: self.db.commit()
        except IntegrityError as exc: self.db.rollback(); raise TraceabilityConflict("Abertura concorrente ou chave reutilizada.") from exc
        return self._opening(row)
    def _opening(self, row): return {"id":row.id,"lot_id":row.lot_id,"opened_at":iso(row.opened_at),"rule_code":row.rule_code,"resulting_expires_at":iso(row.resulting_expires_at),"actor_id":row.actor_id}
    def add_genealogy(self, body, key):
        if not key: raise TraceabilityInvalid("Idempotency-Key obrigatoria.")
        source, target = self._lot(body.source_lot_id), self._lot(body.target_lot_id)
        if source.id == target.id or source.item_id != target.item_id: raise TraceabilityInvalid("Lotes de origem e destino incompativeis.")
        operation = self.db.query(InventoryOperation).filter_by(tenant_id=self.tenant_id, id=body.operation_id).first()
        if not operation: raise TraceabilityNotFound("Operacao nao encontrada neste tenant.")
        unit = self.db.query(InventoryUnit).filter_by(tenant_id=self.tenant_id, id=body.unit_id).first()
        if not unit: raise TraceabilityNotFound("Unidade nao encontrada neste tenant.")
        prior = self.db.query(InventoryLotGenealogy).filter_by(tenant_id=self.tenant_id, operation_id=body.operation_id, source_lot_id=body.source_lot_id, target_lot_id=body.target_lot_id).first()
        if prior: return self._genealogy(prior)
        row = InventoryLotGenealogy(id=str(uuid.uuid4()), tenant_id=self.tenant_id, source_lot_id=source.id, target_lot_id=target.id, operation_id=operation.id, quantity=body.quantity, unit_id=unit.id, relation_type=body.relation_type, actor_id=self.actor_id)
        self.db.add(row)
        try: self.db.commit()
        except IntegrityError as exc: self.db.rollback(); raise TraceabilityConflict("Genealogia concorrente ou ja registrada.") from exc
        return self._genealogy(row)
    def _genealogy(self, row): return {"id":row.id,"source_lot_id":row.source_lot_id,"target_lot_id":row.target_lot_id,"operation_id":row.operation_id,"quantity":format(row.quantity,"f"),"unit_id":row.unit_id,"relation_type":row.relation_type,"actor_id":row.actor_id,"created_at":iso(row.created_at)}
    def genealogy(self, lot_id):
        self._lot(lot_id)
        rows = self.db.query(InventoryLotGenealogy).filter(InventoryLotGenealogy.tenant_id == self.tenant_id, (InventoryLotGenealogy.source_lot_id == lot_id) | (InventoryLotGenealogy.target_lot_id == lot_id)).order_by(InventoryLotGenealogy.created_at, InventoryLotGenealogy.id).all()
        return {"items":[self._genealogy(row) for row in rows]}

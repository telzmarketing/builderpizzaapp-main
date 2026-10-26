from __future__ import annotations
from datetime import datetime, timedelta, timezone
import uuid
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from backend.core.exceptions import DomainError, OrderNotFound
from backend.core.tenant_context import TenantContext
from backend.models.order import Order
from backend.models.kds_production import ProductionUnit, ProductionAttempt, KdsOperatorState, KdsAssignment, ProductionAttemptConsumption
from backend.models.cmv import OrderItemCmvSnapshot
from backend.models.inventory_foundation import InventoryOperation
from backend.services.inventory_foundation_service import InventoryFoundationService, FoundationConflict
from decimal import Decimal
from backend.models.tenant import Tenant
from backend.models.inventory import InventoryItem, InventoryStockMovement
from backend.models.rbac import AdminAuditLog
from backend.models.product import Product


class KdsStockConflict(DomainError):
    http_status = 409


def ensure_kds_units_ready(db: Session, tenant_id: str, order_id: str) -> None:
    """Legacy orders without physical units retain their published flow."""
    if db.query(ProductionUnit.id).filter(
        ProductionUnit.tenant_id == tenant_id, ProductionUnit.order_id == order_id,
        ProductionUnit.state.notin_(("ready", "cancelled")),
    ).first():
        raise KdsStockConflict(
            "Conclua a conferencia de estoque, producao e forno das unidades antes de liberar o pedido.",
            code="KdsUnitsPending",
        )


class KdsProductionService:
    def __init__(self, db: Session, context: TenantContext): self.db, self.tenant_id = db, context.tenant_id
    def _now(self): return datetime.now(timezone.utc)
    def _unit(self, task_id, lock=False):
        q = self.db.query(ProductionAttempt).join(ProductionUnit).filter(ProductionAttempt.tenant_id==self.tenant_id, ProductionAttempt.id==task_id)
        if lock: q=q.populate_existing().with_for_update()
        row=q.first()
        if not row: raise DomainError("Tarefa nao encontrada.", code="KdsTaskNotFound")
        return row
    def _check(self, attempt, expected):
        if attempt.version != expected: raise KdsStockConflict("A tarefa foi alterada por outro operador.", code="VersionConflict")
    def _payload(self, a):
        u=a.unit
        consumption = self.db.query(ProductionAttemptConsumption).filter_by(tenant_id=self.tenant_id, attempt_id=a.id).all()
        operation_ids = [row.operation_id for row in consumption if row.operation_id]
        snapshot = self.db.query(OrderItemCmvSnapshot).filter_by(tenant_id=self.tenant_id, order_item_id=u.order_item_id).first()
        return {"id":a.id,"task_id":a.id,"production_unit_id":u.id,"order_id":u.order_id,"order_item_id":u.order_item_id,"unit_index":u.unit_index,"attempt_id":a.id,"attempt_number":a.attempt_number,"state":a.state,"version":a.version,"operator_id":a.operator_id,"requires_oven":u.requires_oven,"assigned_at":a.assigned_at,"started_at":a.started_at,"assembly_finished_at":a.assembly_finished_at,"completed_at":a.completed_at,"consumption_mode":a.stock_consumption_mode or ("attempts" if consumption else "pending"),"consumption_operation_id":operation_ids[0] if operation_ids else None,"composition_revision_id":snapshot.snapshot_id if snapshot else None,"server_time":self._now(),"stock_requested_at":a.stock_requested_at,"stock_check_after":a.stock_check_after,"blocked_reason":a.blocked_reason,"product_name":snapshot.product_name if snapshot else None,"created_at":a.created_at,"priority":0}

    @staticmethod
    def _aware(value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

    def _lock_station(self):
        # A durable tenant mutex orders stock requests across browser sessions/workers.
        if not self.db.query(Tenant).filter(Tenant.id == self.tenant_id).with_for_update().first():
            raise KdsStockConflict("Estabelecimento indisponivel.", code="TenantUnavailable")

    def _audit(self, attempt, actor_id, old_state, reason):
        self.db.add(AdminAuditLog(id=str(uuid.uuid4()), tenant_id=self.tenant_id,
            user_id=actor_id, action="status_change", module_key="cozinha",
            entity_type="production_attempt", entity_id=attempt.id,
            old_value=old_state, new_value=f"{attempt.state}: {reason}"))

    def _order_for_attempt(self, attempt):
        order = self.db.query(Order).filter_by(tenant_id=self.tenant_id, id=attempt.unit.order_id).populate_existing().with_for_update().first()
        if not order or str(getattr(order.status, "value", order.status)) not in {"paid", "pago", "preparing"}:
            raise KdsStockConflict("Pedido nao esta elegivel para producao.", code="KdsOrderNotEligible")
        return order

    def _owner(self, attempt, actor_id):
        if attempt.operator_id and attempt.operator_id != actor_id:
            raise KdsStockConflict("Tarefa reservada para outro operador.", code="KdsTaskOwned")

    def start_stock_check(self, task_id, actor_id, body):
        self._lock_station()
        a = self._unit(task_id, True)
        self._owner(a, actor_id)
        self._order_for_attempt(a)
        # Replaying start never creates another timer, movement or attempt.
        if a.stock_requested_at is not None:
            return self._payload(a)
        self._check(a, body.expected_version)
        if a.state != "queued":
            raise KdsStockConflict("Tarefa nao esta na fila.", code="StateConflict")
        now = self._now()
        a.stock_requested_at, a.stock_check_after = now, now + timedelta(seconds=5)
        a.operator_id, a.assigned_at = actor_id, a.assigned_at or now
        a.state = a.unit.state = "checking_stock"
        a.version += 1
        a.unit.version += 1
        self._audit(a, actor_id, "queued", "Conferencia de estoque solicitada; sem baixa durante cinco segundos.")
        self.db.commit()
        return self._payload(a)

    def confirm_stock(self, task_id, actor_id, body):
        self._lock_station()
        target = self._unit(task_id, True)
        self._owner(target, actor_id)
        if target.state != "checking_stock":
            if target.stock_requested_at is not None:
                return self._payload(target)
            raise KdsStockConflict("Inicie a conferencia antes de confirmar.", code="StateConflict")
        self._check(target, body.expected_version)
        now = self._now()
        if not target.stock_check_after or self._aware(target.stock_check_after) > now:
            raise KdsStockConflict("Aguarde os cinco segundos da conferencia.", code="StockCheckPending")
        # A later browser cannot overtake earlier requests merely by confirming first.
        pending = self.db.query(ProductionAttempt).filter(
            ProductionAttempt.tenant_id == self.tenant_id,
            ProductionAttempt.state == "checking_stock",
            ProductionAttempt.stock_check_after <= now,
        ).order_by(ProductionAttempt.stock_requested_at, ProductionAttempt.id).populate_existing().with_for_update().all()
        for a in pending:
            try:
                with self.db.begin_nested():
                    self._order_for_attempt(a)
                    result = self.consume_attempt(a.id, a.operator_id)
                    a.stock_consumption_mode = result.get("mode", "attempts")
                    a.state = a.unit.state = "assembling"
                    a.started_at = now
                    a.blocked_reason = None
                    a.version += 1
                    a.unit.version += 1
                    self._audit(a, a.operator_id, "checking_stock", "Estoque disponivel; iniciando preparo.")
            except DomainError as exc:
                a.state = a.unit.state = "aguardando_analise"
                a.blocked_reason = exc.message
                a.version += 1
                a.unit.version += 1
                self._audit(a, a.operator_id, "checking_stock", exc.message)
        self.db.commit()
        return self._payload(target)

    def return_to_service(self, task_id, actor_id, body):
        self._lock_station()
        a = self._unit(task_id, True)
        self._owner(a, actor_id)
        if a.state == "atendimento":
            return self._payload(a)
        self._check(a, body.expected_version)
        if a.state != "aguardando_analise":
            raise KdsStockConflict("Somente pendencias de estoque retornam ao atendimento.", code="StateConflict")
        a.state = a.unit.state = "atendimento"
        a.version += 1
        a.unit.version += 1
        self._audit(a, actor_id, "aguardando_analise", body.reason or a.blocked_reason or "Retorno solicitado pelo pizzaiolo.")
        self.db.commit()
        return self._payload(a)

    def stock_alerts(self):
        return [self._payload(a) for a in self.db.query(ProductionAttempt).filter(
            ProductionAttempt.tenant_id == self.tenant_id,
            ProductionAttempt.state.in_(("aguardando_analise", "atendimento")),
        ).order_by(ProductionAttempt.stock_requested_at, ProductionAttempt.id).all()]
    def initialize_order(self, order_id: str, actor_id: str, *, commit=True):
        order=self.db.query(Order).filter(Order.tenant_id==self.tenant_id,Order.id==order_id).with_for_update().first()
        if not order: raise OrderNotFound(order_id)
        for item in order.items:
            qty=max(0,int(item.quantity or 0))
            for idx in range(1,qty+1):
                unit=self.db.query(ProductionUnit).filter_by(tenant_id=self.tenant_id,order_item_id=item.id,unit_index=idx).first()
                if unit: continue
                product = self.db.query(Product).filter_by(tenant_id=self.tenant_id, id=item.product_id).first()
                # Unknown legacy product types retain the conservative oven gate.
                requires_oven = not (product and product.product_type == "drink")
                unit=ProductionUnit(id=str(uuid.uuid4()),tenant_id=self.tenant_id,order_id=order.id,order_item_id=item.id,unit_index=idx,state="queued",requires_oven=requires_oven)
                self.db.add(unit); self.db.flush()
                self.db.add(ProductionAttempt(id=str(uuid.uuid4()),tenant_id=self.tenant_id,production_unit_id=unit.id,attempt_number=1,state="queued"))
        if commit: self.db.commit()
        else: self.db.flush()
        return self.queue(actor_id)
    def queue(self, actor_id):
        rows=self.db.query(ProductionAttempt).join(ProductionUnit).options(joinedload(ProductionAttempt.unit)).filter(ProductionAttempt.tenant_id==self.tenant_id,ProductionAttempt.state.notin_(("ready","cancelled"))).filter((ProductionAttempt.operator_id==actor_id) | (ProductionAttempt.operator_id.is_(None))).order_by(ProductionAttempt.created_at).all()
        return [self._payload(r) for r in rows]
    def all_queued(self):
        rows=self.db.query(ProductionAttempt).join(ProductionUnit).options(joinedload(ProductionAttempt.unit)).filter(ProductionAttempt.tenant_id==self.tenant_id,ProductionAttempt.state.in_(("queued","checking_stock","aguardando_analise","atendimento","assembling","assembled","baking","checking"))).order_by(ProductionAttempt.created_at).all()
        return [self._payload(r) for r in rows]
    def presence(self, actor_id, body):
        row=self.db.query(KdsOperatorState).filter_by(tenant_id=self.tenant_id,user_id=actor_id,station_id=body.station_id).with_for_update().first()
        if row is None:
            if body.expected_version != 0: raise DomainError("Estado inexistente.",code="VersionConflict")
            row=KdsOperatorState(id=str(uuid.uuid4()),tenant_id=self.tenant_id,user_id=actor_id,station_id=body.station_id,requested_state=body.effective_state)
            self.db.add(row)
        else:
            self._check(row,body.expected_version); row.requested_state=body.effective_state; row.version+=1
        self.db.commit(); return {"id":row.id,"state":row.requested_state,"station_id":row.station_id,"version":row.version,"last_heartbeat_at":row.last_heartbeat_at}
    def heartbeat(self, actor_id, body):
        row=self.db.query(KdsOperatorState).filter_by(tenant_id=self.tenant_id,user_id=actor_id,station_id=body.station_id).with_for_update().first()
        if not row: raise DomainError("Presenca operacional nao encontrada.",code="OperatorStateNotFound")
        self._check(row,body.expected_version); row.operational_session_id=body.operational_session_id; row.last_heartbeat_at=self._now(); self.db.commit()
        return {"server_time":self._now(),"state":row.requested_state,"version":row.version,"operational_session_id":row.operational_session_id}
    def command(self, task_id, actor_id, body, command):
        if command == "start": return self.start_stock_check(task_id, actor_id, body)
        if command == "confirm-stock": return self.confirm_stock(task_id, actor_id, body)
        if command == "return-to-service": return self.return_to_service(task_id, actor_id, body)
        self._lock_station()
        a=self._unit(task_id,True); self._check(a,body.expected_version); now=self._now()
        self._owner(a, actor_id)
        self._order_for_attempt(a)
        transitions={"start":("queued","assembling"),"finish-assembly":("assembling","assembled"),"start-oven":("assembled","baking"),"complete-oven":("baking","checking"),"check":("checking","ready")}
        if command == "check" and not a.unit.requires_oven: transitions["check"] = ("assembled", "ready")
        expected,new=transitions[command]
        if command=="check" and not body.approved: new="checking"
        if a.state!=expected: raise DomainError("Etapa incompativel com o estado atual.",code="StateConflict")
        if command=="start-oven" and not a.unit.requires_oven: raise DomainError("Esta unidade nao exige forno.",code="StateConflict")
        if command=="check" and not body.approved and not body.reason: raise DomainError("Motivo obrigatorio para reprovacao.",code="ReasonRequired")
        if command == "finish-assembly" and not a.stock_consumption_mode:
            # Compatibility for assemblies begun before the stock gate migration.
            result = self.consume_attempt(a.id, actor_id)
            a.stock_consumption_mode = result.get("mode", "attempts")
        a.state=new; a.version+=1
        if command=="start": a.operator_id=actor_id; a.started_at=now; a.assigned_at=a.assigned_at or now
        elif command=="finish-assembly": a.assembly_finished_at=now
        elif command=="start-oven": a.oven_started_at=now
        elif command=="complete-oven": a.oven_finished_at=now
        elif command=="check": a.checked_at=now; a.check_reason=body.reason; a.completed_at=now if body.approved else None
        a.unit.state=new; a.unit.version+=1
        self.db.commit(); self.db.refresh(a); return self._payload(a)

    def consume_attempt(self, attempt_id: str, actor_id: str):
        """Consume the frozen CMV composition once for this physical unit."""
        attempt = self._unit(attempt_id, True)
        existing = self.db.query(ProductionAttemptConsumption).filter_by(
            tenant_id=self.tenant_id, attempt_id=attempt.id).count()
        if existing:
            return {"consumed": True, "reason": "already_consumed", "lines": existing}
        item_snapshot = self.db.query(OrderItemCmvSnapshot).filter_by(
            tenant_id=self.tenant_id, order_item_id=attempt.unit.order_item_id).first()
        if not item_snapshot or item_snapshot.missing_recipe:
            raise DomainError("Composicao tecnica congelada indisponivel para consumo.", code="RecipeSnapshotRequired")
        item_quantity = Decimal(str(item_snapshot.quantity or 1))
        if item_quantity <= 0:
            raise DomainError("Quantidade congelada invalida.", code="RecipeSnapshotInvalid")
        requirements = {}
        costs = {}
        for line in item_snapshot.ingredients:
            if not line.inventory_item_id:
                continue
            quantity = Decimal(str(line.quantity or 0)) / item_quantity
            if quantity > 0:
                requirements[line.inventory_item_id] = requirements.get(line.inventory_item_id, Decimal("0")) + quantity
                costs[line.inventory_item_id] = Decimal(str(line.unit_cost or 0))
        if not requirements:
            raise DomainError("Composicao tecnica sem insumos consumiveis.", code="RecipeSnapshotEmpty")
        # Same lock order as the legacy order writer and foundation operations.
        items = self.db.query(InventoryItem).filter(
            InventoryItem.tenant_id == self.tenant_id, InventoryItem.id.in_(requirements),
        ).order_by(InventoryItem.id).with_for_update().all()
        if len(items) != len(requirements):
            raise FoundationConflict("Insumo da composicao nao pertence ao estabelecimento.", code="InventoryUnavailable")
        legacy = self.db.query(InventoryStockMovement).filter(
            InventoryStockMovement.tenant_id == self.tenant_id,
            InventoryStockMovement.source_id == attempt.unit.order_id,
            InventoryStockMovement.source_type.in_(("order_sale", "foundation_order_sale")),
        ).all()
        if legacy and attempt.attempt_number == 1:
            for item_id, required in requirements.items():
                covered = sum((-Decimal(str(m.quantity_delta)) for m in legacy if m.item_id == item_id), Decimal("0"))
                if covered < required:
                    raise FoundationConflict("Cobertura legada incompleta; atendimento deve conciliar a baixa.", code="LegacyCoverageIncomplete")
            return {"consumed": True, "reason": "legacy_covered", "mode": "legacy_covered", "lines": len(requirements)}
        foundation = InventoryFoundationService(self.db, self.tenant_id, actor_id)
        foundation.consume_legacy_sale(
            attempt.id, requirements, costs,
            source_type="foundation_production_attempt",
            operation_kind="production_attempt",
            identity_scope="kds-production-attempt",
            include_untracked=True,
            reservation_order_id=attempt.unit.order_id,
        )
        consumed_items = set(self.db.query(InventoryOperation).filter(
            InventoryOperation.tenant_id == self.tenant_id,
            InventoryOperation.kind == "production_attempt",
            InventoryOperation.business_key.like(f"{attempt.id}:%"),
        ).with_entities(InventoryOperation.business_key).all())
        if len(consumed_items) < len(requirements):
            raise FoundationConflict("Saldo utilizavel livre insuficiente para tentativa.", code="InventoryUnavailable")
        for item_id, quantity in requirements.items():
            op = self.db.query(InventoryOperation).filter_by(
                tenant_id=self.tenant_id, kind="production_attempt", business_key=f"{attempt.id}:{item_id}").first()
            if not op:
                raise FoundationConflict("Saldo fisico insuficiente para concluir o consumo da tentativa.", code="InventoryUnavailable")
            self.db.add(ProductionAttemptConsumption(
                id=str(uuid.uuid4()), tenant_id=self.tenant_id, attempt_id=attempt.id,
                inventory_item_id=item_id, quantity=quantity,
                unit_cost=costs.get(item_id, Decimal("0")),
                movement_ids=(op.result_json or {}).get("movement_ids", []),
                operation_id=op.id,
            ))
        self.db.flush()
        return {"consumed": True, "reason": "ok", "lines": len(requirements)}
    def remake(self, task_id, actor_id, body):
        a=self._unit(task_id,True); self._check(a,body.expected_version)
        order=self.db.query(Order).filter(Order.tenant_id==self.tenant_id,Order.id==a.unit.order_id).with_for_update().first()
        if not order or str(getattr(order.status,"value",order.status))!="preparing": raise DomainError("Refazimento tardio nao permitido.",code="LateReworkNotSupported",)
        if not body.reason: raise DomainError("Motivo obrigatorio.",code="ReasonRequired")
        a.state="cancelled"; a.version+=1; a.check_reason=body.reason
        new=ProductionAttempt(id=str(uuid.uuid4()),tenant_id=self.tenant_id,production_unit_id=a.production_unit_id,attempt_number=a.attempt_number+1,state="queued",previous_attempt_id=a.id)
        a.unit.state="queued"; a.unit.version+=1; self.db.add(new); self.db.commit(); self.db.refresh(new); return self._payload(new)
    def redistribute(self, body, actor_id):
        target_operator_id = body.effective_target_operator_id
        target=self.db.query(KdsOperatorState).filter_by(tenant_id=self.tenant_id,user_id=target_operator_id,requested_state="available").first()
        if not target: raise DomainError("Operador destino indisponivel.",code="OperatorUnavailable")
        result=[]
        for task_id in body.task_ids:
            a=self._unit(task_id,True); self._check(a,body.effective_versions.get(task_id,-1))
            if a.state != "queued":
                raise DomainError("Somente tarefas na fila podem ser redistribuidas.", code="StateConflict")
            old=self.db.query(KdsAssignment).filter_by(tenant_id=self.tenant_id,attempt_id=a.id,active=True).with_for_update().first()
            if old: old.active=False; old.released_at=self._now(); old.reason=body.reason
            a.operator_id=target_operator_id; a.assigned_at=self._now(); a.version+=1
            self.db.add(KdsAssignment(id=str(uuid.uuid4()),tenant_id=self.tenant_id,attempt_id=a.id,operator_id=target_operator_id,reason=body.reason)); result.append(self._payload(a))
        self.db.commit(); return {"tasks":result,"target_operator_id":target_operator_id}

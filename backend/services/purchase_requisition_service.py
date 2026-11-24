from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from backend.core.exceptions import DomainError, IdempotencyConflict
from backend.core.tenant_context import TenantContext
from backend.models.admin import AdminUser
from backend.models.inventory import InventoryItem, InventoryUnit
from backend.models.purchase_requisition import PurchaseRequisition, PurchaseRequisitionEvent, PurchaseRequisitionItem
from backend.models.rbac import AdminAuditLog
from backend.schemas.purchase_requisition import PurchaseRequisitionCreate, PurchaseRequisitionTransitionIn, PurchaseRequisitionUpdate
from backend.services.idempotency_service import IdempotencyService


class PurchaseRequisitionNotFound(DomainError):
    http_status = 404

    def __init__(self):
        super().__init__("Requisicao de compra nao encontrada.", code="PurchaseRequisitionNotFound")


class PurchaseRequisitionConflict(DomainError):
    http_status = 409


class PurchaseRequisitionService:
    TRANSITIONS = {
        "draft": {"submit": "submitted", "cancel": "cancelled"},
        "submitted": {"approve": "approved", "reject": "rejected", "cancel": "cancelled"},
        "approved": {"source": "sourcing", "cancel": "cancelled"},
        "sourcing": {"order": "ordered", "cancel": "cancelled"},
        "ordered": {"partial": "partially_fulfilled", "fulfill": "fulfilled", "cancel": "cancelled"},
        "partially_fulfilled": {"partial": "partially_fulfilled", "fulfill": "fulfilled"},
        "fulfilled": {}, "rejected": {}, "cancelled": {},
    }

    def __init__(self, db: Session, actor_id: str, tenant_context: TenantContext):
        self.db = db
        self.actor_id = actor_id
        self.tenant_id = tenant_context.tenant_id

    def list(self, status: str | None = None) -> list[PurchaseRequisition]:
        query = self.db.query(PurchaseRequisition).options(joinedload(PurchaseRequisition.items), joinedload(PurchaseRequisition.events)).filter(PurchaseRequisition.tenant_id == self.tenant_id)
        if status:
            query = query.filter(PurchaseRequisition.status == status)
        return query.order_by(PurchaseRequisition.created_at.desc()).limit(500).all()

    def get(self, requisition_id: str) -> PurchaseRequisition:
        row = self.db.query(PurchaseRequisition).options(joinedload(PurchaseRequisition.items), joinedload(PurchaseRequisition.events)).filter(PurchaseRequisition.tenant_id == self.tenant_id, PurchaseRequisition.id == requisition_id).first()
        if not row:
            raise PurchaseRequisitionNotFound()
        return row

    def create(self, body: PurchaseRequisitionCreate, key: str) -> PurchaseRequisition:
        claim = IdempotencyService(self.db, self.tenant_id).claim(key, "purchase_requisition_create", body.model_dump(mode="json"))
        if claim.replay_resource_id:
            return self.get(claim.replay_resource_id)
        try:
            self._validate_items(body.items)
            code = self._next_code()
            row = PurchaseRequisition(id=f"preq-{uuid.uuid4().hex[:14]}", tenant_id=self.tenant_id, code=code, requested_by_admin_id=self.actor_id, priority=body.priority, needed_by=body.needed_by, reason=body.reason, notes=body.notes)
            self.db.add(row)
            self.db.flush()
            self._replace_items(row, body.items)
            self._event(row, None, "draft", "created", None)
            self.db.flush()
            IdempotencyService(self.db, self.tenant_id).complete(claim.record, row.id, commit=False)
            self._audit(row, "created", None, "draft")
            self.db.commit()
            return self.get(row.id)
        except Exception:
            IdempotencyService(self.db, self.tenant_id).abandon(claim.record)
            raise

    def update(self, requisition_id: str, body: PurchaseRequisitionUpdate) -> PurchaseRequisition:
        row = self._locked(requisition_id)
        if row.status != "draft":
            raise PurchaseRequisitionConflict("Somente requisicoes em rascunho podem ser editadas.", code="PurchaseRequisitionNotEditable")
        if row.version != body.expected_version:
            raise PurchaseRequisitionConflict("A requisicao foi alterada por outro usuario.", code="PurchaseRequisitionVersionConflict")
        self._validate_items(body.items)
        row.priority, row.needed_by, row.reason, row.notes = body.priority, body.needed_by, body.reason, body.notes
        row.version += 1
        self._replace_items(row, body.items)
        self._event(row, "draft", "draft", "updated", None)
        self._audit(row, "updated", "draft", "draft")
        self.db.commit()
        return self.get(row.id)

    def transition(self, requisition_id: str, action: str, body: PurchaseRequisitionTransitionIn, key: str) -> PurchaseRequisition:
        row = self._locked(requisition_id)
        idem_payload = {"id": requisition_id, "action": action, **body.model_dump(mode="json")}
        claim = IdempotencyService(self.db, self.tenant_id).claim(key, f"purchase_requisition_{action}", idem_payload)
        if claim.replay_resource_id:
            return self.get(claim.replay_resource_id)
        try:
            if row.version != body.expected_version:
                raise PurchaseRequisitionConflict("A requisicao foi alterada por outro usuario.", code="PurchaseRequisitionVersionConflict")
            target = self.TRANSITIONS.get(row.status, {}).get(action)
            if not target:
                raise PurchaseRequisitionConflict(f"Transicao '{action}' nao permitida para o estado '{row.status}'.", code="PurchaseRequisitionInvalidTransition")
            if action == "approve" and row.requested_by_admin_id == self.actor_id:
                raise PurchaseRequisitionConflict("O solicitante nao pode aprovar a propria requisicao.", code="PurchaseRequisitionSelfApproval")
            previous = row.status
            row.status, row.version = target, row.version + 1
            self._event(row, previous, target, action, body.reason)
            self._audit(row, action, previous, target, body.reason)
            self.db.flush()
            IdempotencyService(self.db, self.tenant_id).complete(claim.record, row.id, commit=False)
            self.db.commit()
            return self.get(row.id)
        except Exception:
            IdempotencyService(self.db, self.tenant_id).abandon(claim.record)
            raise

    def _locked(self, requisition_id: str) -> PurchaseRequisition:
        row = self.db.query(PurchaseRequisition).options(joinedload(PurchaseRequisition.items)).filter(PurchaseRequisition.tenant_id == self.tenant_id, PurchaseRequisition.id == requisition_id).with_for_update().first()
        if not row:
            raise PurchaseRequisitionNotFound()
        return row

    def _validate_items(self, items) -> None:
        seen = set()
        for item in items:
            if item.item_id in seen:
                raise PurchaseRequisitionConflict("O mesmo insumo nao pode aparecer duas vezes na requisicao.", code="PurchaseRequisitionDuplicateItem")
            seen.add(item.item_id)
            if not self.db.query(InventoryItem.id).filter(InventoryItem.tenant_id == self.tenant_id, InventoryItem.id == item.item_id, InventoryItem.active.is_(True)).first():
                raise PurchaseRequisitionConflict("Insumo inexistente, inativo ou de outro tenant.", code="PurchaseRequisitionInvalidItem")
            if not self.db.query(InventoryUnit.id).filter(InventoryUnit.tenant_id == self.tenant_id, InventoryUnit.id == item.unit_id, InventoryUnit.active.is_(True)).first():
                raise PurchaseRequisitionConflict("Unidade inexistente, inativa ou de outro tenant.", code="PurchaseRequisitionInvalidUnit")

    def _replace_items(self, row, items) -> None:
        row.items.clear()
        for position, item in enumerate(items):
            row.items.append(PurchaseRequisitionItem(id=f"preqi-{uuid.uuid4().hex[:14]}", tenant_id=self.tenant_id, item_id=item.item_id, unit_id=item.unit_id, quantity=item.quantity, notes=item.notes, position=position))

    def _event(self, row, previous: str | None, target: str, action: str, reason: str | None) -> None:
        sequence = (max((event.sequence for event in row.events), default=0) + 1)
        row.events.append(PurchaseRequisitionEvent(id=f"preqe-{uuid.uuid4().hex[:14]}", tenant_id=self.tenant_id, sequence=sequence, from_status=previous, to_status=target, action=action, actor_admin_id=self.actor_id, reason=reason, snapshot={"version": row.version, "status": target}))

    def _audit(self, row, action: str, previous: str | None, target: str, reason: str | None = None) -> None:
        self.db.add(AdminAuditLog(id=f"audit-preq-{uuid.uuid4().hex[:14]}", tenant_id=self.tenant_id, user_id=self.actor_id, action=action, module_key="inventory", entity_type="purchase_requisition", entity_id=row.id, old_value=json.dumps({"status": previous}), new_value=json.dumps({"status": target, "version": row.version, "reason": reason})))

    def _next_code(self) -> str:
        prefix = datetime.now(timezone.utc).strftime("REQ-%Y%m%d")
        last = self.db.query(PurchaseRequisition).filter(PurchaseRequisition.tenant_id == self.tenant_id, PurchaseRequisition.code.like(f"{prefix}-%")).order_by(PurchaseRequisition.code.desc()).with_for_update().first()
        sequence = int(last.code.rsplit("-", 1)[-1]) + 1 if last else 1
        return f"{prefix}-{sequence:04d}"

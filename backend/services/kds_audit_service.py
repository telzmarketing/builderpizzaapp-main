"""Business rules for the final delivery audit and handoff."""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session, joinedload

from backend.core.exceptions import DomainError
from backend.models.delivery import Delivery, DeliveryEvent, DeliveryStatus
from backend.models.kds_audit import DeliveryAudit, DeliveryAuditEvidence, DeliveryAuditItemConfirmation, DeliveryAuditVolume
from backend.models.label import LabelVolume
from backend.models.order import Order, OrderStatus
from backend.models.upload_asset import TenantUploadAsset


class KdsAuditService:
    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def _order(self, order_id: str, *, lock: bool = False) -> Order:
        query = self.db.query(Order).filter(Order.tenant_id == self.tenant_id, Order.id == order_id)
        if lock:
            query = query.with_for_update()
        order = query.options(joinedload(Order.items)).one_or_none()
        if order is None:
            raise DomainError("Pedido nao encontrado.", code="KdsAuditOrderNotFound")
        return order

    def _audit(self, audit_id: str, *, lock: bool = False) -> DeliveryAudit:
        query = self.db.query(DeliveryAudit).filter(DeliveryAudit.tenant_id == self.tenant_id, DeliveryAudit.id == audit_id)
        if lock:
            query = query.with_for_update()
        audit = query.one_or_none()
        if audit is None:
            raise DomainError("Auditoria nao encontrada.", code="KdsAuditNotFound")
        return audit

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    def queue(self) -> list[dict]:
        rows = self.db.query(Order, Delivery).join(Delivery, Delivery.order_id == Order.id).filter(
            Order.tenant_id == self.tenant_id,
            Delivery.tenant_id == self.tenant_id,
            Order.status == OrderStatus.ready_for_pickup,
            Delivery.status.in_((DeliveryStatus.pending_assignment, DeliveryStatus.assigned)),
        ).order_by(Order.ready_for_pickup_at.asc().nullsfirst(), Order.created_at.asc()).all()
        return [{"order_id": o.id, "order_code": o.order_code, "order_origin": o.order_origin,
                 "status": o.status.value, "delivery_id": d.id, "delivery_status": d.status.value,
                 "delivery_person_id": d.delivery_person_id, "ready_for_pickup_at": o.ready_for_pickup_at}
                for o, d in rows]

    def detail(self, order_id: str) -> dict:
        order = self._order(order_id)
        delivery = self.db.query(Delivery).filter(Delivery.tenant_id == self.tenant_id, Delivery.order_id == order_id).one_or_none()
        if delivery is None or delivery.status not in (DeliveryStatus.pending_assignment, DeliveryStatus.assigned):
            raise DomainError("Pedido nao esta aguardando auditoria.", code="KdsAuditNotEligible")
        audit = self.db.query(DeliveryAudit).filter(DeliveryAudit.tenant_id == self.tenant_id, DeliveryAudit.order_id == order_id).one_or_none()
        item_rows = self.db.query(DeliveryAuditItemConfirmation).filter(DeliveryAuditItemConfirmation.tenant_id == self.tenant_id,
            DeliveryAuditItemConfirmation.audit_id == audit.id).all() if audit else []
        volume_rows = self.db.query(DeliveryAuditVolume).filter(DeliveryAuditVolume.tenant_id == self.tenant_id,
            DeliveryAuditVolume.audit_id == audit.id).all() if audit else []
        return {"order_id": order.id, "order_code": order.order_code, "order_origin": order.order_origin,
                "delivery_id": delivery.id, "delivery_status": delivery.status.value,
                "audit_id": audit.id if audit else None, "audit_status": audit.status if audit else None,
                "audit_items": [{"order_item_id": row.order_item_id, "expected_quantity": row.expected_quantity,
                                 "confirmed_quantity": row.confirmed_quantity, "confirmed": row.confirmed}
                                for row in item_rows],
                "audit_volumes": [{"id": row.id, "order_item_id": row.order_item_id, "label_volume_id": row.label_volume_id,
                                   "sequence": row.sequence, "confirmed": row.confirmed} for row in volume_rows],
                "items": [{"id": item.id, "quantity": item.quantity, "product_id": item.product_id,
                           "selected_size": item.selected_size, "selected_crust_type": item.selected_crust_type,
                           "notes": item.notes} for item in order.items]}

    def start(self, order_id: str, actor_id: str) -> dict:
        order = self._order(order_id, lock=True)
        delivery = self.db.query(Delivery).filter(Delivery.tenant_id == self.tenant_id, Delivery.order_id == order_id).with_for_update().one_or_none()
        if delivery is None or delivery.status not in (DeliveryStatus.pending_assignment, DeliveryStatus.assigned):
            raise DomainError("Pedido nao esta aguardando auditoria.", code="KdsAuditNotEligible")
        audit = self.db.query(DeliveryAudit).filter(DeliveryAudit.tenant_id == self.tenant_id, DeliveryAudit.order_id == order_id).with_for_update().one_or_none()
        if audit is None:
            audit = DeliveryAudit(id=str(uuid4()), tenant_id=self.tenant_id, order_id=order_id, delivery_id=delivery.id, started_by_admin_id=actor_id)
            self.db.add(audit)
            self.db.flush()
            for item in order.items:
                self.db.add(DeliveryAuditItemConfirmation(id=str(uuid4()), tenant_id=self.tenant_id, audit_id=audit.id,
                    order_item_id=item.id, expected_quantity=int(item.quantity or 0)))
            label_rows = self.db.query(LabelVolume).filter(LabelVolume.tenant_id == self.tenant_id, LabelVolume.order_item_id.in_([i.id for i in order.items])).order_by(LabelVolume.sequence.asc()).all()
            if label_rows:
                for sequence, volume in enumerate(label_rows, 1):
                    self.db.add(DeliveryAuditVolume(id=str(uuid4()), tenant_id=self.tenant_id, audit_id=audit.id,
                        order_item_id=volume.order_item_id, label_volume_id=volume.id, sequence=sequence))
            else:
                sequence = 0
                for item in order.items:
                    for _ in range(max(1, int(item.quantity or 0))):
                        sequence += 1
                        self.db.add(DeliveryAuditVolume(id=str(uuid4()), tenant_id=self.tenant_id, audit_id=audit.id,
                            order_item_id=item.id, sequence=sequence))
        elif audit.status == "completed":
            raise DomainError("A retirada ja foi auditada.", code="KdsAuditAlreadyCompleted")
        self.db.commit()
        return self.detail(order_id) | {"audit_id": audit.id, "audit_status": audit.status}

    def confirm_item(self, audit_id: str, item_id: str, quantity: int, actor_id: str) -> dict:
        audit = self._audit(audit_id, lock=True)
        row = self.db.query(DeliveryAuditItemConfirmation).filter(DeliveryAuditItemConfirmation.tenant_id == self.tenant_id,
            DeliveryAuditItemConfirmation.audit_id == audit.id, DeliveryAuditItemConfirmation.order_item_id == item_id).one_or_none()
        if row is None:
            raise DomainError("Item nao pertence a esta auditoria.", code="KdsAuditItemNotFound")
        if quantity > row.expected_quantity:
            raise DomainError("Quantidade conferida maior que a esperada.", code="KdsAuditQuantityInvalid")
        row.confirmed_quantity, row.confirmed, row.actor_id, row.confirmed_at = quantity, quantity == row.expected_quantity, actor_id, self._now()
        self.db.commit()
        return {"audit_id": audit.id, "order_item_id": item_id, "confirmed_quantity": quantity, "confirmed": row.confirmed}

    def confirm_volume(self, audit_id: str, volume_id: str, actor_id: str) -> dict:
        audit = self._audit(audit_id, lock=True)
        row = self.db.query(DeliveryAuditVolume).filter(DeliveryAuditVolume.tenant_id == self.tenant_id,
            DeliveryAuditVolume.audit_id == audit.id, DeliveryAuditVolume.id == volume_id).one_or_none()
        if row is None:
            raise DomainError("Volume nao pertence a esta auditoria.", code="KdsAuditVolumeNotFound")
        row.confirmed, row.actor_id, row.confirmed_at = True, actor_id, self._now()
        self.db.commit()
        return {"audit_id": audit.id, "volume_id": volume_id, "confirmed": True}

    def add_evidence(self, audit_id: str, body, actor_id: str) -> dict:
        audit = self._audit(audit_id)
        asset = self.db.query(TenantUploadAsset).filter(TenantUploadAsset.tenant_id == self.tenant_id, TenantUploadAsset.id == body.asset_id).one_or_none()
        if asset is None:
            raise DomainError("Evidencia nao pertence ao estabelecimento.", code="KdsAuditEvidenceNotFound")
        existing = self.db.query(DeliveryAuditEvidence).filter(DeliveryAuditEvidence.tenant_id == self.tenant_id,
            DeliveryAuditEvidence.audit_id == audit.id, DeliveryAuditEvidence.asset_id == asset.id).one_or_none()
        if existing:
            return {"evidence_id": existing.id, "audit_id": audit.id, "asset_id": asset.id, "idempotent": True}
        row = DeliveryAuditEvidence(id=str(uuid4()), tenant_id=self.tenant_id, audit_id=audit.id, asset_id=asset.id,
            evidence_type=body.evidence_type, captured_at=body.captured_at, actor_id=actor_id, metadata_json=body.metadata_json)
        self.db.add(row)
        self.db.commit()
        return {"evidence_id": row.id, "audit_id": audit.id, "asset_id": asset.id, "idempotent": False}

    def handoff(self, audit_id: str, actor_id: str) -> dict:
        audit = self._audit(audit_id, lock=True)
        if audit.status == "completed":
            return {"audit_id": audit.id, "status": audit.status, "idempotent": True}
        items = self.db.query(DeliveryAuditItemConfirmation).filter(DeliveryAuditItemConfirmation.tenant_id == self.tenant_id, DeliveryAuditItemConfirmation.audit_id == audit.id).all()
        volumes = self.db.query(DeliveryAuditVolume).filter(DeliveryAuditVolume.tenant_id == self.tenant_id, DeliveryAuditVolume.audit_id == audit.id).all()
        if not items or not all(x.confirmed for x in items) or not volumes or not all(x.confirmed for x in volumes):
            raise DomainError("Conclua a conferencia de todos os itens e volumes antes da retirada.", code="KdsAuditIncomplete")
        now = self._now()
        delivery = self.db.query(Delivery).filter(Delivery.tenant_id == self.tenant_id, Delivery.id == audit.delivery_id).with_for_update().one()
        order = self._order(audit.order_id, lock=True)
        if delivery.status not in (DeliveryStatus.pending_assignment, DeliveryStatus.assigned, DeliveryStatus.picked_up):
            raise DomainError("Entrega nao pode ser liberada neste estado.", code="KdsAuditDeliveryState")
        delivery.status, delivery.picked_up_at = DeliveryStatus.picked_up, delivery.picked_up_at or now
        order.status, order.out_for_delivery_at = OrderStatus.on_the_way, order.out_for_delivery_at or now
        audit.status, audit.completed_at, audit.handoff_at, audit.handoff_by_admin_id = "completed", now, now, actor_id
        self.db.add(DeliveryEvent(id=str(uuid4()), tenant_id=self.tenant_id, delivery_id=delivery.id,
            event_type="audit_handoff", description="Pedido liberado apos auditoria KDS.",
            actor_type="admin", actor_id=actor_id, created_at=now))
        self.db.commit()
        return {"audit_id": audit.id, "status": audit.status, "delivery_id": delivery.id, "delivery_status": delivery.status.value,
                "order_id": order.id, "order_status": order.status.value, "idempotent": False}

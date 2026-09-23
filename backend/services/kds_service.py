"""Business rules for the kitchen and dispatch touch stations."""
from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.core.events import DeliveryAssigned
from backend.core.exceptions import DomainError, OrderNotFound
from backend.core.tenant_context import TenantContext, TenantSource
from backend.models.delivery import (
    Delivery, DeliveryEvent, DeliveryPerson, DeliveryPersonStatus, DeliveryStatus,
)
from backend.models.order import Order, OrderStatus
from backend.models.product import Product
from backend.services.order_service import OrderService


class KdsService:
    KITCHEN_STATUSES = (OrderStatus.paid, OrderStatus.pago, OrderStatus.preparing)

    def __init__(self, db: Session, tenant_context: TenantContext):
        self.db = db
        self.tenant_context = tenant_context
        self.tenant_id = tenant_context.tenant_id

    def _order_query(self):
        return self.db.query(Order).filter(Order.tenant_id == self.tenant_id)

    def _load_order(self, order_id: str, *, lock: bool = False) -> Order:
        query = self._order_query().filter(Order.id == order_id)
        if lock:
            # Do not combine PostgreSQL FOR UPDATE with joined outer loads.
            query = query.with_for_update(of=Order)
        else:
            query = query.options(
                joinedload(Order.items), joinedload(Order.payment),
                joinedload(Order.delivery).joinedload(Delivery.delivery_person),
            )
        order = query.first()
        if order is None:
            raise OrderNotFound(order_id)
        return order

    def kitchen_orders(self) -> list[dict]:
        orders = self._order_query().options(
            joinedload(Order.items), joinedload(Order.payment),
        ).filter(or_(
            Order.status.in_(self.KITCHEN_STATUSES),
            and_(
                Order.fulfillment_type == "pickup",
                Order.status == OrderStatus.ready_for_pickup,
            ),
        )).order_by(Order.created_at).all()
        return self._serialize_orders(orders, include_dispatch_details=False)

    def start_preparation(self, order_id: str, *, actor_id: str) -> dict:
        order = self._load_order(order_id, lock=True)
        current = self._status(order)
        if current not in {OrderStatus.paid.value, OrderStatus.pago.value}:
            raise DomainError(
                "Somente pedidos pagos podem entrar em preparacao.",
                code="KdsOrderNotReadyToStart",
            )
        self._audit_order_transition(order, current, OrderStatus.preparing.value, actor_id)
        order = OrderService(
            self.db, self.tenant_context
        ).change_status(order.id, OrderStatus.preparing.value, changed_by=f"kds:{actor_id}")
        return self._serialize_orders([self._load_order(order_id)], include_dispatch_details=False)[0]

    def mark_ready(self, order_id: str, *, actor_id: str) -> dict:
        order = self._load_order(order_id, lock=True)
        current = self._status(order)
        self._audit_order_transition(order, current, OrderStatus.ready_for_pickup.value, actor_id)
        order = OrderService(
            self.db, self.tenant_context
        ).change_status(order.id, OrderStatus.ready_for_pickup.value, changed_by=f"kds:{actor_id}")
        return self._serialize_orders([self._load_order(order_id)], include_dispatch_details=False)[0]

    def complete_pickup(self, order_id: str, *, actor_id: str) -> dict:
        order = self._load_order(order_id, lock=True)
        if order.fulfillment_type != "pickup":
            raise DomainError("Somente pedidos para retirada podem usar esta acao.", code="KdsPickupOnly")
        current = self._status(order)
        if current != OrderStatus.ready_for_pickup.value:
            raise DomainError("O pedido para retirada ainda nao esta pronto.", code="KdsPickupNotReady")
        self._audit_order_transition(order, current, OrderStatus.delivered.value, actor_id)
        order = OrderService(
            self.db, self.tenant_context
        ).complete_customer_pickup(order.id, changed_by=f"kds:{actor_id}")
        return self._serialize_orders([self._load_order(order_id)], include_dispatch_details=False)[0]

    def dispatch_orders(self) -> list[dict]:
        orders = self._order_query().options(
            joinedload(Order.items), joinedload(Order.payment),
            joinedload(Order.delivery).joinedload(Delivery.delivery_person),
        ).filter(
            Order.status == OrderStatus.ready_for_pickup,
            Order.fulfillment_type == "delivery",
            ~Order.delivery.has(Delivery.status.in_((
                DeliveryStatus.assigned, DeliveryStatus.picked_up,
                DeliveryStatus.on_the_way, DeliveryStatus.delivered,
                DeliveryStatus.completed,
            ))),
        ).order_by(Order.updated_at).all()
        return self._serialize_orders(orders, include_dispatch_details=True)

    def available_drivers(self) -> list[dict]:
        people = self.db.query(DeliveryPerson).filter(
            DeliveryPerson.tenant_id == self.tenant_id,
            DeliveryPerson.active.is_(True),
            DeliveryPerson.deleted_at.is_(None),
            DeliveryPerson.status == DeliveryPersonStatus.available,
        ).order_by(DeliveryPerson.name).all()
        return [{
            "id": row.id,
            "name": row.name,
            "status": self._status(row),
            "vehicle_type": self._status(row.vehicle_type),
        } for row in people]

    def assign_driver(
        self, order_id: str, delivery_person_id: str, *,
        estimated_minutes: int, actor_id: str,
    ) -> dict:
        order = self._load_order(order_id, lock=True)
        if self._status(order) != OrderStatus.ready_for_pickup.value:
            raise DomainError("O pedido ainda nao esta pronto para expedicao.", code="DispatchOrderNotReady")
        if order.fulfillment_type != "delivery":
            raise DomainError("Pedidos para retirada nao recebem motoboy.", code="DispatchPickupNotAllowed")

        person = self.db.query(DeliveryPerson).filter(
            DeliveryPerson.id == delivery_person_id,
            DeliveryPerson.tenant_id == self.tenant_id,
            DeliveryPerson.active.is_(True),
            DeliveryPerson.deleted_at.is_(None),
        ).with_for_update().first()
        if person is None:
            raise DomainError("Motoboy nao encontrado neste estabelecimento.", code="DeliveryPersonNotFound")
        if person.status != DeliveryPersonStatus.available:
            raise DomainError("Motoboy precisa estar ativo e disponivel.", code="DeliveryPersonUnavailable")

        delivery = self.db.query(Delivery).filter(
            Delivery.tenant_id == self.tenant_id,
            Delivery.order_id == order.id,
        ).with_for_update().first()
        if delivery and delivery.status not in (DeliveryStatus.failed, DeliveryStatus.cancelled):
            raise DomainError("Pedido ja possui uma entrega atribuida.", code="DeliveryAlreadyAssigned")

        now = datetime.now(timezone.utc)
        if delivery is None:
            delivery = Delivery(id=str(uuid.uuid4()), tenant_id=self.tenant_id, order_id=order.id)
            self.db.add(delivery)
        delivery.delivery_person_id = person.id
        delivery.status = DeliveryStatus.assigned
        delivery.assigned_at = now
        delivery.estimated_minutes = estimated_minutes
        delivery.confirmation_code = "".join(random.choices("0123456789", k=4))
        delivery.confirmed_by_code_at = None
        person.status = DeliveryPersonStatus.busy
        self.db.flush()
        self.db.add(DeliveryEvent(
            id=str(uuid.uuid4()), tenant_id=self.tenant_id,
            delivery_id=delivery.id, event_type="assigned",
            description=f"Motoboy {person.name} atribuido pela expedicao.",
            actor_type="admin", actor_id=actor_id,
            metadata_json=json.dumps({
                "delivery_person_id": person.id,
                "estimated_minutes": estimated_minutes,
                "source": "kds_dispatch",
            }),
        ))
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise DomainError("Pedido ou motoboy foi atribuido por outro operador.", code="DispatchConcurrencyConflict") from exc
        self.db.refresh(delivery)

        # Assignment does not mean the driver has departed.  The driver app is
        # the authority that later advances the order to on_the_way.
        from backend.core.events import bus
        bus.publish(DeliveryAssigned(
            delivery_id=delivery.id, order_id=order.id,
            delivery_person_id=person.id, delivery_person_name=person.name,
            estimated_minutes=estimated_minutes,
        ))
        return {
            "order": self._serialize_orders([self._load_order(order.id)], include_dispatch_details=True)[0],
            "delivery": {
                "id": delivery.id, "order_id": delivery.order_id,
                "delivery_person_id": delivery.delivery_person_id,
                "delivery_person_name": person.name,
                "status": self._status(delivery),
                "estimated_minutes": delivery.estimated_minutes,
                "assigned_at": delivery.assigned_at,
            },
        }

    def _audit_order_transition(self, order: Order, old: str, new: str, actor_id: str) -> None:
        from backend.models.rbac import AdminAuditLog
        self.db.add(AdminAuditLog(
            id=str(uuid.uuid4()), tenant_id=self.tenant_id, user_id=actor_id,
            action="status_change", module_key="cozinha",
            entity_type="order", entity_id=order.id,
            old_value=old, new_value=new,
        ))

    @staticmethod
    def _status(value) -> str:
        value = getattr(value, "status", value)
        return value.value if hasattr(value, "value") else str(value)

    def _serialize_orders(self, orders: list[Order], *, include_dispatch_details: bool) -> list[dict]:
        product_ids = {item.product_id for order in orders for item in order.items}
        products = {
            row.id: row for row in self.db.query(Product).filter(
                Product.tenant_id == self.tenant_id,
                Product.id.in_(product_ids),
            ).all()
        } if product_ids else {}
        result = []
        for order in orders:
            payment = order.payment
            delivery = order.delivery
            payload = {
                "id": order.id, "order_code": order.order_code,
                "status": self._status(order),
                "fulfillment_type": order.fulfillment_type or "delivery",
                "sales_channel": order.sales_channel or "delivery",
                "notes": order.notes, "total": order.total,
                "estimated_time": order.estimated_time,
                "created_at": order.created_at, "updated_at": order.updated_at,
                "preparation_started_at": order.preparation_started_at,
                "items": [{
                    "id": item.id, "product_id": item.product_id,
                    "product_name": products[item.product_id].name if item.product_id in products else "Item",
                    "quantity": item.quantity, "selected_size": item.selected_size,
                    "selected_crust_type": item.selected_crust_type,
                    "selected_drink_variant": item.selected_drink_variant,
                    "notes": item.notes,
                    "flavors": [{"name": flavor.flavor_name} for flavor in item.flavors],
                } for item in order.items],
            }
            if include_dispatch_details:
                payload.update({
                    "delivery_name": order.delivery_name,
                    "delivery_street": order.delivery_street,
                    "delivery_city": order.delivery_city,
                    "delivery_complement": order.delivery_complement,
                    "payment_method": self._status(payment.method) if payment else None,
                    "pay_on_delivery": bool(payment.pay_on_delivery) if payment else False,
                    "delivery_payment_method": payment.delivery_payment_method if payment else None,
                    "cash_needs_change": payment.cash_needs_change if payment else None,
                    "cash_change_for": payment.cash_change_for if payment else None,
                    "delivery": ({
                    "id": delivery.id, "status": self._status(delivery),
                    "delivery_person_id": delivery.delivery_person_id,
                    "delivery_person_name": delivery.delivery_person.name if delivery.delivery_person else None,
                    "assigned_at": delivery.assigned_at,
                    } if delivery else None),
                })
            result.append(payload)
        return result

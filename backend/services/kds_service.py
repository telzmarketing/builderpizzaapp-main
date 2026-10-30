"""Business rules for the kitchen and dispatch touch stations."""
from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.core.events import DeliveryAssigned
from backend.core.exceptions import DomainError, OrderNotFound
from backend.core.state_machine import delivery_sm
from backend.core.tenant_context import TenantContext, TenantSource
from backend.models.delivery import (
    Delivery, DeliveryEvent, DeliveryPerson, DeliveryPersonStatus, DeliveryStatus,
    LogisticsSettings,
)
from backend.models.kds_production import ProductionUnit, ProductionAttempt
from backend.models.order import Order, OrderItem, OrderStatus
from backend.models.cmv import OrderCmvSnapshot, OrderItemCmvSnapshot
from backend.models.product import Product
from backend.services.order_service import OrderService
from backend.services.operational_payment import cash_change_amount


class KdsService:
    KITCHEN_STATUSES = (OrderStatus.paid, OrderStatus.pago, OrderStatus.preparing)
    OVERVIEW_ORDER_STATUSES = (
        OrderStatus.paid,
        OrderStatus.pago,
        OrderStatus.preparing,
        OrderStatus.ready_for_pickup,
        OrderStatus.on_the_way,
    )
    OVERVIEW_STAGES = (
        "waiting_kitchen",
        "preparing",
        "ready_unassigned",
        "assigned_waiting_departure",
        "in_route",
    )
    ASSIGNED_WAITING_DEPARTURE_STATUSES = (DeliveryStatus.assigned,)
    # An assigned delivery remains visible at dispatch while the package is
    # still on the counter.  Once pickup starts, the driver's operational flow
    # becomes authoritative and the order leaves this queue.
    DISPATCH_HIDDEN_DELIVERY_STATUSES = (
        DeliveryStatus.picked_up,
        DeliveryStatus.on_the_way,
        DeliveryStatus.delivered,
        DeliveryStatus.completed,
    )

    def __init__(self, db: Session, tenant_context: TenantContext):
        self.db = db
        self.tenant_context = tenant_context
        self.tenant_id = tenant_context.tenant_id

    def _order_query(self):
        return self.db.query(Order).filter(
            Order.tenant_id == self.tenant_id,
            Order.archived_at.is_(None),
        )

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

    def _latest_attempts(self, units: list[ProductionUnit]) -> dict[str, ProductionAttempt]:
        if not units:
            return {}
        attempts = self.db.query(ProductionAttempt).filter(
            ProductionAttempt.tenant_id == self.tenant_id,
            ProductionAttempt.production_unit_id.in_([unit.id for unit in units]),
        ).order_by(ProductionAttempt.attempt_number).all()
        latest: dict[str, ProductionAttempt] = {}
        for attempt in attempts:
            latest[attempt.production_unit_id] = attempt
        return latest

    def _production_unit_snapshot(self, orders: list[Order]):
        if not orders:
            return {}, {}
        units = self.db.query(ProductionUnit).filter(
            ProductionUnit.tenant_id == self.tenant_id,
            ProductionUnit.order_id.in_([order.id for order in orders]),
        ).order_by(ProductionUnit.order_id, ProductionUnit.order_item_id, ProductionUnit.unit_index).all()
        latest = self._latest_attempts(units)
        by_order: dict[str, list[ProductionUnit]] = {order.id: [] for order in orders}
        progress = {order.id: {"total_units": 0, "ready_units": 0, "pending_units": 0, "dispatch_completed_units": 0} for order in orders}
        for unit in units:
            by_order.setdefault(unit.order_id, []).append(unit)
            row = progress[unit.order_id]
            row["total_units"] += 1
            if unit.state == "ready" and latest.get(unit.id) is not None and latest[unit.id].state == "ready":
                row["ready_units"] += 1
            else:
                row["pending_units"] += 1
            if unit.dispatch_completed_at is not None:
                row["dispatch_completed_units"] += 1
        return by_order, progress

    def _drink_item_ids(self, orders: list[Order]) -> set[str]:
        item_ids = [item.id for order in orders for item in order.items]
        if not item_ids:
            return set()
        rows = self.db.query(OrderItem.id).outerjoin(
            Product, Product.id == OrderItem.product_id,
        ).filter(
            OrderItem.tenant_id == self.tenant_id,
            OrderItem.id.in_(item_ids),
            Product.tenant_id == self.tenant_id,
            or_(Product.product_type == "drink", OrderItem.selected_drink_variant.isnot(None)),
        ).all()
        return {row[0] for row in rows}

    def _mark_drink_units_ready(self, order: Order) -> None:
        """Drinks remain dispatch volumes but have no kitchen production step."""
        drink_item_ids = self._drink_item_ids([order])
        if not drink_item_ids:
            return
        units = self.db.query(ProductionUnit).filter(
            ProductionUnit.tenant_id == self.tenant_id,
            ProductionUnit.order_id == order.id,
            ProductionUnit.order_item_id.in_(drink_item_ids),
        ).all()
        for unit in units:
            unit.state = "ready"
            for attempt in unit.attempts:
                if attempt.state not in {"ready", "cancelled"}:
                    attempt.state = "ready"
                    attempt.completed_at = attempt.completed_at or datetime.now(timezone.utc)

    def _audit_unit(self, order_id: str, unit_id: str, actor_id: str, old: str, new: str, module_key: str) -> None:
        from backend.models.rbac import AdminAuditLog
        self.db.add(AdminAuditLog(
            id=str(uuid.uuid4()), tenant_id=self.tenant_id, user_id=actor_id,
            action="status_change", module_key=module_key,
            entity_type="production_unit", entity_id=unit_id,
            old_value=old, new_value=f"{new}; order_id={order_id}",
        ))

    def kitchen_orders(self) -> list[dict]:
        orders = self._order_query().options(
            joinedload(Order.items), joinedload(Order.payment),
            joinedload(Order.delivery).joinedload(Delivery.delivery_person),
        ).filter(
            Order.status.in_(self.KITCHEN_STATUSES),
        ).order_by(Order.created_at).all()
        item_ids = [item.id for order in orders for item in order.items]
        frozen = {}
        if item_ids:
            rows = self.db.query(OrderItemCmvSnapshot).filter(
                OrderItemCmvSnapshot.tenant_id == self.tenant_id,
                OrderItemCmvSnapshot.order_item_id.in_(item_ids),
            ).all()
            frozen = {
                row.order_item_id: self._operational_composition(row.composition_json)
                for row in rows
            }
        return self._serialize_orders(
            orders, include_dispatch_details=False, composition_by_item=frozen,
        )

    def kitchen_order_composition(self, order_id: str) -> dict:
        """Return the immutable technical composition for a kitchen order.

        KDS must render the same revision that was frozen when the order was
        created.  Resolving active recipes here would make an already paid
        order silently change when a manager publishes a new recipe.  CMV
        snapshots are the existing canonical frozen projection and contain no
        costs in this response.
        """
        order = self._load_order(order_id)
        snapshot = (
            self.db.query(OrderCmvSnapshot)
            .options(joinedload(OrderCmvSnapshot.items))
            .filter(
                OrderCmvSnapshot.tenant_id == self.tenant_id,
                OrderCmvSnapshot.order_id == order.id,
            )
            .first()
        )
        if snapshot is None:
            return {
                "order_id": order.id,
                "snapshot_id": None,
                "status": "missing_snapshot",
                "executable": False,
                "warnings": [{
                    "code": "CompositionSnapshotMissing",
                    "message": "Este pedido nao possui composicao tecnica congelada.",
                }],
                "items": [],
            }

        item_snapshots = {
            row.order_item_id: row for row in snapshot.items
            if row.tenant_id == self.tenant_id
        }
        items = []
        warnings = []
        for item in sorted(order.items, key=lambda row: (row.position or 0, row.id)):
            frozen = item_snapshots.get(item.id)
            composition = frozen.composition_json if frozen else None
            if not isinstance(composition, dict):
                warnings.append({
                    "code": "CompositionSnapshotMissingForItem",
                    "message": f"Item {item.id} nao possui composicao tecnica congelada.",
                })
                composition = {
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "complete": False,
                    "missing": ["composition_snapshot"],
                    "common_components": [], "flavors": [],
                    "ingredients": [], "removed_ingredients": [],
                    "substitutions": [], "methods": [], "notes": item.notes,
                    "recipe_version_ids": [],
                }
            # Do not forward any future financial fields if the persisted
            # projection gains them; KDS receives only operational keys.
            safe = self._operational_composition(composition)
            items.append({
                "order_item_id": item.id,
                "position": item.position,
                "product_id": item.product_id,
                "composition": safe,
            })
        return {
            "order_id": order.id,
            "snapshot_id": snapshot.id,
            "status": snapshot.status,
            "executable": not warnings and all(
                row["composition"].get("complete") is True for row in items
            ),
            "warnings": warnings,
            "items": items,
        }

    @staticmethod
    def _operational_composition(composition: dict | None) -> dict | None:
        if not isinstance(composition, dict):
            return composition
        return {
            key: composition.get(key)
            for key in (
                "product_id", "quantity", "complete", "missing",
                "recipe_version_ids", "common_components", "flavors",
                "ingredients", "removed_ingredients", "substitutions",
                "methods", "notes",
            )
        }

    def overview(self) -> dict:
        """Return the tenant's bounded operational snapshot for the general KDS."""
        orders = self._order_query().options(
            joinedload(Order.delivery).joinedload(Delivery.delivery_person),
        ).filter(
            Order.status.in_(self.OVERVIEW_ORDER_STATUSES),
        ).order_by(Order.created_at).all()

        counters = {stage: 0 for stage in self.OVERVIEW_STAGES}
        serialized_orders = []
        for order in orders:
            delivery = self._overview_delivery(order)
            stage = self._overview_stage(order, delivery)
            counters[stage] += 1
            serialized_orders.append(
                self._serialize_overview_order(order, stage, delivery)
            )

        driver_counts = dict(self.db.query(
            DeliveryPerson.status,
            func.count(DeliveryPerson.id),
        ).filter(
            DeliveryPerson.tenant_id == self.tenant_id,
            DeliveryPerson.active.is_(True),
            DeliveryPerson.deleted_at.is_(None),
            DeliveryPerson.status.in_((
                DeliveryPersonStatus.available,
                DeliveryPersonStatus.busy,
            )),
        ).group_by(DeliveryPerson.status).all())
        counters.update({
            "drivers_available": driver_counts.get(DeliveryPersonStatus.available, 0),
            "drivers_busy": driver_counts.get(DeliveryPersonStatus.busy, 0),
        })
        return {
            "generated_at": self._as_utc(datetime.now(timezone.utc)),
            "counters": counters,
            "orders": serialized_orders,
        }

    def _overview_delivery(self, order: Order) -> Delivery | None:
        delivery = order.delivery
        if delivery is None or delivery.tenant_id != self.tenant_id:
            return None
        return delivery

    def _overview_stage(self, order: Order, delivery: Delivery | None) -> str:
        order_status = self._status(order)
        if order_status in {OrderStatus.paid.value, OrderStatus.pago.value}:
            return "waiting_kitchen"
        if order_status == OrderStatus.preparing.value:
            return "preparing"
        if order_status == OrderStatus.on_the_way.value:
            return "in_route"
        if delivery is not None:
            delivery_status = self._status(delivery)
            if delivery_status in {
                DeliveryStatus.picked_up.value,
                DeliveryStatus.on_the_way.value,
            }:
                return "in_route"
            if delivery.status in self.ASSIGNED_WAITING_DEPARTURE_STATUSES:
                return "assigned_waiting_departure"
        return "ready_unassigned"

    def _serialize_overview_order(
        self, order: Order, stage: str, delivery: Delivery | None,
    ) -> dict:
        status_started_at = {
            "waiting_kitchen": order.paid_at,
            "preparing": order.preparation_started_at,
            "ready_unassigned": order.ready_for_pickup_at,
            "assigned_waiting_departure": delivery.assigned_at if delivery else None,
            "in_route": order.out_for_delivery_at or (
                delivery.picked_up_at if delivery else None
            ),
        }[stage] or order.updated_at or order.created_at

        delivery_payload = None
        if delivery is not None:
            person = delivery.delivery_person
            driver_name = (
                person.name
                if person is not None and person.tenant_id == self.tenant_id
                else None
            )
            delivery_payload = {
                "status": self._status(delivery),
                "driver_name": driver_name,
            }
        return {
            "id": order.id,
            "order_code": order.order_code,
            "stage": stage,
            "status": self._status(order),
            "fulfillment_type": order.fulfillment_type or "delivery",
            "created_at": self._as_utc(order.created_at),
            "status_started_at": self._as_utc(status_started_at),
            "delivery": delivery_payload,
        }

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def start_preparation(self, order_id: str, *, actor_id: str) -> dict:
        order = self._load_order(order_id, lock=True)
        current = self._status(order)
        if current not in {OrderStatus.paid.value, OrderStatus.pago.value}:
            raise DomainError(
                "Somente pedidos pagos podem entrar em preparacao.",
                code="KdsOrderNotReadyToStart",
            )
        self._audit_order_transition(order, current, OrderStatus.preparing.value, actor_id)
        from backend.services.kds_production_service import KdsProductionService
        KdsProductionService(self.db, self.tenant_context).initialize_order(order_id, actor_id, commit=False)
        order = OrderService(
            self.db, self.tenant_context
        ).change_status(order.id, OrderStatus.preparing.value, changed_by=f"kds:{actor_id}")
        return self._serialize_orders([self._load_order(order_id)], include_dispatch_details=False)[0]

    def _assert_all_units_ready(self, order: Order) -> list[ProductionUnit]:
        self._mark_drink_units_ready(order)
        units, progress = self._production_unit_snapshot([order])
        drink_item_ids = self._drink_item_ids([order])
        expected = sum(max(0, int(item.quantity or 0)) for item in order.items if item.id not in drink_item_ids)
        kitchen_units = [unit for unit in units.get(order.id, []) if unit.order_item_id not in drink_item_ids]
        latest = self._latest_attempts(kitchen_units)
        actual = sum(1 for unit in kitchen_units if unit.state == "ready" and latest.get(unit.id) is not None and latest[unit.id].state == "ready")
        if len(kitchen_units) != expected or actual != expected:
            raise DomainError(
                "Todas as unidades físicas precisam estar prontas no KDS antes de avançar o pedido.",
                code="KdsUnitsPending",
            )
        return units.get(order.id, [])

    def mark_ready(self, order_id: str, *, actor_id: str) -> dict:
        order = self._load_order(order_id, lock=True)
        current = self._status(order)
        units, _ = self._production_unit_snapshot([order])
        if units.get(order.id):
            self._assert_all_units_ready(order)
        else:
            # Published orders created before physical-unit KDS keep their legacy gate.
            from backend.services.kds_production_service import ensure_kds_units_ready
            ensure_kds_units_ready(self.db, order.tenant_id, order.id)
        if current == OrderStatus.ready_for_pickup.value:
            return self._serialize_orders([self._load_order(order_id)], include_dispatch_details=False)[0]
        self._audit_order_transition(order, current, OrderStatus.ready_for_pickup.value, actor_id)
        order = OrderService(
            self.db, self.tenant_context
        ).change_status(order.id, OrderStatus.ready_for_pickup.value, changed_by=f"kds:{actor_id}")
        return self._serialize_orders([self._load_order(order_id)], include_dispatch_details=False)[0]

    def complete_pickup(
        self, order_id: str, *, actor_id: str, audit_module: str = "cozinha",
    ) -> dict:
        order = self._load_order(order_id, lock=True)
        if order.fulfillment_type != "pickup":
            raise DomainError("Somente pedidos para retirada podem usar esta acao.", code="KdsPickupOnly")
        current = self._status(order)
        units = self._assert_all_units_ready(order)
        if any(unit.dispatch_completed_at is None for unit in units):
            raise DomainError("Conclua cada unidade na expedição antes de entregar o pedido.", code="DispatchUnitsPending")
        if current != OrderStatus.ready_for_pickup.value:
            raise DomainError("O pedido para retirada ainda nao esta pronto.", code="KdsPickupNotReady")
        self._audit_order_transition(
            order, current, OrderStatus.delivered.value, actor_id,
            module_key=audit_module,
        )
        order = OrderService(
            self.db, self.tenant_context
        ).complete_customer_pickup(order.id, changed_by=f"kds:{actor_id}")
        return self._serialize_orders([self._load_order(order_id)], include_dispatch_details=False)[0]

    def serve_dine_in(self, order_id: str, *, actor_id: str) -> dict:
        order = self._load_order(order_id, lock=True)
        if order.fulfillment_type != "dine_in":
            raise DomainError("Somente pedidos do salao podem ser servidos.", code="DineInOnly")
        self._audit_order_transition(order, self._status(order), OrderStatus.delivered.value, actor_id)
        OrderService(self.db, self.tenant_context).serve_dine_in(order.id, changed_by=f"kds:{actor_id}")
        return self._serialize_orders([self._load_order(order_id)], include_dispatch_details=False)[0]

    def dispatch_orders(self) -> list[dict]:
        orders = self._order_query().options(
            joinedload(Order.items), joinedload(Order.payment),
            joinedload(Order.delivery).joinedload(Delivery.delivery_person),
        ).filter(
            Order.status == OrderStatus.ready_for_pickup,
            or_(
                Order.fulfillment_type == "pickup",
                and_(
                    Order.fulfillment_type == "delivery",
                    ~Order.delivery.has(
                        Delivery.status.in_(self.DISPATCH_HIDDEN_DELIVERY_STATUSES)
                    ),
                ),
            ),
        ).order_by(Order.updated_at).all()
        return self._serialize_orders(orders, include_dispatch_details=True)

    def complete_dispatch_unit(
        self, order_id: str, unit_id: str, *, expected_version: int, actor_id: str,
    ) -> dict:
        order = self._load_order(order_id, lock=True)
        if self._status(order) != OrderStatus.ready_for_pickup.value:
            raise DomainError("A unidade só pode ser fechada após o pedido ficar pronto.", code="DispatchOrderNotReady")
        self._assert_all_units_ready(order)
        unit = self.db.query(ProductionUnit).filter(
            ProductionUnit.tenant_id == self.tenant_id,
            ProductionUnit.order_id == order.id,
            ProductionUnit.id == unit_id,
        ).with_for_update().first()
        if unit is None:
            raise DomainError("Unidade de produção não encontrada neste pedido.", code="ProductionUnitNotFound")
        if unit.dispatch_completed_at is None:
            if unit.version != expected_version:
                raise DomainError("A unidade foi alterada por outro operador.", code="VersionConflict")
            latest = self._latest_attempts([unit]).get(unit.id)
            if unit.state != "ready" or latest is None or latest.state != "ready":
                raise DomainError("A unidade ainda não foi concluída na cozinha.", code="ProductionUnitNotReady")
            unit.dispatch_completed_at = datetime.now(timezone.utc)
            unit.dispatch_completed_by = actor_id
            unit.version += 1
            self._audit_unit(order.id, unit.id, actor_id, "dispatch_open", "dispatch_completed", "expedicao")
            self.db.commit()

        current_units, _ = self._production_unit_snapshot([self._load_order(order_id)])
        all_closed = bool(current_units.get(order_id)) and all(
            row.dispatch_completed_at is not None for row in current_units[order_id]
        )
        assignment = None
        if all_closed and order.fulfillment_type == "delivery":
            assignment = self._auto_assign_order(order_id, actor_id=actor_id)
        updated = self._serialize_orders(
            [self._load_order(order_id)], include_dispatch_details=True,
        )[0]
        updated["auto_assignment"] = assignment
        return updated

    def _auto_assign_order(self, order_id: str, *, actor_id: str) -> dict:
        settings = self.db.query(LogisticsSettings).filter(
            LogisticsSettings.tenant_id == self.tenant_id,
        ).first()
        if settings is None or not settings.auto_assign:
            return {"status": "disabled"}
        order = self._load_order(order_id)
        if self._status(order) != OrderStatus.ready_for_pickup.value:
            return {"status": "blocked", "message": "Pedido ainda não está pronto."}
        if order.delivery and order.delivery.status not in (DeliveryStatus.failed, DeliveryStatus.cancelled):
            return {"status": "already_assigned", "delivery_person_name": order.delivery.delivery_person.name if order.delivery.delivery_person else None}

        active_statuses = (DeliveryStatus.assigned, DeliveryStatus.picked_up, DeliveryStatus.on_the_way)
        counts = dict(self.db.query(
            Delivery.delivery_person_id, func.count(Delivery.id),
        ).filter(
            Delivery.tenant_id == self.tenant_id,
            Delivery.status.in_(active_statuses),
        ).group_by(Delivery.delivery_person_id).all())
        people = self.db.query(DeliveryPerson).filter(
            DeliveryPerson.tenant_id == self.tenant_id,
            DeliveryPerson.active.is_(True),
            DeliveryPerson.deleted_at.is_(None),
            DeliveryPerson.status == DeliveryPersonStatus.available,
        ).order_by(DeliveryPerson.name).all()
        eligible = [person for person in people if counts.get(person.id, 0) < (settings.max_concurrent_deliveries or 0)]
        if not eligible:
            return {"status": "unavailable", "message": "Nenhum motoboy elegível/disponível para atribuição automática."}
        selected = min(eligible, key=lambda person: (counts.get(person.id, 0), person.name.lower(), person.id))
        try:
            result = self.assign_driver(
                order_id, selected.id,
                estimated_minutes=settings.default_estimated_minutes or 40,
                actor_id=actor_id, assignment_source="kds_auto_assign",
            )
            return {"status": "assigned", "delivery_person_name": result["delivery"]["delivery_person_name"]}
        except DomainError as exc:
            return {"status": "unavailable", "message": exc.message}

    def return_to_kitchen(
        self, order_id: str, production_unit_ids: list[str], *, reason: str, actor_id: str,
    ) -> dict:
        order = self._load_order(order_id, lock=True)
        if self._status(order) != OrderStatus.ready_for_pickup.value:
            raise DomainError("Somente pedidos prontos na expedição podem voltar à cozinha.", code="DispatchReturnInvalidState")
        if not reason.strip():
            raise DomainError("Informe o motivo do retorno à cozinha.", code="ReasonRequired")
        delivery = self.db.query(Delivery).filter(
            Delivery.tenant_id == self.tenant_id, Delivery.order_id == order.id,
        ).with_for_update().first()
        if delivery and delivery.status in (
            DeliveryStatus.picked_up, DeliveryStatus.on_the_way,
            DeliveryStatus.delivered, DeliveryStatus.completed,
        ):
            raise DomainError("Pedido com rota iniciada ou concluída não pode voltar à cozinha.", code="DispatchReturnRouteStarted")
        units = self._assert_all_units_ready(order)
        selected_ids = set(production_unit_ids)
        if len(selected_ids) != len(production_unit_ids) or not selected_ids:
            raise DomainError("Selecione ao menos uma unidade válida para refazer.", code="InvalidProductionUnits")
        selected = [unit for unit in units if unit.id in selected_ids]
        if len(selected) != len(selected_ids):
            raise DomainError("Uma ou mais unidades não pertencem ao pedido.", code="ProductionUnitNotFound")
        if delivery and delivery.status in (DeliveryStatus.pending_assignment, DeliveryStatus.assigned):
            person = self.db.query(DeliveryPerson).filter(
                DeliveryPerson.tenant_id == self.tenant_id,
                DeliveryPerson.id == delivery.delivery_person_id,
            ).with_for_update().first() if delivery.delivery_person_id else None
            delivery_sm.transition(
                delivery.id, self._status(delivery), DeliveryStatus.cancelled.value,
            )
            delivery.status = DeliveryStatus.cancelled
            if person:
                other_active = self.db.query(Delivery.id).filter(
                    Delivery.tenant_id == self.tenant_id,
                    Delivery.delivery_person_id == person.id,
                    Delivery.id != delivery.id,
                    Delivery.status.in_((DeliveryStatus.assigned, DeliveryStatus.picked_up, DeliveryStatus.on_the_way)),
                ).first()
                if not other_active:
                    person.status = DeliveryPersonStatus.available
            self.db.add(DeliveryEvent(
                id=str(uuid.uuid4()), tenant_id=self.tenant_id, delivery_id=delivery.id,
                event_type="cancelled", description="Atribuição cancelada para retorno do pedido à cozinha.",
                actor_type="admin", actor_id=actor_id, metadata_json=json.dumps({"reason": reason, "source": "kds_dispatch_return"}),
            ))
        for unit in selected:
            latest = self._latest_attempts([unit]).get(unit.id)
            if latest is None or latest.state != "ready":
                raise DomainError("Somente unidades prontas podem voltar para retrabalho.", code="ProductionUnitNotReady")
            unit.state = "queued"
            unit.version += 1
            unit.dispatch_completed_at = None
            unit.dispatch_completed_by = None
            self.db.add(ProductionAttempt(
                id=str(uuid.uuid4()), tenant_id=self.tenant_id,
                production_unit_id=unit.id, attempt_number=latest.attempt_number + 1,
                state="queued", previous_attempt_id=latest.id,
            ))
            self._audit_unit(order.id, unit.id, actor_id, "ready", f"queued: {reason}", "expedicao")
        self._audit_order_transition(
            order, OrderStatus.ready_for_pickup.value, OrderStatus.preparing.value,
            actor_id, module_key="expedicao",
        )
        OrderService(self.db, self.tenant_context).change_status(
            order.id, OrderStatus.preparing.value,
            changed_by=f"kds:expedicao:{actor_id}",
        )
        return self._serialize_orders([self._load_order(order_id)], include_dispatch_details=False)[0]

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
        estimated_minutes: int, actor_id: str, assignment_source: str = "kds_dispatch",
    ) -> dict:
        order = self._load_order(order_id, lock=True)
        if self._status(order) != OrderStatus.ready_for_pickup.value:
            raise DomainError("O pedido ainda nao esta pronto para expedicao.", code="DispatchOrderNotReady")
        if order.fulfillment_type != "delivery":
            raise DomainError("Pedidos para retirada nao recebem motoboy.", code="DispatchPickupNotAllowed")
        units = self._assert_all_units_ready(order)
        if any(unit.dispatch_completed_at is None for unit in units):
            raise DomainError("Conclua cada unidade na expedição antes de atribuir a entrega.", code="DispatchUnitsPending")

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
            description=f"Motoboy {person.name} atribuido automaticamente." if assignment_source == "kds_auto_assign" else f"Motoboy {person.name} atribuido pela expedicao.",
            actor_type="admin", actor_id=actor_id,
            metadata_json=json.dumps({
                "delivery_person_id": person.id,
                "estimated_minutes": estimated_minutes,
                "source": assignment_source,
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
            tenant_id=self.tenant_id,
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

    def _audit_order_transition(
        self, order: Order, old: str, new: str, actor_id: str, *,
        module_key: str = "cozinha",
    ) -> None:
        from backend.models.rbac import AdminAuditLog
        self.db.add(AdminAuditLog(
            id=str(uuid.uuid4()), tenant_id=self.tenant_id, user_id=actor_id,
            action="status_change", module_key=module_key,
            entity_type="order", entity_id=order.id,
            old_value=old, new_value=new,
        ))

    @staticmethod
    def _status(value) -> str:
        value = getattr(value, "status", value)
        return value.value if hasattr(value, "value") else str(value)

    def _serialize_orders(
        self, orders: list[Order], *, include_dispatch_details: bool,
        composition_by_item: dict[str, dict | None] | None = None,
    ) -> list[dict]:
        production_units, production_progress = self._production_unit_snapshot(orders)
        latest_attempts = self._latest_attempts([unit for rows in production_units.values() for unit in rows])
        drink_item_ids = self._drink_item_ids(orders)
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
            delivery_summary = ({
                "id": delivery.id,
                "status": self._status(delivery),
                "delivery_person_id": delivery.delivery_person_id,
                "delivery_person_name": (
                    delivery.delivery_person.name if delivery.delivery_person else None
                ),
                "assigned_at": delivery.assigned_at,
            } if delivery else None)
            serialized_items = []
            for item in order.items:
                product = products.get(item.product_id)
                is_drink = bool(
                    (product is not None and product.product_type == "drink")
                    or item.selected_drink_variant
                )
                serialized_items.append({
                    "id": item.id,
                    "product_id": item.product_id,
                    "product_name": product.name if product is not None else "Item",
                    "product_type": product.product_type if product is not None else None,
                    "is_drink": is_drink,
                    "quantity": item.quantity,
                    "selected_size": item.selected_size,
                    "selected_crust_type": item.selected_crust_type,
                    "selected_border_name": item.selected_border_name,
                    "selected_drink_variant": item.selected_drink_variant,
                    "notes": item.notes,
                    "add_ons": list(item.add_ons or []),
                    "flavors": [{"name": flavor.flavor_name} for flavor in item.flavors],
                    **({"composition": composition_by_item[item.id]} if composition_by_item is not None and item.id in composition_by_item else {}),
                })
            drinks = [
                {
                    "product_id": item["product_id"],
                    "name": item["product_name"],
                    "quantity": item["quantity"],
                    "notes": item.get("notes"),
                }
                for item in serialized_items
                if item["is_drink"]
            ]
            kitchen_view = not include_dispatch_details
            visible_items = [item for item in serialized_items if not kitchen_view or not item["is_drink"]]
            visible_units = [unit for unit in production_units.get(order.id, []) if not kitchen_view or unit.order_item_id not in drink_item_ids]
            visible_progress = production_progress.get(order.id, {
                "total_units": 0, "ready_units": 0, "pending_units": 0,
                "dispatch_completed_units": 0,
            })
            if kitchen_view:
                visible_ready = sum(1 for unit in visible_units if unit.state == "ready" and latest_attempts.get(unit.id) is not None and latest_attempts[unit.id].state == "ready")
                visible_progress = {
                    "total_units": len(visible_units),
                    "ready_units": visible_ready,
                    "pending_units": len(visible_units) - visible_ready,
                    "dispatch_completed_units": sum(1 for unit in visible_units if unit.dispatch_completed_at is not None),
                }
            payload = {
                "id": order.id, "order_code": order.order_code,
                "status": self._status(order),
                "fulfillment_type": order.fulfillment_type or "delivery",
                "sales_channel": order.sales_channel or "delivery",
                "notes": order.notes, "total": order.total,
                "estimated_time": order.estimated_time,
                "created_at": order.created_at, "updated_at": order.updated_at,
                "preparation_started_at": order.preparation_started_at,
                # This bounded association is shared by all operational KDS
                # surfaces.  Address and payment details remain dispatch-only.
                "delivery": delivery_summary,
                "items": visible_items,
                "drinks": drinks if include_dispatch_details else [],
                "has_drinks": bool(drinks) if include_dispatch_details else False,
                "production_units": [{
                    "id": unit.id,
                    "order_item_id": unit.order_item_id,
                    "unit_index": unit.unit_index,
                    "task_id": latest_attempts.get(unit.id).id if latest_attempts.get(unit.id) else None,
                    "state": unit.state,
                    "version": unit.version,
                    "dispatch_completed_at": unit.dispatch_completed_at,
                } for unit in visible_units],
                "production_progress": visible_progress,
            }
            if include_dispatch_details:
                payload.update({
                    "delivery_name": order.delivery_name,
                    "delivery_street": order.delivery_street,
                    "delivery_city": order.delivery_city,
                    "delivery_complement": order.delivery_complement,
                    "payment_method": self._status(payment.method) if payment else None,
                    "payment_status": self._status(payment.status) if payment else None,
                    "payment_provider": payment.provider if payment else None,
                    "pay_on_delivery": bool(payment.pay_on_delivery) if payment else False,
                    "delivery_payment_method": payment.delivery_payment_method if payment else None,
                    "cash_needs_change": payment.cash_needs_change if payment else None,
                    "cash_change_for": payment.cash_change_for if payment else None,
                    "cash_change_amount": cash_change_amount(payment, order.total),
                    "can_assign_driver": delivery is None or delivery.status in (
                        DeliveryStatus.failed, DeliveryStatus.cancelled,
                    ),
                })
            result.append(payload)
        return result

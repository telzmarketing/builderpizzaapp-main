from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.core.exceptions import OrderNotFound, TestOrderPurgeBlocked
from backend.models.delivery import Delivery, DeliveryItemConfirmation
from backend.models.finance import FinanceObligation, FinanceSettlement, FinanceTransaction
from backend.models.fiscal import FiscalDocument
from backend.models.kds_audit import DeliveryAudit as KdsDeliveryAudit
from backend.models.order import Order, OrderItem
from backend.models.payment import Payment, PaymentEvent, PaymentMethod
from backend.models.kds_production import (
    KdsAssignment,
    ProductionAttempt,
    ProductionAttemptConsumption,
    ProductionUnit,
)
from backend.models.rbac import AdminAuditLog
from backend.services.idempotency_service import IdempotencyService


class OrderTestPurgeService:
    """Fail-closed, tenant-scoped physical purge for explicitly confirmed tests."""

    OPERATION = "orders.purge_test"
    CONFIRMATION = "PURGE_TEST_ORDER"
    AUDIT_ACTION = "purge_test_order"
    ALLOWED_ORDER_REFERENCES = frozenset({"order_items", "payments", "production_units"})
    SAFE_PRODUCTION_UNIT_STATES = frozenset({"unassigned", "cancelled"})
    ALLOW_MANUAL_TEST_EXTERNAL_METADATA = False
    ALLOW_CANCELLED_PRODUCTION_ATTEMPTS = False
    PRODUCTION_ATTEMPT_EXECUTION_FIELDS = (
        "started_at",
        "stock_requested_at",
        "assembly_finished_at",
        "oven_started_at",
        "oven_finished_at",
        "checked_at",
        "completed_at",
    )

    def __init__(self, db: Session, *, tenant_id: str, actor_id: str, actor_name: str,
                 ip_address: str | None = None, user_agent: str | None = None):
        self.db = db
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.actor_name = actor_name
        self.ip_address = ip_address
        self.user_agent = user_agent

    def purge(self, *, order_id: str, confirmation: str, reason: str, idempotency_key: str) -> dict[str, Any]:
        if confirmation != self.CONFIRMATION:
            raise TestOrderPurgeBlocked(order_id, ["confirmation_token_invalid"])

        payload = {"order_id": order_id, "confirmation": confirmation, "reason": reason.strip()}
        idempotency = IdempotencyService(self.db, self.tenant_id)
        claim = idempotency.claim(idempotency_key, self.OPERATION, payload)
        if claim.replay_resource_id:
            return {
                "status": "already_purged",
                "order_id": claim.replay_resource_id,
                "deleted_payment": False,
                "deleted_order_items": 0,
            }

        try:
            return self._purge_locked(
                order_id=order_id,
                reason=reason.strip(),
                payload=payload,
                idempotency_record=claim.record,
            )
        except Exception:
            # The claim is deliberately abandoned after every failed attempt so
            # a blocked/rolled-back purge cannot poison the idempotency key.
            idempotency.abandon(claim.record)
            raise

    def _purge_locked(
        self,
        *,
        order_id: str,
        reason: str,
        payload: dict[str, str],
        idempotency_record: Any | None = None,
    ) -> dict[str, Any]:
        order = (
            self.db.query(Order)
            .filter(Order.id == order_id, Order.tenant_id == self.tenant_id)
            .with_for_update()
            .first()
        )
        if order is None:
            raise OrderNotFound(order_id)
        if order.archived_at is None:
            raise TestOrderPurgeBlocked(order_id, ["order_not_archived"])

        blockers = self._find_blockers(order)
        if blockers:
            raise TestOrderPurgeBlocked(order_id, blockers)

        payment = self.db.query(Payment).filter(
            Payment.tenant_id == self.tenant_id,
            Payment.order_id == order_id,
        ).with_for_update().first()
        item_count = self.db.query(OrderItem).filter(
            OrderItem.tenant_id == self.tenant_id,
            OrderItem.order_id == order_id,
        ).count()

        production_units = self.db.query(ProductionUnit).filter(
            ProductionUnit.tenant_id == self.tenant_id,
            ProductionUnit.order_id == order_id,
        ).with_for_update().all()

        # The ORM relationship has delete-orphan for items/flavors. Payment is
        # explicitly deleted because its FK is not CASCADE. Production units
        # must be removed before order items because their FK is RESTRICT.
        for unit in production_units:
            self.db.delete(unit)
        try:
            # Force the KDS rows out first. This makes the deletion order
            # explicit while keeping the whole operation in one transaction.
            self.db.flush()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        if payment is not None:
            self.db.delete(payment)
        self.db.delete(order)
        self.db.add(AdminAuditLog(
            id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.actor_id,
            user_name=self.actor_name,
            action=self.AUDIT_ACTION,
            module_key="pedidos",
            entity_type="order",
            entity_id=order_id,
            old_value=json.dumps({"archived_at": order.archived_at.isoformat()}, ensure_ascii=False),
            new_value=json.dumps({"purged": True, "reason": reason, "confirmation": payload["confirmation"]}, ensure_ascii=False),
            ip_address=self.ip_address,
            user_agent=self.user_agent,
        ))
        if idempotency_record is not None:
            idempotency_record.status = "completed"
            idempotency_record.resource_id = order_id

        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise
        return {
            "status": "purged",
            "order_id": order_id,
            "deleted_payment": payment is not None,
            "deleted_order_items": item_count,
        }

    def _find_blockers(self, order: Order) -> list[str]:
        try:
            return self._find_blockers_checked(order)
        except SQLAlchemyError:
            return ["dependency_verification_failed"]

    def _find_blockers_checked(self, order: Order) -> list[str]:
        blockers: list[str] = []
        blockers.extend(self._find_production_unit_blockers(order.id))
        payment = self.db.query(Payment).filter(
            Payment.tenant_id == self.tenant_id, Payment.order_id == order.id,
        ).first()
        if payment is not None:
            method = payment.method.value if hasattr(payment.method, "value") else str(payment.method)
            provider = str(payment.provider or "").strip().lower()
            gateway = str(payment.gateway or "").strip().lower()
            if method != PaymentMethod.cash.value:
                blockers.append("payment_not_manual")
            if provider not in {"", "manual", "mock"} or gateway not in {"", "manual", "mock"}:
                blockers.append("payment_external_provider")
            if not self.ALLOW_MANUAL_TEST_EXTERNAL_METADATA and any(getattr(payment, field, None) for field in (
                "provider_payment_id", "mercado_pago_payment_id", "transaction_id", "external_reference",
            )):
                blockers.append("payment_external_reference")
            if payment.refunded_at is not None or payment.cancelled_at is not None:
                blockers.append("payment_refunded_or_cancelled")
            if self.db.query(PaymentEvent).filter(
                PaymentEvent.tenant_id == self.tenant_id,
                PaymentEvent.provider_payment_id.is_not(None),
                PaymentEvent.provider_payment_id.in_([
                    value for value in (payment.provider_payment_id, payment.mercado_pago_payment_id) if value
                ] or ["__none__"]),
            ).first() is not None:
                blockers.append("protected_payment_event")

        transaction_query = self.db.query(FinanceTransaction).filter(
            FinanceTransaction.tenant_id == self.tenant_id,
            FinanceTransaction.order_id == order.id,
        )
        transactions = transaction_query.all()
        if transactions:
            blockers.append("finance_transactions")
            transaction_ids = [row.id for row in transactions]
            if self.db.query(FinanceSettlement).filter(
                FinanceSettlement.tenant_id == self.tenant_id,
                FinanceSettlement.transaction_id.in_(transaction_ids),
            ).first() is not None:
                blockers.append("finance_settlements")
            if self.db.query(FinanceObligation).filter(
                FinanceObligation.tenant_id == self.tenant_id,
                FinanceObligation.id.in_([
                    row.obligation_id for row in transactions if row.obligation_id
                ] or ["__none__"]),
            ).first() is not None:
                blockers.append("finance_obligations")

        checks = (
            (FiscalDocument, "order_id", "fiscal_documents"),
            (Delivery, "order_id", "delivery"),
            (DeliveryItemConfirmation, "order_id", "delivery_item_confirmations"),
            (KdsDeliveryAudit, "order_id", "kds_audits"),
        )
        for model, field, label in checks:
            if self.db.query(model).filter(
                getattr(model, field) == order.id,
                getattr(model, "tenant_id") == self.tenant_id,
            ).first() is not None:
                blockers.append(label)

        # Any direct FK to orders not explicitly allowed is blocked. This keeps
        # future order-related tables fail-closed without a migration.
        try:
            inspector = inspect(self.db.get_bind())
            for table_name in inspector.get_table_names(schema="public"):
                if table_name in self.ALLOWED_ORDER_REFERENCES or table_name == "orders":
                    continue
                for fk in inspector.get_foreign_keys(table_name, schema="public"):
                    if fk.get("referred_table") != "orders" or "order_id" not in (fk.get("constrained_columns") or []):
                        continue
                    if not self._table_has_row(table_name, order.id):
                        continue
                    blockers.append(f"unverified_dependency:{table_name}")
        except Exception:
            blockers.append("dependency_verification_unavailable")

        return list(dict.fromkeys(blockers))

    def _find_production_unit_blockers(self, order_id: str) -> list[str]:
        """Validate the explicit KDS boundary before allowing an order purge.

        Production units are removable only when they are still unassigned or
        cancelled and have no attempts, consumption, assignments, audit, or
        other child record. Any verification failure blocks the operation.
        """
        try:
            units = self.db.query(ProductionUnit).filter(
                ProductionUnit.tenant_id == self.tenant_id,
                ProductionUnit.order_id == order_id,
            ).with_for_update().all()
            if not units:
                return []

            blockers: list[str] = []
            unit_ids = [unit.id for unit in units]
            attempt_ids: list[str] | None = None
            unsafe = [
                unit for unit in units
                if str(unit.state or "").strip().lower() not in self.SAFE_PRODUCTION_UNIT_STATES
            ]
            if unsafe:
                blockers.append("production_units_unsafe_state")

            attempt_query = self.db.query(ProductionAttempt).filter(
                ProductionAttempt.tenant_id == self.tenant_id,
                ProductionAttempt.production_unit_id.in_(unit_ids),
            )
            if self.ALLOW_CANCELLED_PRODUCTION_ATTEMPTS:
                attempts = attempt_query.all()
                attempt_ids = [attempt.id for attempt in attempts]
                unsafe_attempt = any(
                    str(attempt.state or "").strip().lower() != "cancelled"
                    or any(getattr(attempt, field, None) is not None for field in self.PRODUCTION_ATTEMPT_EXECUTION_FIELDS)
                    for attempt in attempts
                )
                if unsafe_attempt:
                    blockers.append("production_attempts")
            elif attempt_query.first() is not None:
                blockers.append("production_attempts")

            # These checks are intentionally independent of attempts. They
            # protect against legacy/orphaned rows and keep the purge fail-closed.
            attempt_ids = attempt_ids or self._production_attempt_ids(unit_ids)
            if self.db.query(ProductionAttemptConsumption).filter(
                ProductionAttemptConsumption.tenant_id == self.tenant_id,
                ProductionAttemptConsumption.attempt_id.in_(
                    attempt_ids or ["__none__"]
                ),
            ).first() is not None:
                blockers.append("production_attempt_consumptions")

            if self.db.query(KdsAssignment).filter(
                KdsAssignment.tenant_id == self.tenant_id,
                KdsAssignment.attempt_id.in_(
                    attempt_ids or ["__none__"]
                ),
            ).first() is not None:
                blockers.append("kds_assignments")

            blockers.extend(self._find_production_unit_child_blockers(unit_ids))
            return list(dict.fromkeys(blockers))
        except Exception:
            return ["production_dependency_verification_failed"]

    def _production_attempt_ids(self, unit_ids: list[str]) -> list[str]:
        rows = self.db.query(ProductionAttempt.id).filter(
            ProductionAttempt.tenant_id == self.tenant_id,
            ProductionAttempt.production_unit_id.in_(unit_ids),
        ).all()
        return [row[0] if isinstance(row, tuple) else row.id for row in rows]

    def _find_production_unit_child_blockers(self, unit_ids: list[str]) -> list[str]:
        """Discover future/vision children by FK metadata, never by guessing."""
        blockers: list[str] = []
        inspector = inspect(self.db.get_bind())
        protected = {
            "production_attempts",
            "production_attempt_consumptions",
            "kds_assignments",
            "production_units",
        }
        for table_name in inspector.get_table_names(schema="public"):
            if table_name in protected:
                continue
            for fk in inspector.get_foreign_keys(table_name, schema="public"):
                referred = fk.get("referred_table")
                columns = fk.get("constrained_columns") or []
                if referred not in {"production_units", "production_attempts"}:
                    continue
                reference_column = "production_unit_id" if "production_unit_id" in columns else "production_attempt_id"
                if reference_column not in columns:
                    continue
                if self._table_has_any_reference(table_name, reference_column, unit_ids):
                    blockers.append(f"production_unit_dependency:{table_name}")
        return blockers

    def _table_has_any_reference(self, table_name: str, column: str, values: list[str]) -> bool:
        inspector = inspect(self.db.get_bind())
        columns = {item["name"] for item in inspector.get_columns(table_name, schema="public")}
        if column not in columns:
            return True
        params: dict[str, Any] = {"values": values, "tenant_id": self.tenant_id}
        where = f'"{column}" = ANY(:values)'
        if "tenant_id" in columns:
            where += ' AND "tenant_id" = :tenant_id'
        statement = text(f'SELECT 1 FROM "{table_name}" WHERE {where} LIMIT 1')
        return self.db.execute(statement, params).first() is not None

    def _table_has_row(self, table_name: str, order_id: str) -> bool:
        inspector = inspect(self.db.get_bind())
        columns = {column["name"] for column in inspector.get_columns(table_name, schema="public")}
        if "order_id" not in columns:
            return True
        params = {"order_id": order_id}
        where = '"order_id" = :order_id'
        if "tenant_id" in columns:
            where += ' AND "tenant_id" = :tenant_id'
            params["tenant_id"] = self.tenant_id
        statement = text(f'SELECT 1 FROM "{table_name}" WHERE {where} LIMIT 1')
        return self.db.execute(statement, params).first() is not None


class ConfirmedSimulationPurgeService(OrderTestPurgeService):
    """Explicit simulation purge; never weakens the regular purge contract."""

    OPERATION = "orders.purge_confirmed_simulation"
    CONFIRMATION = "PURGE_CONFIRMED_SIMULATION"
    AUDIT_ACTION = "purge_confirmed_simulation"
    ALLOW_MANUAL_TEST_EXTERNAL_METADATA = True
    SAFE_PRODUCTION_UNIT_STATES = frozenset({"cancelled"})
    ALLOW_CANCELLED_PRODUCTION_ATTEMPTS = True

    def purge(self, *, order_id: str, confirmation: str, reason: str, idempotency_key: str) -> dict[str, Any]:
        return super().purge(order_id=order_id, confirmation=confirmation, reason=reason, idempotency_key=idempotency_key)

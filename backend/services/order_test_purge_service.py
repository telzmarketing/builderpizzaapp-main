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
from backend.models.rbac import AdminAuditLog
from backend.services.idempotency_service import IdempotencyService


class OrderTestPurgeService:
    """Fail-closed, tenant-scoped physical purge for explicitly confirmed tests."""

    OPERATION = "orders.purge_test"
    ALLOWED_ORDER_REFERENCES = frozenset({"order_items", "payments"})

    def __init__(self, db: Session, *, tenant_id: str, actor_id: str, actor_name: str,
                 ip_address: str | None = None, user_agent: str | None = None):
        self.db = db
        self.tenant_id = tenant_id
        self.actor_id = actor_id
        self.actor_name = actor_name
        self.ip_address = ip_address
        self.user_agent = user_agent

    def purge(self, *, order_id: str, confirmation: str, reason: str, idempotency_key: str) -> dict[str, Any]:
        if confirmation != "PURGE_TEST_ORDER":
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

        # The ORM relationship has delete-orphan for items/flavors. Payment is
        # explicitly deleted because its FK is not CASCADE.
        if payment is not None:
            self.db.delete(payment)
        self.db.delete(order)
        self.db.add(AdminAuditLog(
            id=str(uuid.uuid4()),
            tenant_id=self.tenant_id,
            user_id=self.actor_id,
            user_name=self.actor_name,
            action="purge_test_order",
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
            if any(getattr(payment, field, None) for field in (
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

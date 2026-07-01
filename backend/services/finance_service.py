from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from backend.core.exceptions import DomainError
from backend.models.finance import FinanceAccount, FinanceCategory, FinanceCounterparty, FinanceSettlement, FinanceTransaction
from backend.models.gestao import GestaoModuleSettings
from backend.models.inventory import InventoryPurchase
from backend.models.cmv import OrderCmvSnapshot
from backend.models.order import Order
from backend.models.payment import Payment
from backend.schemas.finance import FinanceAccountIn, FinanceCategoryIn, FinanceCounterpartyIn, FinanceSettlementIn, FinanceTransactionIn

TENANT_ID = "default"


class FinanceNotFound(DomainError):
    http_status = 404

    def __init__(self, entity: str):
        super().__init__(f"{entity} nao encontrado.", code="FinanceNotFound")


class FinanceInvalidReference(DomainError):
    def __init__(self, message: str):
        super().__init__(message, code="FinanceInvalidReference")


class FinanceService:
    def __init__(self, db: Session, tenant_id: str = TENANT_ID):
        self._db = db
        self._tenant_id = tenant_id

    def overview(self) -> dict:
        return {
            "summary": self.summary(),
            "management": self.management_summary(),
            "accounts": self.list_accounts(),
            "categories": self.list_categories(),
            "counterparties": self.list_counterparties(),
            "transactions": self.list_transactions(),
        }

    def summary(self) -> dict:
        transactions = (
            self._db.query(FinanceTransaction)
            .filter(FinanceTransaction.tenant_id == self._tenant_id)
            .options(joinedload(FinanceTransaction.settlements))
            .filter(FinanceTransaction.status != "cancelled")
            .all()
        )
        accounts = self._db.query(FinanceAccount).filter(FinanceAccount.tenant_id == self._tenant_id, FinanceAccount.active == True).all()  # noqa: E712
        income_paid = sum(self._cash_effect(row) for row in transactions if row.entry_type == "income" and row.status in {"partial", "paid"})
        expense_paid = sum(self._cash_effect(row) for row in transactions if row.entry_type == "expense" and row.status in {"partial", "paid"})
        income_pending = sum(self._open_amount(row) for row in transactions if row.entry_type == "income" and row.status in {"pending", "partial"})
        expense_pending = sum(self._open_amount(row) for row in transactions if row.entry_type == "expense" and row.status in {"pending", "partial"})
        opening_balance = sum(float(row.opening_balance or 0.0) for row in accounts)
        today = date.today()
        return {
            "income_paid": round(income_paid, 2),
            "expense_paid": round(expense_paid, 2),
            "income_pending": round(income_pending, 2),
            "expense_pending": round(expense_pending, 2),
            "balance": round(opening_balance + income_paid - expense_paid, 2),
            "overdue_count": sum(1 for row in transactions if row.status == "pending" and row.due_date and row.due_date < today),
            "pending_count": sum(1 for row in transactions if row.status in {"pending", "partial"}),
        }

    def list_accounts(self) -> list[dict]:
        rows = (
            self._db.query(FinanceAccount)
            .filter(FinanceAccount.tenant_id == self._tenant_id)
            .filter(FinanceAccount.active == True)  # noqa: E712
            .order_by(FinanceAccount.name)
            .all()
        )
        balances = self._account_balance_map()
        return [self._serialize_account(row, balances.get(row.id, 0.0)) for row in rows]

    def create_account(self, payload: FinanceAccountIn) -> dict:
        row = FinanceAccount(id=f"fin-acc-{uuid.uuid4().hex[:12]}", tenant_id=self._tenant_id, **payload.model_dump())
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_account(row)

    def update_account(self, account_id: str, payload: FinanceAccountIn) -> dict:
        row = self._get_account(account_id)
        for key, value in payload.model_dump().items():
            setattr(row, key, value)
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_account(row)

    def delete_account(self, account_id: str) -> None:
        row = self._get_account(account_id)
        row.active = False
        self._db.commit()

    def list_categories(self) -> list[dict]:
        rows = (
            self._db.query(FinanceCategory)
            .options(joinedload(FinanceCategory.parent))
            .filter(FinanceCategory.tenant_id == self._tenant_id)
            .filter(FinanceCategory.active == True)  # noqa: E712
            .order_by(FinanceCategory.entry_type, FinanceCategory.name)
            .all()
        )
        return [self._serialize_category(row) for row in rows]

    def create_category(self, payload: FinanceCategoryIn) -> dict:
        data = payload.model_dump()
        self._validate_category_refs(data)
        row = FinanceCategory(id=f"fin-cat-{uuid.uuid4().hex[:12]}", tenant_id=self._tenant_id, **data)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_category(row)

    def update_category(self, category_id: str, payload: FinanceCategoryIn) -> dict:
        data = payload.model_dump()
        self._validate_category_refs(data, category_id)
        row = self._get_category(category_id)
        for key, value in data.items():
            setattr(row, key, value)
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_category(row)

    def delete_category(self, category_id: str) -> None:
        row = self._get_category(category_id)
        row.active = False
        self._db.commit()

    def list_counterparties(self) -> list[dict]:
        rows = (
            self._db.query(FinanceCounterparty)
            .filter(FinanceCounterparty.tenant_id == self._tenant_id)
            .filter(FinanceCounterparty.active == True)  # noqa: E712
            .order_by(FinanceCounterparty.name)
            .all()
        )
        open_amounts = self._counterparty_open_amount_map()
        return [self._serialize_counterparty(row, open_amounts.get(row.id, 0.0)) for row in rows]

    def create_counterparty(self, payload: FinanceCounterpartyIn) -> dict:
        row = FinanceCounterparty(
            id=f"fin-cpt-{uuid.uuid4().hex[:12]}",
            tenant_id=self._tenant_id,
            **payload.model_dump(),
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_counterparty(row)

    def update_counterparty(self, counterparty_id: str, payload: FinanceCounterpartyIn) -> dict:
        row = self._get_counterparty(counterparty_id)
        for key, value in payload.model_dump().items():
            setattr(row, key, value)
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_counterparty(row)

    def delete_counterparty(self, counterparty_id: str) -> None:
        row = self._get_counterparty(counterparty_id)
        row.active = False
        self._db.commit()

    def list_transactions(self) -> list[dict]:
        rows = (
            self._db.query(FinanceTransaction)
            .options(
                joinedload(FinanceTransaction.account),
                joinedload(FinanceTransaction.category),
                joinedload(FinanceTransaction.counterparty),
                joinedload(FinanceTransaction.settlements),
                joinedload(FinanceTransaction.order),
            )
            .filter(FinanceTransaction.tenant_id == self._tenant_id)
            .order_by(FinanceTransaction.competence_date.desc(), FinanceTransaction.created_at.desc())
            .limit(300)
            .all()
        )
        return [self._serialize_transaction(row) for row in rows]

    def management_summary(self) -> dict:
        transactions = (
            self._db.query(FinanceTransaction)
            .options(
                joinedload(FinanceTransaction.category),
                joinedload(FinanceTransaction.order),
                joinedload(FinanceTransaction.settlements),
            )
            .filter(FinanceTransaction.tenant_id == self._tenant_id)
            .filter(FinanceTransaction.status != "cancelled")
            .all()
        )
        cash_income = sum(self._cash_effect(row) for row in transactions if row.entry_type == "income" and row.status in {"partial", "paid"})
        cash_expense = sum(self._cash_effect(row) for row in transactions if row.entry_type == "expense" and row.status in {"partial", "paid"})
        accrual_income = sum(float(row.amount or 0.0) for row in transactions if row.entry_type == "income")
        accrual_expense = sum(float(row.amount or 0.0) for row in transactions if row.entry_type == "expense")
        cmv_count = self._db.query(OrderCmvSnapshot).filter(OrderCmvSnapshot.tenant_id == self._tenant_id).count()
        dre_lines: dict[tuple[str, str], dict] = {}
        origin_lines: dict[tuple[str, str], dict] = {}
        category_lines: dict[tuple[str, str], dict] = {}
        cost_center_lines: dict[tuple[str, str], dict] = {}
        channel_lines: dict[tuple[str, str], dict] = {}

        for row in transactions:
            amount = round(float(row.amount or 0.0), 2)
            dre_group = row.category.dre_group if row.category else "sem_grupo_dre"
            category = row.category.name if row.category else "Sem categoria"
            cost_center = row.cost_center or "Sem centro de custo"
            channel = row.order.sales_channel if row.order and row.order.sales_channel else "Sem canal"
            self._add_dimension(dre_lines, dre_group, row.entry_type, amount)
            self._add_dimension(origin_lines, row.origin_type or "manual", row.entry_type, amount)
            self._add_dimension(category_lines, category, row.entry_type, amount)
            self._add_dimension(cost_center_lines, cost_center, row.entry_type, amount)
            self._add_dimension(channel_lines, channel, row.entry_type, amount)

        dre_status = "complete_with_operational_cmv" if cmv_count else "partial_without_cmv"
        dre_label = "DRE completa com CMV operacional" if cmv_count else "DRE parcial sem CMV"
        return {
            "cash_realized_income": round(cash_income, 2),
            "cash_realized_expense": round(cash_expense, 2),
            "cash_realized_result": round(cash_income - cash_expense, 2),
            "accrual_income": round(accrual_income, 2),
            "accrual_expense": round(accrual_expense, 2),
            "accrual_result": round(accrual_income - accrual_expense, 2),
            "dre_status": dre_status,
            "dre_label": dre_label,
            "dre_lines": [
                {"group": item["label"], "entry_type": item["entry_type"], "amount": item["amount"]}
                for item in self._dimension_rows(dre_lines)
            ],
            "by_origin": [
                {"origin_type": item["label"], "entry_type": item["entry_type"], "amount": item["amount"], "count": item["count"]}
                for item in self._dimension_rows(origin_lines)
            ],
            "by_category": self._dimension_rows(category_lines),
            "by_cost_center": self._dimension_rows(cost_center_lines),
            "by_channel": self._dimension_rows(channel_lines),
        }

    def create_transaction(self, payload: FinanceTransactionIn, admin_id: str | None = None) -> dict:
        data = self._transaction_data(payload)
        data["created_by_admin_id"] = admin_id
        data["updated_by_admin_id"] = admin_id
        row = FinanceTransaction(id=f"fin-trx-{uuid.uuid4().hex[:12]}", tenant_id=self._tenant_id, **data)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_transaction(row)

    def update_transaction(self, transaction_id: str, payload: FinanceTransactionIn, admin_id: str | None = None) -> dict:
        row = self._get_transaction(transaction_id)
        data = self._transaction_data(payload)
        data["updated_by_admin_id"] = admin_id
        for key, value in data.items():
            setattr(row, key, value)
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_transaction(row)

    def delete_transaction(self, transaction_id: str) -> None:
        row = self._get_transaction(transaction_id)
        row.status = "cancelled"
        self._db.commit()

    def sync_payment_confirmed(
        self,
        *,
        payment_id: str,
        order_id: str,
        amount: float,
        gateway: str,
        transaction_id: str | None = None,
    ) -> dict:
        settings = self._module_settings()
        if not settings or not settings.get("auto_create_receivables"):
            return {"created": False, "reason": "disabled"}

        existing = (
            self._db.query(FinanceTransaction)
            .options(joinedload(FinanceTransaction.settlements))
            .filter(
                FinanceTransaction.tenant_id == self._tenant_id,
                FinanceTransaction.origin_type == "payment_receivable",
                FinanceTransaction.origin_id == payment_id,
            )
            .first()
        )
        if existing and any(item.idempotency_key == f"payment-confirmed:{payment_id}" for item in existing.settlements):
            return {"created": False, "reason": "already_synced", "transaction_id": existing.id}

        payment = self._db.query(Payment).filter(Payment.id == payment_id).first()
        order = self._db.query(Order).filter(Order.id == order_id).first()
        paid_at = payment.paid_at if payment and payment.paid_at else datetime.now(timezone.utc)
        receivable_amount = round(float(payment.amount if payment else amount or 0.0), 2)
        if receivable_amount <= 0:
            return {"created": False, "reason": "invalid_amount"}

        account_id = settings.get("default_receivable_account_id") or None
        if account_id:
            self._get_account(str(account_id))

        if existing:
            row = existing
        else:
            order_label = order.order_code or order.id if order else order_id
            row = FinanceTransaction(
                id=f"fin-trx-{uuid.uuid4().hex[:12]}",
                tenant_id=self._tenant_id,
                account_id=account_id,
                category_id=self._ensure_category("Receita de pedidos", "income", "gross_revenue"),
                cost_center=order.sales_channel if order and order.sales_channel else "delivery",
                entry_type="income",
                status="paid",
                description=f"Recebimento do pedido {order_label}",
                amount=receivable_amount,
                paid_amount=0.0,
                competence_date=paid_at.date(),
                due_date=paid_at.date(),
                paid_at=paid_at,
                payment_method=(payment.method.value if payment and hasattr(payment.method, "value") else str(payment.method)) if payment else gateway,
                payment_reference=transaction_id or (payment.transaction_id if payment else None),
                order_id=order_id,
                payment_id=payment_id,
                origin_type="payment_receivable",
                origin_id=payment_id,
                notes=self._payment_composition_notes(order),
            )
            self._db.add(row)
            self._db.flush()

        settlement = FinanceSettlement(
            id=f"fin-set-{uuid.uuid4().hex[:12]}",
            tenant_id=self._tenant_id,
            transaction_id=row.id,
            account_id=account_id or row.account_id,
            settled_at=paid_at,
            principal_amount=receivable_amount,
            net_amount=receivable_amount,
            payment_method=row.payment_method,
            payment_reference=transaction_id or row.payment_reference,
            origin_type="payment_confirmed",
            origin_id=payment_id,
            idempotency_key=f"payment-confirmed:{payment_id}",
            notes="Liquidacao automatica por pagamento confirmado.",
        )
        self._db.add(settlement)
        row.account_id = account_id or row.account_id
        row.status = "paid"
        row.paid_amount = round(float(row.paid_amount or 0.0) + receivable_amount, 2)
        row.net_amount = round(float(row.net_amount or 0.0) + receivable_amount, 2)
        row.paid_at = row.paid_at or paid_at
        row.payment_reference = transaction_id or row.payment_reference
        try:
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            existing_after_race = (
                self._db.query(FinanceTransaction)
                .filter(
                    FinanceTransaction.tenant_id == self._tenant_id,
                    FinanceTransaction.origin_type == "payment_receivable",
                    FinanceTransaction.origin_id == payment_id,
                )
                .first()
            )
            return {
                "created": False,
                "reason": "already_synced",
                "transaction_id": existing_after_race.id if existing_after_race else None,
            }
        self._db.refresh(row)
        return {"created": True, "reason": "ok", "transaction_id": row.id}

    def sync_payment_reversed(
        self,
        *,
        payment_id: str,
        order_id: str,
        amount: float,
        gateway: str,
        transaction_id: str | None = None,
        reason: str | None = None,
    ) -> dict:
        row = (
            self._db.query(FinanceTransaction)
            .options(joinedload(FinanceTransaction.settlements))
            .filter(
                FinanceTransaction.tenant_id == self._tenant_id,
                FinanceTransaction.origin_type == "payment_receivable",
                FinanceTransaction.origin_id == payment_id,
            )
            .first()
        )
        if not row:
            return {"reversed": False, "reason": "no_receivable"}

        idempotency_key = f"payment-reversed:{payment_id}"
        if any(item.idempotency_key == idempotency_key for item in row.settlements):
            return {"reversed": False, "reason": "already_reversed", "transaction_id": row.id}

        original_settlements = [
            item
            for item in row.settlements
            if item.origin_type == "payment_confirmed"
            and item.origin_id == payment_id
            and item.cancelled_at is None
        ]
        if not original_settlements:
            return {"reversed": False, "reason": "no_settlement", "transaction_id": row.id}

        now = datetime.now(timezone.utc)
        account_id = next((item.account_id for item in original_settlements if item.account_id), row.account_id)
        for item in original_settlements:
            item.cancelled_at = now
        settlement = FinanceSettlement(
            id=f"fin-set-{uuid.uuid4().hex[:12]}",
            tenant_id=self._tenant_id,
            transaction_id=row.id,
            account_id=account_id,
            settled_at=now,
            principal_amount=0.0,
            net_amount=0.0,
            payment_method=row.payment_method or gateway,
            payment_reference=transaction_id or row.payment_reference,
            origin_type="payment_reversed",
            origin_id=payment_id,
            idempotency_key=idempotency_key,
            notes=f"Reversao automatica por estorno de pagamento. {reason or ''}".strip(),
        )
        self._db.add(settlement)

        row.status = "cancelled"
        row.paid_amount = 0.0
        row.net_amount = 0.0
        row.payment_reference = transaction_id or row.payment_reference
        row.notes = (row.notes or "") + "\nRevertido automaticamente por estorno de pagamento."

        try:
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            return {"reversed": False, "reason": "already_reversed", "transaction_id": row.id}
        self._db.refresh(row)
        return {"reversed": True, "reason": "ok", "transaction_id": row.id}

    def sync_purchase_confirmed(self, *, purchase_id: str) -> dict:
        settings = self._module_settings()
        if not settings or not settings.get("auto_create_payables_from_purchases"):
            return {"created": False, "reason": "disabled"}

        purchase = (
            self._db.query(InventoryPurchase)
            .options(joinedload(InventoryPurchase.supplier))
            .filter(InventoryPurchase.tenant_id == self._tenant_id, InventoryPurchase.id == purchase_id)
            .first()
        )
        if not purchase or purchase.status != "confirmed":
            return {"created": False, "reason": "purchase_not_confirmed"}
        amount = round(float(purchase.total_amount or 0.0), 2)
        if amount <= 0:
            return {"created": False, "reason": "invalid_amount"}

        existing = (
            self._db.query(FinanceTransaction)
            .filter(
                FinanceTransaction.tenant_id == self._tenant_id,
                FinanceTransaction.origin_type == "inventory_purchase_payable",
                FinanceTransaction.origin_id == purchase.id,
            )
            .first()
        )
        if existing:
            return {"created": False, "reason": "already_synced", "transaction_id": existing.id}

        supplier = purchase.supplier
        counterparty_id = self._ensure_supplier_counterparty(supplier) if supplier else None
        account_id = settings.get("default_payable_account_id") or None
        if account_id:
            self._get_account(str(account_id))
        due_date = purchase.expected_date or date.today()
        row = FinanceTransaction(
            id=f"fin-trx-{uuid.uuid4().hex[:12]}",
            tenant_id=self._tenant_id,
            account_id=account_id,
            category_id=self._ensure_category("Compras de estoque", "expense", "inventory_purchases"),
            counterparty_id=counterparty_id,
            counterparty_type="supplier",
            counterparty_name=supplier.name if supplier else "Fornecedor nao informado",
            counterparty_document=supplier.document if supplier else None,
            cost_center="estoque",
            entry_type="expense",
            status="pending",
            description=f"Compra de estoque {purchase.invoice_number or purchase.id}",
            amount=amount,
            competence_date=due_date,
            due_date=due_date,
            document_number=purchase.invoice_number,
            document_date=due_date,
            inventory_purchase_id=purchase.id,
            origin_type="inventory_purchase_payable",
            origin_id=purchase.id,
            notes="Criado automaticamente por compra de estoque confirmada.",
        )
        self._db.add(row)
        try:
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            return {"created": False, "reason": "already_synced", "transaction_id": None}
        self._db.refresh(row)
        return {"created": True, "reason": "ok", "transaction_id": row.id}

    def settle_transaction(self, transaction_id: str, payload: FinanceSettlementIn, admin_id: str | None = None) -> dict:
        row = self._get_transaction(transaction_id)
        if row.status == "cancelled":
            raise FinanceInvalidReference("Lancamento cancelado nao pode ser baixado.")
        if payload.account_id:
            self._get_account(payload.account_id)

        interest_amount = round(float(payload.interest_amount or 0.0), 2)
        fine_amount = round(float(payload.fine_amount or 0.0), 2)
        discount_amount = round(float(payload.discount_amount or 0.0), 2)
        fee_amount = round(float(payload.fee_amount or 0.0), 2)
        adjusted_total = self._adjusted_total(row, extra_interest=interest_amount, extra_fine=fine_amount, extra_discount=discount_amount)
        if adjusted_total <= 0:
            raise FinanceInvalidReference("O total ajustado precisa ser maior que zero.")

        open_amount = round(max(0.0, adjusted_total - float(row.paid_amount or 0.0)), 2)
        paid_amount = round(float(payload.paid_amount if payload.paid_amount is not None else open_amount), 2)
        if paid_amount <= 0:
            raise FinanceInvalidReference("Informe um valor de baixa maior que zero.")
        if paid_amount > open_amount:
            raise FinanceInvalidReference("O valor baixado nao pode ser maior que o saldo em aberto.")

        settled_at = payload.paid_at or datetime.now(timezone.utc)
        net_amount = self._net_amount(row.entry_type, paid_amount, fee_amount)
        settlement = FinanceSettlement(
            id=f"fin-set-{uuid.uuid4().hex[:12]}",
            tenant_id=self._tenant_id,
            transaction_id=row.id,
            account_id=payload.account_id or row.account_id,
            settled_at=settled_at,
            principal_amount=paid_amount,
            interest_amount=interest_amount,
            fine_amount=fine_amount,
            discount_amount=discount_amount,
            fee_amount=fee_amount,
            net_amount=net_amount,
            payment_method=payload.payment_method or row.payment_method,
            payment_reference=payload.payment_reference or row.payment_reference,
            created_by_admin_id=admin_id,
            origin_type="manual",
            notes=payload.notes,
        )
        self._db.add(settlement)

        row.account_id = payload.account_id or row.account_id
        row.interest_amount = round(float(row.interest_amount or 0.0) + interest_amount, 2)
        row.fine_amount = round(float(row.fine_amount or 0.0) + fine_amount, 2)
        row.discount_amount = round(float(row.discount_amount or 0.0) + discount_amount, 2)
        row.fee_amount = round(float(row.fee_amount or 0.0) + fee_amount, 2)
        row.paid_amount = round(float(row.paid_amount or 0.0) + paid_amount, 2)
        row.net_amount = round(float(row.net_amount or 0.0) + net_amount, 2)
        final_total = self._adjusted_total(row)
        row.status = "paid" if row.paid_amount >= final_total else "partial"
        row.paid_at = settled_at
        row.payment_method = payload.payment_method or row.payment_method
        row.payment_reference = payload.payment_reference or row.payment_reference
        row.updated_by_admin_id = admin_id
        if payload.notes:
            row.notes = payload.notes

        self._db.commit()
        self._db.refresh(row)
        return self._serialize_transaction(row)

    def _transaction_data(self, payload: FinanceTransactionIn) -> dict:
        data = payload.model_dump()
        if data.get("account_id"):
            self._get_account(data["account_id"])
        if data.get("category_id"):
            category = self._get_category(data["category_id"])
            if category.entry_type != data["entry_type"]:
                raise FinanceInvalidReference("A categoria escolhida nao corresponde ao tipo do lancamento.")
        if data.get("cost_center"):
            data["cost_center"] = str(data["cost_center"]).strip() or None
        if data.get("counterparty_id"):
            counterparty = self._get_counterparty(data["counterparty_id"])
            data["counterparty_type"] = data.get("counterparty_type") or counterparty.counterparty_type
            data["counterparty_name"] = data.get("counterparty_name") or counterparty.name
            data["counterparty_document"] = data.get("counterparty_document") or counterparty.document
        if int(data.get("installment_number") or 1) > int(data.get("installment_total") or 1):
            raise FinanceInvalidReference("A parcela atual nao pode ser maior que o total de parcelas.")
        if data["status"] == "paid" and not data.get("paid_at"):
            data["paid_at"] = datetime.now(timezone.utc)
        for key in ("interest_amount", "fine_amount", "discount_amount", "fee_amount", "paid_amount", "net_amount"):
            data[key] = round(float(data.get(key) or 0.0), 2)
        adjusted_total = self._adjusted_total_from_data(data)
        if data["status"] == "paid" and not data.get("paid_amount"):
            data["paid_amount"] = adjusted_total
        if data["status"] == "paid":
            data["net_amount"] = data.get("net_amount") or self._net_amount(data["entry_type"], data["paid_amount"], data["fee_amount"])
        if data["status"] == "partial":
            if data["paid_amount"] <= 0 or data["paid_amount"] >= adjusted_total:
                raise FinanceInvalidReference("Lancamento parcial precisa ter valor baixado menor que o total ajustado.")
            data["net_amount"] = data.get("net_amount") or self._net_amount(data["entry_type"], data["paid_amount"], data["fee_amount"])
            data["paid_at"] = data.get("paid_at") or datetime.now(timezone.utc)
        if data["status"] == "paid" and data["paid_amount"] > adjusted_total:
            raise FinanceInvalidReference("O valor pago nao pode ser maior que o total ajustado.")
        if data["status"] == "pending":
            data["paid_at"] = None
            data["paid_amount"] = 0.0
            data["net_amount"] = 0.0
        return data

    def _module_settings(self) -> dict:
        item = (
            self._db.query(GestaoModuleSettings)
            .filter(
                GestaoModuleSettings.tenant_id == self._tenant_id,
                GestaoModuleSettings.module_key == "finance",
            )
            .first()
        )
        if not item or not item.enabled or item.status == "disabled":
            return {}
        try:
            return json.loads(item.settings_json or "{}")
        except json.JSONDecodeError:
            return {}

    def _validate_category_refs(self, data: dict, current_id: str | None = None) -> None:
        parent_id = data.get("parent_id")
        if not parent_id:
            return
        if current_id and parent_id == current_id:
            raise FinanceInvalidReference("A categoria nao pode ser pai dela mesma.")
        parent = self._get_category(parent_id)
        if parent.entry_type != data["entry_type"]:
            raise FinanceInvalidReference("A categoria pai precisa ter o mesmo tipo.")

    def _get_account(self, account_id: str) -> FinanceAccount:
        row = (
            self._db.query(FinanceAccount)
            .filter(FinanceAccount.tenant_id == self._tenant_id, FinanceAccount.id == account_id, FinanceAccount.active == True)
            .first()
        )
        if not row:
            raise FinanceNotFound("Conta")
        return row

    def _get_category(self, category_id: str) -> FinanceCategory:
        row = (
            self._db.query(FinanceCategory)
            .filter(FinanceCategory.tenant_id == self._tenant_id, FinanceCategory.id == category_id, FinanceCategory.active == True)
            .first()
        )
        if not row:
            raise FinanceNotFound("Categoria")
        return row

    def _get_counterparty(self, counterparty_id: str) -> FinanceCounterparty:
        row = (
            self._db.query(FinanceCounterparty)
            .filter(
                FinanceCounterparty.tenant_id == self._tenant_id,
                FinanceCounterparty.id == counterparty_id,
                FinanceCounterparty.active == True,
            )
            .first()
        )
        if not row:
            raise FinanceNotFound("Favorecido")
        return row

    def _get_transaction(self, transaction_id: str) -> FinanceTransaction:
        row = (
            self._db.query(FinanceTransaction)
            .filter(FinanceTransaction.tenant_id == self._tenant_id, FinanceTransaction.id == transaction_id)
            .first()
        )
        if not row:
            raise FinanceNotFound("Lancamento")
        return row

    def _account_balance_map(self) -> dict[str, float]:
        rows = (
            self._db.query(FinanceSettlement)
            .options(joinedload(FinanceSettlement.transaction))
            .filter(FinanceSettlement.tenant_id == self._tenant_id)
            .filter(FinanceSettlement.cancelled_at.is_(None))
            .all()
        )
        balances: dict[str, float] = {}
        for settlement in rows:
            if not settlement.account_id or not settlement.transaction:
                continue
            delta = float(settlement.net_amount or 0.0) if settlement.transaction.entry_type == "income" else -float(settlement.net_amount or 0.0)
            balances[settlement.account_id] = balances.get(settlement.account_id, 0.0) + delta
        return balances

    def _counterparty_open_amount_map(self) -> dict[str, float]:
        rows = (
            self._db.query(FinanceTransaction)
            .filter(FinanceTransaction.tenant_id == self._tenant_id)
            .filter(FinanceTransaction.status == "pending")
            .all()
        )
        totals: dict[str, float] = {}
        for row in rows:
            if not row.counterparty_id:
                continue
            totals[row.counterparty_id] = totals.get(row.counterparty_id, 0.0) + self._open_amount(row)
        return totals

    def _adjusted_total(
        self,
        row: FinanceTransaction,
        *,
        extra_interest: float = 0.0,
        extra_fine: float = 0.0,
        extra_discount: float = 0.0,
    ) -> float:
        return round(
            float(row.amount or 0.0)
            + float(row.interest_amount or 0.0)
            + float(extra_interest or 0.0)
            + float(row.fine_amount or 0.0)
            + float(extra_fine or 0.0)
            - float(row.discount_amount or 0.0)
            - float(extra_discount or 0.0),
            2,
        )

    def _adjusted_total_from_data(self, data: dict) -> float:
        return round(
            float(data.get("amount") or 0.0)
            + float(data.get("interest_amount") or 0.0)
            + float(data.get("fine_amount") or 0.0)
            - float(data.get("discount_amount") or 0.0),
            2,
        )

    def _net_amount(self, entry_type: str, paid_amount: float, fee_amount: float) -> float:
        fee = float(fee_amount or 0.0)
        paid = float(paid_amount or 0.0)
        return round(max(0.0, paid - fee) if entry_type == "income" else paid + fee, 2)

    def _cash_effect(self, row: FinanceTransaction) -> float:
        value = float(row.net_amount or 0.0)
        if value > 0:
            return value
        if row.status in {"partial", "paid"}:
            return self._net_amount(row.entry_type, float(row.paid_amount or 0.0), float(row.fee_amount or 0.0))
        return 0.0

    def _open_amount(self, row: FinanceTransaction) -> float:
        if row.status == "paid":
            return 0.0
        return round(max(0.0, self._adjusted_total(row) - float(row.paid_amount or 0.0)), 2)

    def _serialize_account(self, row: FinanceAccount, movement_balance: float | None = None) -> dict:
        if movement_balance is None:
            movement_balance = self._account_balance_map().get(row.id, 0.0)
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "name": row.name,
            "account_type": row.account_type,
            "opening_balance": row.opening_balance,
            "current_balance": round(float(row.opening_balance or 0.0) + float(movement_balance or 0.0), 2),
            "notes": row.notes,
            "active": row.active,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def _serialize_category(self, row: FinanceCategory) -> dict:
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "name": row.name,
            "entry_type": row.entry_type,
            "dre_group": row.dre_group,
            "parent_id": row.parent_id,
            "parent_name": row.parent.name if row.parent else None,
            "notes": row.notes,
            "active": row.active,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def _serialize_counterparty(self, row: FinanceCounterparty, open_amount: float | None = None) -> dict:
        if open_amount is None:
            open_amount = self._counterparty_open_amount_map().get(row.id, 0.0)
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "name": row.name,
            "counterparty_type": row.counterparty_type,
            "document": row.document,
            "phone": row.phone,
            "email": row.email,
            "notes": row.notes,
            "active": row.active,
            "open_amount": round(float(open_amount or 0.0), 2),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def _serialize_transaction(self, row: FinanceTransaction) -> dict:
        today = date.today()
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "account_id": row.account_id,
            "account_name": row.account.name if row.account else None,
            "category_id": row.category_id,
            "category_name": row.category.name if row.category else None,
            "cost_center": row.cost_center,
            "counterparty_id": row.counterparty_id,
            "counterparty_type": row.counterparty_type,
            "counterparty_name": row.counterparty_name or (row.counterparty.name if row.counterparty else None),
            "counterparty_document": row.counterparty_document,
            "entry_type": row.entry_type,
            "status": row.status,
            "description": row.description,
            "amount": row.amount,
            "paid_amount": row.paid_amount,
            "interest_amount": row.interest_amount,
            "fine_amount": row.fine_amount,
            "discount_amount": row.discount_amount,
            "fee_amount": row.fee_amount,
            "net_amount": row.net_amount,
            "competence_date": row.competence_date,
            "due_date": row.due_date,
            "paid_at": row.paid_at,
            "document_number": row.document_number,
            "document_date": row.document_date,
            "payment_method": row.payment_method,
            "payment_reference": row.payment_reference,
            "installment_group_id": row.installment_group_id,
            "installment_number": row.installment_number,
            "installment_total": row.installment_total,
            "order_id": row.order_id,
            "payment_id": row.payment_id,
            "inventory_purchase_id": row.inventory_purchase_id,
            "created_by_admin_id": row.created_by_admin_id,
            "updated_by_admin_id": row.updated_by_admin_id,
            "origin_type": row.origin_type,
            "origin_id": row.origin_id,
            "notes": row.notes,
            "overdue": bool(row.status == "pending" and row.due_date and row.due_date < today),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def _ensure_category(self, name: str, entry_type: str, dre_group: str) -> str:
        row = (
            self._db.query(FinanceCategory)
            .filter(
                FinanceCategory.tenant_id == self._tenant_id,
                FinanceCategory.entry_type == entry_type,
                FinanceCategory.name == name,
            )
            .first()
        )
        if row:
            return row.id
        row = FinanceCategory(
            id=f"fin-cat-{uuid.uuid4().hex[:12]}",
            tenant_id=self._tenant_id,
            name=name,
            entry_type=entry_type,
            dre_group=dre_group,
            active=True,
        )
        self._db.add(row)
        self._db.flush()
        return row.id

    def _ensure_supplier_counterparty(self, supplier) -> str:
        row = (
            self._db.query(FinanceCounterparty)
            .filter(
                FinanceCounterparty.tenant_id == self._tenant_id,
                FinanceCounterparty.counterparty_type == "supplier",
                FinanceCounterparty.document == supplier.document,
            )
            .first()
            if supplier.document
            else None
        )
        if not row:
            row = (
                self._db.query(FinanceCounterparty)
                .filter(
                    FinanceCounterparty.tenant_id == self._tenant_id,
                    FinanceCounterparty.counterparty_type == "supplier",
                    FinanceCounterparty.name == supplier.name,
                )
                .first()
            )
        if row:
            return row.id
        row = FinanceCounterparty(
            id=f"fin-cpt-{uuid.uuid4().hex[:12]}",
            tenant_id=self._tenant_id,
            name=supplier.name,
            counterparty_type="supplier",
            document=supplier.document,
            phone=supplier.phone,
            email=supplier.email,
            active=True,
        )
        self._db.add(row)
        self._db.flush()
        return row.id

    def _payment_composition_notes(self, order: Order | None) -> str:
        if not order:
            return "Criado automaticamente por pagamento confirmado."
        product_revenue = round(float(order.subtotal or 0.0), 2)
        shipping_revenue = round(float(order.delivery_fee_final or order.shipping_fee or 0.0), 2)
        discount = round(float(order.discount or 0.0) + float(order.delivery_fee_discount or 0.0), 2)
        return (
            "Criado automaticamente por pagamento confirmado. "
            f"Composicao: produtos={product_revenue:.2f}; frete={shipping_revenue:.2f}; "
            f"descontos={discount:.2f}; canal={order.sales_channel or 'delivery'}."
        )

    def _add_dimension(self, bucket: dict, label: str, entry_type: str, amount: float) -> None:
        key = (label, entry_type)
        if key not in bucket:
            bucket[key] = {"label": label, "entry_type": entry_type, "amount": 0.0, "count": 0}
        bucket[key]["amount"] = round(float(bucket[key]["amount"]) + float(amount or 0.0), 2)
        bucket[key]["count"] += 1

    def _dimension_rows(self, bucket: dict) -> list[dict]:
        return sorted(bucket.values(), key=lambda item: (item["entry_type"], item["label"]))

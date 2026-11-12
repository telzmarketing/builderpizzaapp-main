from __future__ import annotations

import json
import math
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, DecimalException, ROUND_HALF_UP

from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from backend.core.exceptions import DomainError
from backend.core.tenant_context import TenantContext, TenantContextMissing
from backend.core.wave7_tenant_orm import wave7_orm_enabled
from backend.models.finance import (
    FinanceAccount, FinanceBudget, FinanceBudgetLine, FinanceCategory, FinanceCounterparty, FinanceObligation,
    FinanceBankReconciliationEvent, FinanceBankStatement, FinanceBankStatementLine, FinanceObligationInstallment,
    FinanceSettlement, FinanceTransaction,
)
from backend.models.gestao import GestaoModuleSettings
from backend.models.inventory import InventoryPurchase
from backend.models.inventory_receipts import InventoryReceiptDocument
from backend.models.fiscal import FiscalDocument
from backend.models.cmv import OrderCmvSnapshot
from backend.models.order import Order, OrderStatus
from backend.models.payment import Payment, PaymentStatus
from backend.models.delivery import DeliveryEarning, DeliveryPerson
from backend.schemas.finance import (
    FinanceAccountIn, FinanceBudgetIn, FinanceCategoryIn, FinanceCounterpartyIn,
    FinanceBankMatchIn, FinanceBankReconciliationReasonIn, FinanceBankStatementImportIn, FinanceObligationFromFiscalIn,
    FinanceSettlementIn, FinanceTransactionIn,
)
from backend.services.finance_contracts import (
    FinancialContractViolation,
    PaymentConfirmedFact,
    validate_purchase_payable_source,
)

TENANT_ID = "default"


class FinanceNotFound(DomainError):
    http_status = 404

    def __init__(self, entity: str):
        super().__init__(f"{entity} nao encontrado.", code="FinanceNotFound")


class FinanceInvalidReference(DomainError):
    def __init__(self, message: str):
        super().__init__(message, code="FinanceInvalidReference")


class FinanceService:
    def __init__(
        self,
        db: Session,
        tenant_id: str = TENANT_ID,
        tenant_context: TenantContext | None = None,
    ):
        self._db = db
        self._tenant_context = tenant_context
        self._tenant_id = self._resolve_tenant_id(tenant_id, tenant_context)

    @staticmethod
    def _resolve_tenant_id(tenant_id: str | None, context: TenantContext | None) -> str:
        """Require a server-resolved context once Wave 7 is enabled.

        A raw id from a route, event or provider payload is never sufficient
        proof of ownership.  The legacy default remains only while the Wave 7
        gate is disabled.
        """
        if not wave7_orm_enabled():
            return tenant_id or TENANT_ID
        if context is None:
            raise TenantContextMissing("Contexto confiavel obrigatorio para financeiro da Wave 7.")
        if tenant_id not in {None, TENANT_ID, context.tenant_id}:
            context.assert_tenant(tenant_id)
        return context.tenant_id

    def overview(self) -> dict:
        return {
            "summary": self.summary(),
            "management": self.management_summary(),
            "accounts": self.list_accounts(),
            "categories": self.list_categories(),
            "counterparties": self.list_counterparties(),
            "transactions": self.list_transactions(),
        }

    def payment_overview(self) -> dict:
        rows = (
            self._db.query(
                Payment.method,
                Payment.gateway,
                Payment.provider,
                Payment.status,
                func.count(Payment.id),
                func.coalesce(func.sum(Payment.amount), 0),
            )
            .filter(Payment.tenant_id == self._tenant_id)
            .group_by(Payment.method, Payment.gateway, Payment.provider, Payment.status)
            .order_by(Payment.method, Payment.gateway, Payment.provider, Payment.status)
            .all()
        )
        fee_rows = (
            self._db.query(
                FinanceTransaction.payment_id,
                func.coalesce(func.sum(FinanceTransaction.fee_amount), 0),
            )
            .filter(
                FinanceTransaction.tenant_id == self._tenant_id,
                FinanceTransaction.payment_id.is_not(None),
            )
            .group_by(FinanceTransaction.payment_id)
            .all()
        )
        linked_fees = {payment_id: round(float(amount or 0), 2) for payment_id, amount in fee_rows}
        summaries = []
        for method, gateway, provider, status, count, gross_amount in rows:
            method_value = getattr(method, "value", method)
            status_value = getattr(status, "value", status)
            payment_ids = [
                payment_id for payment_id, in self._db.query(Payment.id)
                .filter(
                    Payment.tenant_id == self._tenant_id,
                    Payment.method == method,
                    Payment.gateway == gateway,
                    Payment.provider == provider,
                    Payment.status == status,
                ).all()
            ]
            summaries.append({
                "method": str(method_value),
                "gateway": gateway or "unknown",
                "provider": provider or "unknown",
                "status": str(status_value),
                "count": int(count or 0),
                "gross_amount": round(float(gross_amount or 0), 2),
                "linked_fee_amount": round(sum(linked_fees.get(payment_id, 0) for payment_id in payment_ids), 2),
            })
        return {
            "summaries": summaries,
            "total_count": sum(item["count"] for item in summaries),
            "total_gross_amount": round(sum(item["gross_amount"] for item in summaries), 2),
            "total_linked_fee_amount": round(sum(item["linked_fee_amount"] for item in summaries), 2),
        }

    def delivery_finance_overview(self) -> dict:
        rows = (
            self._db.query(
                DeliveryEarning.delivery_person_id,
                DeliveryPerson.name,
                DeliveryEarning.status,
                func.count(DeliveryEarning.id),
                func.coalesce(func.sum(DeliveryEarning.amount), 0),
            )
            .join(DeliveryPerson, DeliveryPerson.id == DeliveryEarning.delivery_person_id)
            .filter(DeliveryEarning.tenant_id == self._tenant_id)
            .group_by(DeliveryEarning.delivery_person_id, DeliveryPerson.name, DeliveryEarning.status)
            .order_by(DeliveryPerson.name, DeliveryEarning.status)
            .all()
        )
        summaries = [
            {
                "delivery_person_id": person_id,
                "delivery_person_name": name,
                "status": status,
                "count": int(count or 0),
                "amount": round(float(amount or 0), 2),
            }
            for person_id, name, status, count, amount in rows
        ]
        by_status = {status: round(sum(item["amount"] for item in summaries if item["status"] == status), 2) for status in ("pending", "paid", "cancelled")}
        return {
            "summaries": summaries,
            "total_count": sum(item["count"] for item in summaries),
            "pending_amount": by_status["pending"],
            "paid_amount": by_status["paid"],
            "cancelled_amount": by_status["cancelled"],
        }

    def bi_overview(self, date_from: date | None = None, date_to: date | None = None) -> dict:
        today = date.today()
        start = date_from or today.replace(day=1)
        end = date_to or today
        if start > end:
            raise FinanceInvalidReference("O periodo do BI financeiro e invalido.")
        rows = (
            self._db.query(FinanceTransaction)
            .options(joinedload(FinanceTransaction.category), joinedload(FinanceTransaction.order))
            .filter(
                FinanceTransaction.tenant_id == self._tenant_id,
                FinanceTransaction.status != "cancelled",
                FinanceTransaction.competence_date >= start,
                FinanceTransaction.competence_date <= end,
            )
            .all()
        )
        origin_lines: dict[tuple[str, str], dict] = {}
        category_lines: dict[tuple[str, str], dict] = {}
        cost_center_lines: dict[tuple[str, str], dict] = {}
        channel_lines: dict[tuple[str, str], dict] = {}
        total_income = 0.0
        total_expense = 0.0
        for row in rows:
            amount = round(float(row.amount or 0), 2)
            if row.entry_type == "income":
                total_income += amount
            else:
                total_expense += amount
            self._add_dimension(origin_lines, row.origin_type or "manual", row.entry_type, amount)
            self._add_dimension(category_lines, row.category.name if row.category else "Sem categoria", row.entry_type, amount)
            self._add_dimension(cost_center_lines, row.cost_center or "Sem centro de custo", row.entry_type, amount)
            self._add_dimension(channel_lines, row.order.sales_channel if row.order and row.order.sales_channel else "Sem canal", row.entry_type, amount)
        return {
            "date_from": start,
            "date_to": end,
            "total_income": round(total_income, 2),
            "total_expense": round(total_expense, 2),
            "result": round(total_income - total_expense, 2),
            "transaction_count": len(rows),
            "by_origin": [
                {"origin_type": item["label"], "entry_type": item["entry_type"], "amount": item["amount"], "count": item["count"]}
                for item in self._dimension_rows(origin_lines)
            ],
            "by_category": self._dimension_rows(category_lines),
            "by_cost_center": self._dimension_rows(cost_center_lines),
            "by_channel": self._dimension_rows(channel_lines),
        }

    def cash_flow(self, date_from: date | None = None, date_to: date | None = None) -> dict:
        today = date.today()
        start = date_from or today.replace(day=1)
        end = date_to or today
        if start > end:
            raise FinanceInvalidReference("O período do fluxo de caixa é inválido.")
        accounts = self.list_accounts()
        transactions = self.list_transactions()
        lines = []
        for transaction in transactions:
            movement_date = transaction.get("competence_date")
            if isinstance(movement_date, str):
                movement_date = date.fromisoformat(movement_date)
            if movement_date is None or movement_date < start or movement_date > end:
                continue
            amount = float(transaction.get("amount") or 0)
            realized = self._cash_effect_from_values(transaction)
            if transaction.get("entry_type") == "expense":
                realized = -realized
            projected = amount if transaction.get("status") in {"pending", "partial", "paid"} else 0.0
            if transaction.get("entry_type") == "expense":
                projected = -projected
            lines.append({
                "id": transaction["id"],
                "movement_date": movement_date,
                "description": transaction["description"],
                "entry_type": transaction["entry_type"],
                "status": transaction["status"],
                "account_name": transaction.get("account_name"),
                "category_name": transaction.get("category_name"),
                "projected_amount": round(projected, 2),
                "realized_amount": round(realized, 2),
            })
        opening = round(sum(float(account.get("opening_balance") or 0) for account in accounts), 2)
        realized_income = round(sum(line["realized_amount"] for line in lines if line["entry_type"] == "income"), 2)
        realized_expense = round(-sum(line["realized_amount"] for line in lines if line["entry_type"] == "expense"), 2)
        projected_income = round(sum(line["projected_amount"] for line in lines if line["entry_type"] == "income"), 2)
        projected_expense = round(-sum(line["projected_amount"] for line in lines if line["entry_type"] == "expense"), 2)
        return {
            "date_from": start,
            "date_to": end,
            "opening_balance": opening,
            "realized_income": realized_income,
            "realized_expense": realized_expense,
            "realized_result": round(realized_income - realized_expense, 2),
            "projected_income": projected_income,
            "projected_expense": projected_expense,
            "projected_result": round(projected_income - projected_expense, 2),
            "closing_realized_balance": round(opening + realized_income - realized_expense, 2),
            "closing_projected_balance": round(opening + projected_income - projected_expense, 2),
            "lines": sorted(lines, key=lambda line: (line["movement_date"], line["id"]), reverse=True),
        }

    def forecast(self, months: int = 6) -> dict:
        if months < 1 or months > 12:
            raise FinanceInvalidReference("A previsao deve ter entre 1 e 12 meses.")
        today = date.today()
        start = today.replace(day=1)
        end_month = start.month - 1 + months
        end = date(start.year + end_month // 12, end_month % 12 + 1, 1)
        end = end.replace(day=1) - timedelta(days=1)
        transactions = (
            self._db.query(FinanceTransaction)
            .filter(FinanceTransaction.tenant_id == self._tenant_id, FinanceTransaction.status != "cancelled")
            .all()
        )
        accounts = self._db.query(FinanceAccount).filter(
            FinanceAccount.tenant_id == self._tenant_id, FinanceAccount.active == True  # noqa: E712
        ).all()
        opening = sum(float(account.opening_balance or 0) for account in accounts)
        events: list[tuple[date, str, float]] = []
        for row in transactions:
            if row.status in {"pending", "partial"}:
                movement_date = row.due_date or row.competence_date
                amount = self._open_amount(row)
            else:
                movement_date = row.competence_date
                amount = self._cash_effect(row)
            if movement_date and movement_date < start:
                if row.entry_type == "income":
                    opening += amount
                else:
                    opening -= amount
            elif movement_date and start <= movement_date <= end and amount > 0:
                events.append((movement_date, row.entry_type, round(amount, 2)))
        periods = []
        balance = round(opening, 2)
        for index in range(months):
            month_offset = start.month - 1 + index
            period_start = date(start.year + month_offset // 12, month_offset % 12 + 1, 1)
            next_month = period_start.month
            next_year = period_start.year + (next_month // 12)
            next_month = next_month % 12 + 1
            period_end = date(next_year, next_month, 1) - timedelta(days=1)
            selected = [event for event in events if period_start <= event[0] <= period_end]
            income = round(sum(amount for _, entry_type, amount in selected if entry_type == "income"), 2)
            expense = round(sum(amount for _, entry_type, amount in selected if entry_type == "expense"), 2)
            result = round(income - expense, 2)
            periods.append({
                "period_start": period_start,
                "period_end": period_end,
                "opening_balance": balance,
                "projected_income": income,
                "projected_expense": expense,
                "projected_result": result,
                "closing_balance": round(balance + result, 2),
                "source_count": len(selected),
            })
            balance = round(balance + result, 2)
        return {
            "date_from": start,
            "date_to": end,
            "months": months,
            "methodology": "Pagamentos em aberto usam vencimento; valores liquidados usam competencia. Nenhuma receita ou despesa e inferida.",
            "periods": periods,
        }

    def list_budgets(self) -> list[dict]:
        rows = (
            self._db.query(FinanceBudget)
            .filter(FinanceBudget.tenant_id == self._tenant_id)
            .options(joinedload(FinanceBudget.lines).joinedload(FinanceBudgetLine.category))
            .order_by(FinanceBudget.period_start.desc(), FinanceBudget.created_at.desc())
            .limit(200)
            .all()
        )
        transactions = (
            self._db.query(FinanceTransaction)
            .filter(FinanceTransaction.tenant_id == self._tenant_id, FinanceTransaction.status != "cancelled")
            .all()
        )
        return [self._serialize_budget(row, transactions) for row in rows]

    def create_budget(self, payload: FinanceBudgetIn, admin_id: str | None = None) -> dict:
        if payload.period_start > payload.period_end:
            raise FinanceInvalidReference("O período do orçamento é inválido.")
        lines = []
        for item in payload.lines:
            category = self._get_category(item.category_id) if item.category_id else None
            if category and category.entry_type != item.entry_type:
                raise FinanceInvalidReference("A categoria do orçamento não corresponde ao tipo do valor.")
            lines.append(FinanceBudgetLine(
                id=f"fin-budget-line-{uuid.uuid4().hex[:12]}",
                tenant_id=self._tenant_id,
                category_id=item.category_id,
                cost_center=item.cost_center.strip() if item.cost_center else None,
                entry_type=item.entry_type,
                planned_amount=self._money(item.planned_amount, "valor planejado"),
                notes=item.notes,
            ))
        row = FinanceBudget(
            id=f"fin-budget-{uuid.uuid4().hex[:12]}",
            tenant_id=self._tenant_id,
            name=payload.name.strip(),
            period_start=payload.period_start,
            period_end=payload.period_end,
            status=payload.status,
            notes=payload.notes,
            created_by_admin_id=admin_id,
            lines=lines,
        )
        self._db.add(row)
        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        self._db.refresh(row)
        return self._serialize_budget(row, [])

    def _serialize_budget(self, row: FinanceBudget, transactions: list[FinanceTransaction]) -> dict:
        def actual_for(line: FinanceBudgetLine) -> float:
            total = 0.0
            for transaction in transactions:
                if transaction.competence_date < row.period_start or transaction.competence_date > row.period_end:
                    continue
                if transaction.entry_type != line.entry_type:
                    continue
                if line.category_id and transaction.category_id != line.category_id:
                    continue
                if line.cost_center and (transaction.cost_center or "") != line.cost_center:
                    continue
                total += float(transaction.amount or 0.0)
            return round(total, 2)

        serialized_lines = []
        for line in row.lines:
            actual = actual_for(line)
            planned = float(line.planned_amount or 0.0)
            serialized_lines.append({
                "id": line.id,
                "category_id": line.category_id,
                "category_name": line.category.name if line.category else None,
                "cost_center": line.cost_center,
                "entry_type": line.entry_type,
                "planned_amount": planned,
                "notes": line.notes,
                "actual_amount": actual,
                "variance_amount": round(actual - planned, 2),
            })
        planned_income = sum(line["planned_amount"] for line in serialized_lines if line["entry_type"] == "income")
        planned_expense = sum(line["planned_amount"] for line in serialized_lines if line["entry_type"] == "expense")
        actual_income = sum(line["actual_amount"] for line in serialized_lines if line["entry_type"] == "income")
        actual_expense = sum(line["actual_amount"] for line in serialized_lines if line["entry_type"] == "expense")
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "name": row.name,
            "period_start": row.period_start,
            "period_end": row.period_end,
            "status": row.status,
            "notes": row.notes,
            "planned_income": round(planned_income, 2),
            "planned_expense": round(planned_expense, 2),
            "actual_income": round(actual_income, 2),
            "actual_expense": round(actual_expense, 2),
            "variance_result": round((actual_income - actual_expense) - (planned_income - planned_expense), 2),
            "lines": serialized_lines,
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

    def list_bank_statements(self) -> list[dict]:
        rows = (
            self._db.query(FinanceBankStatement)
            .join(FinanceBankStatement.account)
            .filter(FinanceBankStatement.tenant_id == self._tenant_id)
            .options(joinedload(FinanceBankStatement.account), joinedload(FinanceBankStatement.lines))
            .order_by(FinanceBankStatement.imported_at.desc())
            .limit(300)
            .all()
        )
        return [self._serialize_bank_statement(row) for row in rows]

    def list_bank_statement_lines(self, statement_id: str) -> list[dict]:
        statement = self._get_bank_statement(statement_id)
        return [self._serialize_bank_statement_line(row) for row in statement.lines]

    def list_bank_reconciliation(self, statement_id: str) -> list[dict]:
        statement = self._get_bank_statement(statement_id)
        return [
            {
                **self._serialize_bank_statement_line(line),
                "candidates": [self._serialize_bank_candidate(candidate) for candidate in self._matching_transactions(statement, line)],
            }
            for line in statement.lines
        ]

    def match_bank_statement_line(self, line_id: str, payload: FinanceBankMatchIn, admin_id: str | None = None) -> dict:
        line = (
            self._db.query(FinanceBankStatementLine)
            .filter(FinanceBankStatementLine.tenant_id == self._tenant_id, FinanceBankStatementLine.id == line_id)
            .with_for_update()
            .first()
        )
        if not line:
            raise FinanceNotFound("Linha do extrato")
        transaction = self._get_transaction(payload.transaction_id, for_update=True)
        if transaction.account_id != line.account_id:
            raise FinanceInvalidReference("O lancamento precisa pertencer a mesma conta do extrato.")
        if transaction.status not in {"partial", "paid"}:
            raise FinanceInvalidReference("Somente lancamentos baixados podem ser conciliados.")
        if line.reconciliation_status == "matched" and line.matched_transaction_id == transaction.id:
            return self._serialize_bank_statement_line(line)
        already_matched = (
            self._db.query(FinanceBankStatementLine)
            .filter(
                FinanceBankStatementLine.tenant_id == self._tenant_id,
                FinanceBankStatementLine.matched_transaction_id == transaction.id,
                FinanceBankStatementLine.reconciliation_status == "matched",
                FinanceBankStatementLine.id != line.id,
            )
            .first()
        )
        if already_matched:
            raise FinanceInvalidReference("O lancamento ja esta conciliado com outra linha bancaria.")
        if not self._amount_matches_line(line, transaction):
            raise FinanceInvalidReference("O valor do lancamento nao corresponde ao movimento bancario.")
        line.reconciliation_status = "matched"
        line.matched_transaction_id = transaction.id
        line.matched_at = datetime.now(timezone.utc)
        line.matched_by_admin_id = admin_id
        self._record_reconciliation_event(line, "matched", transaction.id, admin_id, None)
        self._db.commit()
        self._db.refresh(line)
        return self._serialize_bank_statement_line(line)

    def unmatch_bank_statement_line(self, line_id: str, payload: FinanceBankReconciliationReasonIn, admin_id: str | None = None) -> dict:
        line = self._get_bank_statement_line(line_id, for_update=True)
        if line.reconciliation_status != "matched" or not line.matched_transaction_id:
            raise FinanceInvalidReference("A linha nao esta conciliada.")
        previous_transaction_id = line.matched_transaction_id
        line.reconciliation_status = "unmatched"
        line.matched_transaction_id = None
        line.matched_at = None
        line.matched_by_admin_id = None
        self._record_reconciliation_event(line, "unmatched", previous_transaction_id, admin_id, payload.reason)
        self._db.commit()
        self._db.refresh(line)
        return self._serialize_bank_statement_line(line)

    def ignore_bank_statement_line(self, line_id: str, payload: FinanceBankReconciliationReasonIn, admin_id: str | None = None) -> dict:
        line = self._get_bank_statement_line(line_id, for_update=True)
        if line.reconciliation_status == "matched":
            raise FinanceInvalidReference("Desconcilie a linha antes de ignora-la.")
        line.reconciliation_status = "ignored"
        self._record_reconciliation_event(line, "ignored", None, admin_id, payload.reason)
        self._db.commit()
        self._db.refresh(line)
        return self._serialize_bank_statement_line(line)

    def list_reconciliation_events(self, line_id: str) -> list[dict]:
        self._get_bank_statement_line(line_id)
        rows = (
            self._db.query(FinanceBankReconciliationEvent)
            .filter(FinanceBankReconciliationEvent.tenant_id == self._tenant_id, FinanceBankReconciliationEvent.statement_line_id == line_id)
            .order_by(FinanceBankReconciliationEvent.created_at.desc())
            .all()
        )
        return [self._serialize_reconciliation_event(row) for row in rows]

    def import_bank_statement(self, payload: FinanceBankStatementImportIn, admin_id: str | None = None) -> dict:
        account = self._get_account(payload.account_id)
        if payload.period_start and payload.period_end and payload.period_start > payload.period_end:
            raise FinanceInvalidReference("O periodo do extrato e invalido.")

        if payload.file_hash:
            existing = (
                self._db.query(FinanceBankStatement)
                .filter(
                    FinanceBankStatement.tenant_id == self._tenant_id,
                    FinanceBankStatement.account_id == account.id,
                    FinanceBankStatement.file_hash == payload.file_hash,
                )
                .first()
            )
            if existing:
                return self._serialize_bank_statement(existing)

        external_ids = [line.external_id.strip() for line in payload.lines]
        if len(set(external_ids)) != len(external_ids):
            raise FinanceInvalidReference("O extrato possui identificadores de lancamento duplicados.")

        statement = FinanceBankStatement(
            id=f"fin-stm-{uuid.uuid4().hex[:12]}",
            tenant_id=self._tenant_id,
            account_id=account.id,
            source=payload.source.strip(),
            external_reference=payload.external_reference,
            file_hash=payload.file_hash,
            period_start=payload.period_start,
            period_end=payload.period_end,
            opening_balance=payload.opening_balance,
            closing_balance=payload.closing_balance,
            created_by_admin_id=admin_id,
        )
        self._db.add(statement)
        for payload_line, external_id in zip(payload.lines, external_ids):
            statement.lines.append(FinanceBankStatementLine(
                id=f"fin-stl-{uuid.uuid4().hex[:12]}",
                tenant_id=self._tenant_id,
                account_id=account.id,
                external_id=external_id,
                transaction_date=payload_line.transaction_date,
                description=payload_line.description.strip(),
                amount=payload_line.amount,
                balance=payload_line.balance,
            ))
        self._db.commit()
        self._db.refresh(statement)
        return self._serialize_bank_statement(statement)

    def create_account(self, payload: FinanceAccountIn) -> dict:
        opening_balance = self._money(payload.opening_balance, "saldo inicial", allow_negative=True)
        row = FinanceAccount(id=f"fin-acc-{uuid.uuid4().hex[:12]}", tenant_id=self._tenant_id, **payload.model_dump())
        row.opening_balance = float(opening_balance)
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_account(row)

    def update_account(self, account_id: str, payload: FinanceAccountIn) -> dict:
        opening_balance = self._money(payload.opening_balance, "saldo inicial", allow_negative=True)
        row = self._get_account(account_id)
        for key, value in payload.model_dump().items():
            setattr(row, key, value)
        row.opening_balance = float(opening_balance)
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

    def list_obligations(self) -> list[dict]:
        rows = (
            self._db.query(FinanceObligation)
            .options(joinedload(FinanceObligation.installments))
            .filter(FinanceObligation.tenant_id == self._tenant_id)
            .order_by(FinanceObligation.created_at.desc())
            .limit(300)
            .all()
        )
        return [self._serialize_obligation(row) for row in rows]

    def create_obligation_from_fiscal_document(
        self,
        document_id: str,
        payload: FinanceObligationFromFiscalIn,
        idempotency_key: str,
        admin_id: str | None = None,
    ) -> dict:
        """Record a payable source without guessing payment terms.

        Explicit installment rows are mirrored into legacy finance transactions
        so existing reports continue to work.  With no rows, only the source
        obligation is recorded; no synthetic due date or installment is made.
        """
        key = (idempotency_key or "").strip()
        if not key or len(key) > 160:
            raise FinanceInvalidReference("Idempotency-Key obrigatoria para criar obrigacao fiscal.")
        existing = (
            self._db.query(FinanceObligation)
            .options(joinedload(FinanceObligation.installments))
            .filter(FinanceObligation.tenant_id == self._tenant_id, FinanceObligation.idempotency_key == key)
            .first()
        )
        if existing:
            return self._serialize_obligation(existing)
        document = (
            self._db.query(FiscalDocument)
            .filter(FiscalDocument.tenant_id == self._tenant_id, FiscalDocument.id == document_id)
            .first()
        )
        if not document:
            raise FinanceNotFound("Documento fiscal")
        existing_document = (
            self._db.query(FinanceObligation)
            .filter(FinanceObligation.tenant_id == self._tenant_id, FinanceObligation.fiscal_document_id == document_id)
            .first()
        )
        if existing_document:
            raise FinanceInvalidReference("Documento fiscal ja possui obrigacao financeira vinculada.")
        total = self._money(document.total_document)
        if total <= 0:
            raise FinanceInvalidReference("Documento fiscal sem valor total positivo.")
        installments = self._validated_obligation_installments(payload, total)
        snapshot = self._json_snapshot(document.snapshot_json)
        supplier = snapshot.get("supplier") if isinstance(snapshot.get("supplier"), dict) else {}
        row = FinanceObligation(
            id=f"fin-obg-{uuid.uuid4().hex[:12]}", tenant_id=self._tenant_id,
            fiscal_document_id=document.id, idempotency_key=key, status="pending",
            total_amount=total, product_amount=self._money(document.total_products),
            freight_amount=self._money(document.total_shipping), discount_amount=self._money(document.total_discount),
            tax_amount=self._money(snapshot.get("taxes_total")),
            supplier_name=supplier.get("name") or snapshot.get("supplier_name"),
            supplier_document=supplier.get("document") or snapshot.get("supplier_document"),
            notes=payload.notes, created_by_admin_id=admin_id,
        )
        self._db.add(row)
        self._db.flush()
        for item in installments:
            transaction = self._transaction_for_obligation(row, document, item, admin_id)
            self._db.add(transaction)
            self._db.flush()
            self._db.add(FinanceObligationInstallment(
                id=f"fin-obg-itm-{uuid.uuid4().hex[:12]}", tenant_id=self._tenant_id,
                obligation_id=row.id, finance_transaction_id=transaction.id,
                installment_number=item["installment_number"], amount=item["amount"], due_date=item["due_date"],
            ))
        try:
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            existing = self._db.query(FinanceObligation).filter(
                FinanceObligation.tenant_id == self._tenant_id, FinanceObligation.idempotency_key == key,
            ).first()
            if existing:
                return self._serialize_obligation(existing)
            raise
        self._db.refresh(row)
        return self._serialize_obligation(row)

    def reconcile_obligation(self, obligation_id: str) -> dict:
        row = self._get_obligation(obligation_id)
        # An unallocated source obligation has no payment evidence. In
        # particular, all([]) must not infer cancellation (or settlement).
        # Preserve explicitly recorded states and their audit timestamps.
        if not row.installments:
            return self._serialize_obligation(row)
        for item in row.installments:
            tx = item.transaction
            if tx is not None:
                item.paid_amount = self._money(tx.paid_amount)
                item.status = tx.status if tx.status in {"pending", "partial", "paid", "cancelled"} else item.status
        if row.installments and all(item.status == "paid" for item in row.installments):
            row.status = "paid"
        elif any(item.status == "partial" for item in row.installments) or any(item.paid_amount > 0 for item in row.installments):
            row.status = "partial"
        elif all(item.status == "cancelled" for item in row.installments):
            row.status = "cancelled"
        else:
            row.status = "pending"
        self._db.commit()
        self._db.refresh(row)
        return self._serialize_obligation(row)

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
        operational_cmv = self._operational_cmv_summary()
        cmv_count = operational_cmv["snapshot_count"]
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

        dre_status = "complete_with_operational_cmv" if cmv_count and operational_cmv["pending_count"] == 0 else "partial_without_cmv"
        dre_label = "DRE completa com CMV operacional" if dre_status == "complete_with_operational_cmv" else "DRE parcial com CMV pendente"
        return {
            "cash_realized_income": round(cash_income, 2),
            "cash_realized_expense": round(cash_expense, 2),
            "cash_realized_result": round(cash_income - cash_expense, 2),
            "accrual_income": round(accrual_income, 2),
            "accrual_expense": round(accrual_expense, 2),
            "accrual_result": round(accrual_income - accrual_expense, 2),
            "operational_cmv": operational_cmv,
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

    def _operational_cmv_summary(self) -> dict:
        effective_statuses = [
            OrderStatus.paid,
            OrderStatus.pago,
            OrderStatus.preparing,
            OrderStatus.ready_for_pickup,
            OrderStatus.on_the_way,
            OrderStatus.delivered,
        ]
        rows = (
            self._db.query(OrderCmvSnapshot)
            .join(Order, Order.id == OrderCmvSnapshot.order_id)
            .join(Payment, Payment.order_id == Order.id)
            .filter(OrderCmvSnapshot.tenant_id == self._tenant_id)
            .filter(Payment.tenant_id == self._tenant_id, Payment.status.in_([PaymentStatus.approved, PaymentStatus.paid]))
            .filter(Order.status.in_(effective_statuses))
            .all()
        )
        sale_total = round(sum(float(row.sale_total or 0.0) for row in rows), 2)
        cost_total = round(sum(float(row.cost_total or 0.0) for row in rows), 2)
        pending_count = sum(1 for row in rows if row.missing_recipe or row.missing_cost)
        return {
            "snapshot_count": len(rows),
            "pending_count": pending_count,
            "sale_total": sale_total,
            "cost_total": cost_total,
            "cmv_percent": round((cost_total / sale_total) * 100, 2) if sale_total > 0 else None,
            "status": "complete" if rows and pending_count == 0 else "pending" if rows else "not_available",
        }

    def create_transaction(self, payload: FinanceTransactionIn, admin_id: str | None = None) -> dict:
        data = self._transaction_data(payload)
        data["created_by_admin_id"] = admin_id
        data["updated_by_admin_id"] = admin_id
        row = FinanceTransaction(id=f"fin-trx-{uuid.uuid4().hex[:12]}", tenant_id=self._tenant_id, **data)
        try:
            self._add_initial_settlement(row, admin_id)
            self._db.add(row)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        self._db.refresh(row)
        return self._serialize_transaction(row)

    def update_transaction(self, transaction_id: str, payload: FinanceTransactionIn, admin_id: str | None = None) -> dict:
        row = self._get_transaction(transaction_id, for_update=True)
        if row.paid_amount and float(row.paid_amount) > 0:
            raise FinanceInvalidReference("Lancamento com liquidacao nao pode ser alterado; use estorno.")
        if row.settlements:
            raise FinanceInvalidReference("Lancamento com historico de liquidacao nao pode ser alterado.")
        data = self._transaction_data(payload)
        data["updated_by_admin_id"] = admin_id
        try:
            for key, value in data.items():
                setattr(row, key, value)
            self._add_initial_settlement(row, admin_id)
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
        self._db.refresh(row)
        return self._serialize_transaction(row)

    def _add_initial_settlement(self, row: FinanceTransaction, admin_id: str | None) -> None:
        """Persist an initial payment with its title, without an intermediate commit.

        Create/update keep accepting paid and partial payloads. Updates with
        any settlement history are rejected before reaching this helper.
        """
        if row.status not in {"partial", "paid"}:
            return
        row.settlements.append(FinanceSettlement(
            id=f"fin-set-{uuid.uuid4().hex[:12]}",
            tenant_id=self._tenant_id,
            account_id=row.account_id,
            settled_at=row.paid_at,
            principal_amount=row.paid_amount,
            interest_amount=row.interest_amount,
            fine_amount=row.fine_amount,
            discount_amount=row.discount_amount,
            fee_amount=row.fee_amount,
            net_amount=row.net_amount,
            payment_method=row.payment_method,
            payment_reference=row.payment_reference,
            created_by_admin_id=admin_id,
            origin_type="manual",
            origin_id=row.id,
            notes=row.notes,
        ))

    def delete_transaction(self, transaction_id: str) -> None:
        row = self._get_transaction(transaction_id, for_update=True)
        if row.paid_amount and float(row.paid_amount) > 0:
            raise FinanceInvalidReference("Lancamento com liquidacao nao pode ser cancelado; use estorno.")
        if any(settlement.cancelled_at is None for settlement in row.settlements):
            raise FinanceInvalidReference("Lancamento com historico de liquidacao nao pode ser cancelado.")
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

        payment, order = self._payment_and_order(payment_id=payment_id, order_id=order_id)
        if not payment or not order:
            return {"created": False, "reason": "payment_or_order_not_found"}
        try:
            fact = PaymentConfirmedFact.build(
                tenant_id=self._tenant_id,
                payment_id=payment_id,
                order_id=order_id,
                gateway=gateway,
                persisted_gateway=payment.gateway,
                payment_amount=payment.amount,
                event_amount=amount,
                transaction_id=transaction_id,
            )
        except FinancialContractViolation:
            return {"created": False, "reason": "financial_contract_violation"}

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
        paid_at = payment.paid_at if payment and payment.paid_at else datetime.now(timezone.utc)
        receivable_amount = float(fact.amount)

        account_id = settings.get("default_receivable_account_id") or None
        if account_id:
            self._get_account(str(account_id))

        if existing:
            row = existing
        else:
            order_label = order.order_code or order.id
            row = FinanceTransaction(
                id=f"fin-trx-{uuid.uuid4().hex[:12]}",
                tenant_id=self._tenant_id,
                account_id=account_id,
                category_id=self._ensure_category("Receita de pedidos", "income", "gross_revenue"),
                cost_center=order.sales_channel or "delivery",
                entry_type="income",
                status="paid",
                description=f"Recebimento do pedido {order_label}",
                amount=receivable_amount,
                paid_amount=0.0,
                competence_date=paid_at.date(),
                due_date=paid_at.date(),
                paid_at=paid_at,
                payment_method=(payment.method.value if hasattr(payment.method, "value") else str(payment.method)),
                payment_reference=transaction_id or payment.transaction_id,
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
            .with_for_update()
            .first()
        )
        if not purchase or purchase.status != "confirmed":
            return {"created": False, "reason": "purchase_not_confirmed"}
        receipt = (
            self._db.query(InventoryReceiptDocument)
            .filter(
                InventoryReceiptDocument.tenant_id == self._tenant_id,
                InventoryReceiptDocument.purchase_id == purchase.id,
                InventoryReceiptDocument.status != "rejected",
            )
            .order_by(InventoryReceiptDocument.created_at.desc())
            .first()
        )
        if receipt:
            linked_obligation = (
                self._db.query(FinanceObligation)
                .filter(
                    FinanceObligation.tenant_id == self._tenant_id,
                    FinanceObligation.receipt_document_id == receipt.id,
                )
                .first()
            )
            try:
                validate_purchase_payable_source(
                    purchase_id=purchase.id,
                    receipt_id=receipt.id,
                    receipt_status=receipt.status,
                    linked_obligation_id=linked_obligation.id if linked_obligation else None,
                )
            except FinancialContractViolation:
                return {
                    "created": False,
                    "reason": "purchase_receipt_requires_reconciliation",
                    "receipt_document_id": receipt.id,
                    "obligation_id": linked_obligation.id if linked_obligation else None,
                }
        amount = float(self._money(purchase.total_amount, "total da compra"))
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
            description=f"Compra de estoque {purchase.title or purchase.invoice_number or purchase.id}",
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
        row = self._get_transaction(transaction_id, for_update=True)
        if row.status == "cancelled":
            raise FinanceInvalidReference("Lancamento cancelado nao pode ser baixado.")
        if row.status == "paid":
            raise FinanceInvalidReference("Lancamento ja liquidado nao pode ser baixado novamente.")
        if payload.account_id:
            self._get_account(payload.account_id)

        raw_amounts = {
            "juros": payload.interest_amount,
            "multa": payload.fine_amount,
            "desconto": payload.discount_amount,
            "taxa": payload.fee_amount,
            "baixa": payload.paid_amount,
        }
        for label, value in raw_amounts.items():
            if value is not None and not math.isfinite(float(value)):
                raise FinanceInvalidReference(f"Valor de {label} invalido.")
        interest_amount = round(float(payload.interest_amount or 0.0), 2)
        fine_amount = round(float(payload.fine_amount or 0.0), 2)
        discount_amount = round(float(payload.discount_amount or 0.0), 2)
        fee_amount = round(float(payload.fee_amount or 0.0), 2)
        adjusted_total = self._adjusted_total(row, extra_interest=interest_amount, extra_fine=fine_amount, extra_discount=discount_amount)
        if not math.isfinite(adjusted_total) or adjusted_total <= 0:
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

        try:
            self._db.commit()
        except Exception:
            self._db.rollback()
            raise
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
        self._validate_transaction_ownership(data)
        if int(data.get("installment_number") or 1) > int(data.get("installment_total") or 1):
            raise FinanceInvalidReference("A parcela atual nao pode ser maior que o total de parcelas.")
        if data["status"] == "paid" and not data.get("paid_at"):
            data["paid_at"] = datetime.now(timezone.utc)
        money_fields = ("amount", "interest_amount", "fine_amount", "discount_amount", "fee_amount", "paid_amount", "net_amount")
        for key in money_fields:
            data[key] = self._money(data.get(key), key)
        if data["amount"] <= 0:
            raise FinanceInvalidReference("O valor do lancamento precisa ser maior que zero.")
        adjusted_total = data["amount"] + data["interest_amount"] + data["fine_amount"] - data["discount_amount"]
        if not adjusted_total.is_finite() or adjusted_total <= 0:
            raise FinanceInvalidReference("O total ajustado precisa ser finito e maior que zero.")
        if data["status"] == "paid" and not data.get("paid_amount"):
            # Keep the published paid-with-zero/default shorthand, but do not
            # turn a positive sub-cent payment into a full payment by rounding.
            if payload.paid_amount > 0:
                raise FinanceInvalidReference("O valor pago precisa ser maior que zero apos arredondamento.")
            data["paid_amount"] = adjusted_total
        if data["status"] == "paid" and data["paid_amount"] != adjusted_total:
            raise FinanceInvalidReference("O valor pago precisa corresponder ao total ajustado para quitar o lancamento.")
        if data["status"] == "partial":
            if data["paid_amount"] <= 0 or data["paid_amount"] >= adjusted_total:
                raise FinanceInvalidReference("Lancamento parcial precisa ter valor baixado menor que o total ajustado.")
            data["paid_at"] = data.get("paid_at") or datetime.now(timezone.utc)
        if data["status"] in {"partial", "paid"}:
            net_amount = (
                max(Decimal("0.00"), data["paid_amount"] - data["fee_amount"])
                if data["entry_type"] == "income" else data["paid_amount"] + data["fee_amount"]
            )
            if data["net_amount"] and data["net_amount"] != net_amount:
                raise FinanceInvalidReference("O valor liquido precisa corresponder ao valor pago e a taxa.")
            data["net_amount"] = net_amount
        if data["status"] == "pending":
            data["paid_at"] = None
            data["paid_amount"] = 0.0
            data["net_amount"] = 0.0
        # Published DTOs and legacy Float columns remain unchanged. Monetary
        # validation and arithmetic above use Decimal with HALF_UP cents.
        for key in money_fields:
            data[key] = float(data[key])
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

    def _payment_and_order(self, *, payment_id: str, order_id: str) -> tuple[Payment | None, Order | None]:
        payment = (
            self._db.query(Payment)
            .filter(Payment.tenant_id == self._tenant_id, Payment.id == payment_id)
            .first()
        )
        order = (
            self._db.query(Order)
            .filter(Order.tenant_id == self._tenant_id, Order.id == order_id)
            .first()
        )
        if payment and order and payment.order_id != order.id:
            return None, None
        return payment, order

    def _validate_transaction_ownership(self, data: dict) -> None:
        """Reject cross-company links before an ORM relationship can persist them."""
        if not wave7_orm_enabled():
            return
        if data.get("order_id"):
            order = self._db.query(Order).filter(
                Order.tenant_id == self._tenant_id, Order.id == data["order_id"]
            ).first()
            if not order:
                raise FinanceInvalidReference("Pedido nao pertence a empresa atual.")
        if data.get("payment_id"):
            payment = self._db.query(Payment).filter(
                Payment.tenant_id == self._tenant_id, Payment.id == data["payment_id"]
            ).first()
            if not payment:
                raise FinanceInvalidReference("Pagamento nao pertence a empresa atual.")
            if data.get("order_id") and payment.order_id != data["order_id"]:
                raise FinanceInvalidReference("Pagamento nao pertence ao pedido informado.")
        if data.get("inventory_purchase_id"):
            purchase = self._db.query(InventoryPurchase).filter(
                InventoryPurchase.tenant_id == self._tenant_id,
                InventoryPurchase.id == data["inventory_purchase_id"],
            ).first()
            if not purchase:
                raise FinanceInvalidReference("Compra de estoque nao pertence a empresa atual.")

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

    @staticmethod
    def _money(value, field: str = "valor", *, allow_negative: bool = False) -> Decimal:
        if value is None:
            return Decimal("0.00")
        try:
            amount = Decimal(str(value))
        except (DecimalException, TypeError, ValueError):
            raise FinanceInvalidReference(f"{field} invalido.") from None
        if not amount.is_finite() or (not allow_negative and amount < 0):
            raise FinanceInvalidReference(f"{field} invalido.")
        try:
            return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except DecimalException:
            raise FinanceInvalidReference(f"{field} invalido.") from None

    @staticmethod
    def _json_snapshot(value) -> dict:
        if not value:
            return {}
        try:
            parsed = json.loads(value) if isinstance(value, str) else value
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, json.JSONDecodeError):
            return {}

    def _validated_obligation_installments(self, payload: FinanceObligationFromFiscalIn, total: Decimal) -> list[dict]:
        rows = sorted(payload.installments, key=lambda item: item.installment_number)
        if not rows:
            return []
        expected = list(range(1, len(rows) + 1))
        if [item.installment_number for item in rows] != expected:
            raise FinanceInvalidReference("Parcelas devem ser numeradas sequencialmente a partir de 1.")
        amounts = [self._money(item.amount) for item in rows]
        if sum(amounts, Decimal("0.00")) != total:
            raise FinanceInvalidReference("A soma das parcelas precisa corresponder ao total do documento fiscal.")
        return [{"installment_number": item.installment_number, "amount": amount, "due_date": item.due_date} for item, amount in zip(rows, amounts)]

    def _transaction_for_obligation(self, obligation: FinanceObligation, document: FiscalDocument, item: dict, admin_id: str | None) -> FinanceTransaction:
        due_date = item["due_date"]
        return FinanceTransaction(
            id=f"fin-trx-{uuid.uuid4().hex[:12]}", tenant_id=self._tenant_id,
            category_id=self._ensure_category("Compras de estoque", "expense", "inventory_purchases"),
            counterparty_type="supplier", counterparty_name=obligation.supplier_name or "Fornecedor nao informado",
            counterparty_document=obligation.supplier_document, entry_type="expense", status="pending",
            description=f"Obrigacao fiscal {document.access_key or document.id}",
            amount=float(item["amount"]), competence_date=due_date or date.today(), due_date=due_date,
            document_number=document.number and str(document.number), document_date=document.issue_date.date() if document.issue_date else None,
            obligation_id=obligation.id, origin_type="fiscal_document_payable", origin_id=document.id,
            created_by_admin_id=admin_id, notes="Gerado por obrigacao fiscal explicita; termos ausentes permanecem sem vencimento.",
        )

    def _get_obligation(self, obligation_id: str) -> FinanceObligation:
        row = (
            self._db.query(FinanceObligation)
            .options(joinedload(FinanceObligation.installments).joinedload(FinanceObligationInstallment.transaction))
            .filter(FinanceObligation.tenant_id == self._tenant_id, FinanceObligation.id == obligation_id)
            .first()
        )
        if not row:
            raise FinanceNotFound("Obrigacao financeira")
        return row

    def _serialize_obligation(self, row: FinanceObligation) -> dict:
        return {
            "id": row.id, "tenant_id": row.tenant_id, "fiscal_document_id": row.fiscal_document_id,
            "idempotency_key": row.idempotency_key, "status": row.status, "currency": row.currency,
            "total_amount": self._money(row.total_amount), "product_amount": self._money(row.product_amount),
            "freight_amount": self._money(row.freight_amount), "discount_amount": self._money(row.discount_amount),
            "tax_amount": self._money(row.tax_amount), "supplier_name": row.supplier_name,
            "supplier_document": row.supplier_document, "notes": row.notes,
            "created_by_admin_id": row.created_by_admin_id, "created_at": row.created_at, "updated_at": row.updated_at,
            "installments": [{
                "id": item.id, "tenant_id": item.tenant_id, "obligation_id": item.obligation_id,
                "finance_transaction_id": item.finance_transaction_id, "installment_number": item.installment_number,
                "amount": self._money(item.amount), "due_date": item.due_date, "status": item.status,
                "paid_amount": self._money(item.paid_amount), "created_at": item.created_at,
            } for item in row.installments],
        }

    def _get_bank_statement(self, statement_id: str) -> FinanceBankStatement:
        row = (
            self._db.query(FinanceBankStatement)
            .options(joinedload(FinanceBankStatement.account), joinedload(FinanceBankStatement.lines))
            .filter(FinanceBankStatement.tenant_id == self._tenant_id, FinanceBankStatement.id == statement_id)
            .first()
        )
        if not row:
            raise FinanceNotFound("Extrato bancario")
        return row

    def _get_bank_statement_line(self, line_id: str, *, for_update: bool = False) -> FinanceBankStatementLine:
        query = self._db.query(FinanceBankStatementLine).filter(
            FinanceBankStatementLine.tenant_id == self._tenant_id,
            FinanceBankStatementLine.id == line_id,
        )
        if for_update:
            query = query.with_for_update()
        row = query.first()
        if not row:
            raise FinanceNotFound("Linha do extrato")
        return row

    def _record_reconciliation_event(self, line: FinanceBankStatementLine, action: str, transaction_id: str | None, admin_id: str | None, reason: str | None) -> None:
        self._db.add(FinanceBankReconciliationEvent(
            id=f"fin-rec-{uuid.uuid4().hex[:12]}",
            tenant_id=self._tenant_id,
            statement_line_id=line.id,
            action=action,
            transaction_id=transaction_id,
            admin_id=admin_id,
            reason=reason,
        ))

    @staticmethod
    def _serialize_reconciliation_event(row: FinanceBankReconciliationEvent) -> dict:
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "statement_line_id": row.statement_line_id,
            "action": row.action,
            "transaction_id": row.transaction_id,
            "admin_id": row.admin_id,
            "reason": row.reason,
            "created_at": row.created_at,
        }

    @staticmethod
    def _serialize_bank_statement_line(row: FinanceBankStatementLine) -> dict:
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "statement_id": row.statement_id,
            "external_id": row.external_id,
            "transaction_date": row.transaction_date,
            "description": row.description,
            "amount": row.amount,
            "balance": row.balance,
            "reconciliation_status": row.reconciliation_status,
            "matched_transaction_id": row.matched_transaction_id,
            "matched_at": row.matched_at,
        }

    def _serialize_bank_statement(self, row: FinanceBankStatement) -> dict:
        lines = list(row.lines or [])
        return {
            "id": row.id,
            "tenant_id": row.tenant_id,
            "account_id": row.account_id,
            "account_name": row.account.name if row.account else "",
            "source": row.source,
            "external_reference": row.external_reference,
            "file_hash": row.file_hash,
            "period_start": row.period_start,
            "period_end": row.period_end,
            "opening_balance": row.opening_balance,
            "closing_balance": row.closing_balance,
            "status": row.status,
            "imported_at": row.imported_at,
            "line_count": len(lines),
            "unmatched_count": sum(1 for line in lines if line.reconciliation_status != "matched"),
            "created_at": row.created_at,
        }

    def _matching_transactions(self, statement: FinanceBankStatement, line: FinanceBankStatementLine) -> list[FinanceTransaction]:
        target_date = line.transaction_date
        candidates = (
            self._db.query(FinanceTransaction)
            .filter(
                FinanceTransaction.tenant_id == self._tenant_id,
                FinanceTransaction.account_id == statement.account_id,
                FinanceTransaction.status.in_(["partial", "paid"]),
                FinanceTransaction.competence_date.between(target_date - timedelta(days=3), target_date + timedelta(days=3)),
            )
            .order_by(FinanceTransaction.competence_date, FinanceTransaction.created_at)
            .limit(25)
            .all()
        )
        return [candidate for candidate in candidates if self._amount_matches_line(line, candidate)]

    @staticmethod
    def _amount_matches_line(line: FinanceBankStatementLine, transaction: FinanceTransaction) -> bool:
        line_amount = Decimal(str(line.amount or 0)).quantize(Decimal("0.01"))
        settled_amount = Decimal(str(transaction.net_amount or transaction.paid_amount or transaction.amount or 0)).quantize(Decimal("0.01"))
        expected = settled_amount if transaction.entry_type == "income" else -settled_amount
        return line_amount == expected

    @staticmethod
    def _serialize_bank_candidate(row: FinanceTransaction) -> dict:
        return {
            "id": row.id,
            "description": row.description,
            "competence_date": row.competence_date,
            "amount": float(row.amount or 0),
            "entry_type": row.entry_type,
            "status": row.status,
        }

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

    def _get_transaction(self, transaction_id: str, *, for_update: bool = False) -> FinanceTransaction:
        query = (
            self._db.query(FinanceTransaction)
            .filter(FinanceTransaction.tenant_id == self._tenant_id, FinanceTransaction.id == transaction_id)
        )
        if for_update:
            query = query.with_for_update()
        row = query.first()
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
        result = round(
            float(row.amount or 0.0)
            + float(row.interest_amount or 0.0)
            + float(extra_interest or 0.0)
            + float(row.fine_amount or 0.0)
            + float(extra_fine or 0.0)
            - float(row.discount_amount or 0.0)
            - float(extra_discount or 0.0),
            2,
        )
        if not math.isfinite(result):
            raise FinanceInvalidReference("Total financeiro invalido.")
        return result

    def _adjusted_total_from_data(self, data: dict) -> float:
        result = round(
            float(data.get("amount") or 0.0)
            + float(data.get("interest_amount") or 0.0)
            + float(data.get("fine_amount") or 0.0)
            - float(data.get("discount_amount") or 0.0),
            2,
        )
        if not math.isfinite(result):
            raise FinanceInvalidReference("Total financeiro invalido.")
        return result

    def _net_amount(self, entry_type: str, paid_amount: float, fee_amount: float) -> float:
        fee = float(fee_amount or 0.0)
        paid = float(paid_amount or 0.0)
        result = round(max(0.0, paid - fee) if entry_type == "income" else paid + fee, 2)
        if not math.isfinite(result):
            raise FinanceInvalidReference("Valor liquido invalido.")
        return result

    def _cash_effect(self, row: FinanceTransaction) -> float:
        value = float(row.net_amount or 0.0)
        if value > 0:
            return value
        if row.status in {"partial", "paid"}:
            return self._net_amount(row.entry_type, float(row.paid_amount or 0.0), float(row.fee_amount or 0.0))
        return 0.0

    def _cash_effect_from_values(self, transaction: dict) -> float:
        value = float(transaction.get("net_amount") or 0.0)
        if value > 0:
            return value
        if transaction.get("status") in {"partial", "paid"}:
            return self._net_amount(
                str(transaction.get("entry_type") or "expense"),
                float(transaction.get("paid_amount") or 0.0),
                float(transaction.get("fee_amount") or 0.0),
            )
        return 0.0

    def _open_amount(self, row: FinanceTransaction) -> float:
        return float(max(Decimal("0.00"), self._money(self._adjusted_total(row)) - self._money(row.paid_amount)))

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

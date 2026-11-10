"""Read-only financial baseline audit.

This command reports integrity violations; it never repairs data or applies
migrations. Use it only with a read-only database credential when a real
PostgreSQL environment is available.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NONFINITE_SQL = "CAST({field} AS text) IN ('NaN', 'Infinity', '-Infinity')"


FINANCE_TABLES: tuple[str, ...] = (
    "finance_accounts",
    "finance_categories",
    "finance_counterparties",
    "finance_transactions",
    "finance_settlements",
    "finance_obligations",
    "finance_obligation_installments",
)


CHECKS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    *tuple(
        (
            f"{table}_missing_tenant",
            f"""
            SELECT id, tenant_id
            FROM {table}
            WHERE tenant_id IS NULL
            LIMIT 101
            """,
            (table,),
        )
        for table in FINANCE_TABLES
    ),
    (
        "finance_transactions_duplicate_origin",
        """
        SELECT tenant_id, origin_type, origin_id, installment_number,
               COUNT(*) AS duplicate_count
        FROM finance_transactions
        WHERE origin_id IS NOT NULL
        GROUP BY tenant_id, origin_type, origin_id, installment_number
        HAVING COUNT(*) > 1
        LIMIT 101
        """,
        ("finance_transactions",),
    ),
    (
        "finance_transactions_invalid_status",
        """
        SELECT id, tenant_id, status
        FROM finance_transactions
        WHERE status IS NULL
           OR status NOT IN ('pending', 'partial', 'paid', 'cancelled')
        LIMIT 101
        """,
        ("finance_transactions",),
    ),
    (
        "finance_transactions_invalid_amounts",
        f"""
        SELECT id, tenant_id, amount, paid_amount, interest_amount,
               fine_amount, discount_amount, fee_amount, net_amount
        FROM finance_transactions
        WHERE amount IS NULL OR amount <= 0
           OR paid_amount IS NULL OR paid_amount < 0
           OR interest_amount IS NULL OR interest_amount < 0
           OR fine_amount IS NULL OR fine_amount < 0
           OR discount_amount IS NULL OR discount_amount < 0
           OR fee_amount IS NULL OR fee_amount < 0
           OR net_amount IS NULL OR net_amount < 0
           OR (status IN ('partial', 'paid') AND paid_amount = 0)
           OR (status IN ('partial', 'paid') AND net_amount = 0)
           OR {_NONFINITE_SQL.format(field='amount')}
           OR {_NONFINITE_SQL.format(field='paid_amount')}
           OR {_NONFINITE_SQL.format(field='interest_amount')}
           OR {_NONFINITE_SQL.format(field='fine_amount')}
           OR {_NONFINITE_SQL.format(field='discount_amount')}
           OR {_NONFINITE_SQL.format(field='fee_amount')}
           OR {_NONFINITE_SQL.format(field='net_amount')}
        LIMIT 101
        """,
        ("finance_transactions",),
    ),
    (
        "finance_settlements_missing_for_paid_transaction",
        """
        SELECT ft.id, ft.tenant_id, ft.status, ft.paid_amount
        FROM finance_transactions ft
        WHERE (ft.status IN ('partial', 'paid') OR ft.paid_amount > 0)
          AND NOT EXISTS (
              SELECT 1
              FROM finance_settlements fs
              WHERE fs.transaction_id = ft.id
                AND fs.tenant_id = ft.tenant_id
                AND fs.cancelled_at IS NULL
          )
        LIMIT 101
        """,
        ("finance_transactions", "finance_settlements"),
    ),
    (
        "finance_settlements_orphan",
        """
        SELECT fs.id, fs.tenant_id, fs.transaction_id,
               ft.id AS transaction_found, ft.tenant_id AS transaction_tenant_id
        FROM finance_settlements fs
        LEFT JOIN finance_transactions ft
          ON ft.id = fs.transaction_id
         AND ft.tenant_id = fs.tenant_id
        WHERE fs.tenant_id IS NULL
           OR fs.transaction_id IS NULL
           OR ft.id IS NULL
        LIMIT 101
        """,
        ("finance_settlements", "finance_transactions"),
    ),
    (
        "finance_settlement_mismatch",
        """
        WITH active AS (
            SELECT tenant_id, transaction_id,
                   COALESCE(SUM(principal_amount), 0) AS principal_sum,
                   COALESCE(SUM(net_amount), 0) AS net_sum
            FROM finance_settlements
            WHERE cancelled_at IS NULL
            GROUP BY tenant_id, transaction_id
        )
        SELECT ft.id, ft.tenant_id, ft.paid_amount, active.principal_sum,
               ft.net_amount, active.net_sum
        FROM finance_transactions ft
        LEFT JOIN active
          ON active.tenant_id = ft.tenant_id
         AND active.transaction_id = ft.id
        WHERE ROUND(CAST(COALESCE(ft.paid_amount, 0) AS numeric) * 100)
                  IS DISTINCT FROM
              ROUND(CAST(COALESCE(active.principal_sum, 0) AS numeric) * 100)
           OR ROUND(CAST(COALESCE(ft.net_amount, 0) AS numeric) * 100)
                  IS DISTINCT FROM
              ROUND(CAST(COALESCE(active.net_sum, 0) AS numeric) * 100)
        LIMIT 101
        """,
        ("finance_transactions", "finance_settlements"),
    ),
    (
        "finance_settlements_invalid_amounts",
        f"""
        SELECT id, tenant_id, transaction_id, principal_amount,
               interest_amount, fine_amount, discount_amount,
               fee_amount, net_amount
        FROM finance_settlements
        WHERE tenant_id IS NULL OR transaction_id IS NULL
           OR principal_amount IS NULL OR principal_amount <= 0
           OR interest_amount IS NULL OR interest_amount < 0
           OR fine_amount IS NULL OR fine_amount < 0
           OR discount_amount IS NULL OR discount_amount < 0
           OR fee_amount IS NULL OR fee_amount < 0
           OR net_amount IS NULL OR net_amount < 0
           OR {_NONFINITE_SQL.format(field='principal_amount')}
           OR {_NONFINITE_SQL.format(field='interest_amount')}
           OR {_NONFINITE_SQL.format(field='fine_amount')}
           OR {_NONFINITE_SQL.format(field='discount_amount')}
           OR {_NONFINITE_SQL.format(field='fee_amount')}
           OR {_NONFINITE_SQL.format(field='net_amount')}
        LIMIT 101
        """,
        ("finance_settlements",),
    ),
    (
        "finance_obligations_invalid_source",
        """
        SELECT id, tenant_id, fiscal_document_id, receipt_document_id
        FROM finance_obligations
        WHERE (fiscal_document_id IS NULL AND receipt_document_id IS NULL)
           OR (fiscal_document_id IS NOT NULL AND receipt_document_id IS NOT NULL)
        LIMIT 101
        """,
        ("finance_obligations",),
    ),
    (
        "finance_obligations_duplicate_origin",
        """
        SELECT tenant_id, origin_kind, origin_id, COUNT(*) AS duplicate_count
        FROM (
            SELECT tenant_id, 'fiscal_document' AS origin_kind,
                   fiscal_document_id AS origin_id
            FROM finance_obligations
            WHERE fiscal_document_id IS NOT NULL
            UNION ALL
            SELECT tenant_id, 'receipt_document' AS origin_kind,
                   receipt_document_id AS origin_id
            FROM finance_obligations
            WHERE receipt_document_id IS NOT NULL
            UNION ALL
            SELECT tenant_id, 'idempotency_key' AS origin_kind,
                   idempotency_key AS origin_id
            FROM finance_obligations
            WHERE idempotency_key IS NOT NULL
        ) origins
        GROUP BY tenant_id, origin_kind, origin_id
        HAVING COUNT(*) > 1
        LIMIT 101
        """,
        ("finance_obligations",),
    ),
    (
        "finance_obligations_invalid_status",
        """
        SELECT id, tenant_id, status
        FROM finance_obligations
        WHERE status IS NULL
           OR status NOT IN ('pending', 'partial', 'paid', 'cancelled')
        LIMIT 101
        """,
        ("finance_obligations",),
    ),
    (
        "finance_obligations_invalid_amounts",
        f"""
        SELECT id, tenant_id, total_amount, product_amount,
               freight_amount, discount_amount, tax_amount
        FROM finance_obligations
        WHERE total_amount IS NULL OR total_amount <= 0
           OR product_amount IS NULL OR product_amount < 0
           OR freight_amount IS NULL OR freight_amount < 0
           OR discount_amount IS NULL OR discount_amount < 0
           OR tax_amount IS NULL OR tax_amount < 0
           OR {_NONFINITE_SQL.format(field='total_amount')}
           OR {_NONFINITE_SQL.format(field='product_amount')}
           OR {_NONFINITE_SQL.format(field='freight_amount')}
           OR {_NONFINITE_SQL.format(field='discount_amount')}
           OR {_NONFINITE_SQL.format(field='tax_amount')}
        LIMIT 101
        """,
        ("finance_obligations",),
    ),
    (
        "finance_obligation_installments_orphan",
        """
        SELECT foi.id, foi.tenant_id, foi.obligation_id,
               fo.id AS obligation_found, fo.tenant_id AS obligation_tenant_id
        FROM finance_obligation_installments foi
        LEFT JOIN finance_obligations fo
          ON fo.id = foi.obligation_id
         AND fo.tenant_id = foi.tenant_id
        WHERE foi.tenant_id IS NULL
           OR foi.obligation_id IS NULL
           OR fo.id IS NULL
        LIMIT 101
        """,
        ("finance_obligation_installments", "finance_obligations"),
    ),
    (
        "finance_obligation_installments_invalid_status",
        """
        SELECT id, tenant_id, obligation_id, status
        FROM finance_obligation_installments
        WHERE status IS NULL
           OR status NOT IN ('pending', 'partial', 'paid', 'cancelled')
        LIMIT 101
        """,
        ("finance_obligation_installments",),
    ),
    (
        "finance_obligation_installments_invalid_amounts",
        f"""
        SELECT id, tenant_id, obligation_id, installment_number,
               amount, paid_amount
        FROM finance_obligation_installments
        WHERE installment_number IS NULL OR installment_number <= 0
           OR amount IS NULL OR amount <= 0
           OR paid_amount IS NULL OR paid_amount < 0
           OR paid_amount > amount
           OR {_NONFINITE_SQL.format(field='amount')}
           OR {_NONFINITE_SQL.format(field='paid_amount')}
        LIMIT 101
        """,
        ("finance_obligation_installments",),
    ),
    (
        "receipt_purchase_multiple_active_documents",
        """
        SELECT tenant_id, purchase_id, COUNT(*) AS document_count
        FROM inventory_receipt_documents
        WHERE purchase_id IS NOT NULL
          AND (status IS NULL OR status <> 'rejected')
        GROUP BY tenant_id, purchase_id
        HAVING COUNT(*) > 1
        LIMIT 101
        """,
        ("inventory_receipt_documents",),
    ),
    (
        "payment_multiple_financial_projections",
        """
        SELECT payment_id, tenant_id, COUNT(*) AS transaction_count
        FROM finance_transactions
        WHERE payment_id IS NOT NULL
          AND (status IS NULL OR status <> 'cancelled')
        GROUP BY payment_id, tenant_id
        HAVING COUNT(*) > 1
        LIMIT 101
        """,
        ("finance_transactions",),
    ),
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="PostgreSQL DSN; defaults to DATABASE_URL.",
    )
    parser.add_argument(
        "--schema",
        default="public",
        help="PostgreSQL schema used explicitly as the search_path (default: public).",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _validated_schema(schema: str) -> str:
    if not schema or not _IDENTIFIER_RE.fullmatch(schema):
        raise ValueError("Informe um schema PostgreSQL valido.")
    return schema


def _table_names(connection, schema: str) -> set[str]:
    rows = connection.execute(
        text(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = :schema
            """
        ),
        {"schema": schema},
    )
    return {row[0] for row in rows}


def _overall_status(results: list[dict]) -> str:
    if not results or any(item["status"] == "BLOCKED" for item in results):
        return "BLOCKED"
    if any(item["status"] == "FAIL" for item in results):
        return "FAIL"
    return "PASS"


def run(database_url: str, schema: str = "public") -> dict:
    if not database_url or not database_url.startswith(("postgresql://", "postgresql+")):
        raise ValueError("Informe DATABASE_URL apontando para PostgreSQL.")
    schema = _validated_schema(schema)

    engine = create_engine(database_url, pool_pre_ping=True)
    results: list[dict] = []
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '30s'"))
            connection.execute(text("SET LOCAL lock_timeout = '2s'"))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            if str(connection.execute(text("SHOW transaction_read_only")).scalar()).lower() != "on":
                raise RuntimeError("A auditoria nao conseguiu confirmar transaction_read_only=on.")

            tables = _table_names(connection, schema)
            for name, query, required_tables in CHECKS:
                missing = sorted(set(required_tables) - tables)
                if missing:
                    results.append({"name": name, "status": "BLOCKED", "missing_tables": missing})
                    continue
                rows = connection.execute(text(query)).mappings().fetchmany(101)
                truncated = len(rows) > 100
                results.append({
                    "name": name,
                    "status": "PASS" if not rows else "FAIL",
                    "count": min(len(rows), 100),
                    "truncated": truncated,
                    "sample": [dict(row) for row in rows[:10]],
                })
            connection.rollback()
    finally:
        engine.dispose()

    return {
        "audit": "finance-baseline",
        "status": _overall_status(results),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "schema": schema,
        "checks": results,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run(args.database_url, args.schema)
    except (SQLAlchemyError, RuntimeError, ValueError) as exc:
        payload = {"audit": "finance-baseline", "status": "BLOCKED", "error": str(exc)}
        print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        return 2
    output = json.dumps(report, ensure_ascii=False, default=str) if args.as_json else json.dumps(report, ensure_ascii=False, indent=2, default=str)
    print(output)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

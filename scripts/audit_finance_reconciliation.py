"""Read-only reconciliation audit between operational and financial records.

The command reports evidence only. It never mutates the database, applies
schema changes, or infers a business correction for any finding.
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

REQUIRED_TABLES = (
    "orders",
    "payments",
    "finance_transactions",
    "inventory_purchases",
    "finance_obligations",
)


CHECKS = (
    {
        "name": "approved_payment_on_cancelled_order",
        "classification": "pending_decision",
        "tables": ("orders", "payments"),
        "query": """
            SELECT p.id AS payment_id, p.tenant_id, p.order_id,
                   p.amount AS payment_amount, p.status AS payment_status,
                   o.status AS order_status, o.total AS order_total
            FROM payments p
            JOIN orders o ON o.id = p.order_id AND o.tenant_id = p.tenant_id
            WHERE p.status::text = 'approved'
              AND o.status::text = 'cancelled'
            LIMIT 101
        """,
    },
    {
        "name": "approved_payment_without_financial_projection",
        "classification": "inconsistent",
        "tables": ("orders", "payments", "finance_transactions"),
        "query": """
            SELECT p.id AS payment_id, p.tenant_id, p.order_id,
                   p.amount AS payment_amount, p.status AS payment_status
            FROM payments p
            JOIN orders o ON o.id = p.order_id AND o.tenant_id = p.tenant_id
            LEFT JOIN finance_transactions ft
              ON ft.payment_id = p.id
             AND ft.tenant_id = p.tenant_id
             AND ft.status::text <> 'cancelled'
            WHERE p.status::text = 'approved'
              AND ft.id IS NULL
            LIMIT 101
        """,
    },
    {
        "name": "multiple_financial_projections_per_payment",
        "classification": "blocked_auto_fix",
        "tables": ("payments", "finance_transactions"),
        "query": """
            SELECT ft.tenant_id, ft.payment_id,
                   COUNT(*) AS projection_count,
                   ARRAY_AGG(ft.id ORDER BY ft.id) AS transaction_ids
            FROM finance_transactions ft
            JOIN payments p ON p.id = ft.payment_id AND p.tenant_id = ft.tenant_id
            WHERE ft.payment_id IS NOT NULL
              AND ft.status::text <> 'cancelled'
            GROUP BY ft.tenant_id, ft.payment_id
            HAVING COUNT(*) > 1
            LIMIT 101
        """,
    },
    {
        "name": "confirmed_purchase_with_zero_value",
        "classification": "blocked_auto_fix",
        "tables": ("inventory_purchases",),
        "query": """
            SELECT id AS purchase_id, tenant_id, status, total_amount,
                   supplier_id, source, purchase_date
            FROM inventory_purchases
            WHERE status = 'confirmed'
              AND (total_amount IS NULL OR total_amount = 0)
            LIMIT 101
        """,
    },
    {
        "name": "confirmed_purchase_without_supplier",
        "classification": "pending_decision",
        "tables": ("inventory_purchases",),
        "query": """
            SELECT id AS purchase_id, tenant_id, status, total_amount,
                   supplier_id, source, purchase_date
            FROM inventory_purchases
            WHERE status = 'confirmed'
              AND supplier_id IS NULL
            LIMIT 101
        """,
    },
    {
        "name": "confirmed_purchase_without_financial_obligation",
        "classification": "inconsistent",
        "tables": ("inventory_purchases", "finance_transactions", "finance_obligations"),
        "query": """
            SELECT ip.id AS purchase_id, ip.tenant_id, ip.total_amount,
                   ip.status, ip.supplier_id, ip.source
            FROM inventory_purchases ip
            LEFT JOIN finance_transactions ft
              ON ft.inventory_purchase_id = ip.id
             AND ft.tenant_id = ip.tenant_id
             AND ft.status::text <> 'cancelled'
            LEFT JOIN finance_obligations fo
              ON fo.id = ft.obligation_id
             AND fo.tenant_id = ip.tenant_id
            WHERE ip.status = 'confirmed'
              AND fo.id IS NULL
            LIMIT 101
        """,
    },
    {
        "name": "operational_and_financial_value_divergence",
        "classification": "pending_decision",
        "tables": ("orders", "payments", "finance_transactions", "inventory_purchases"),
        "query": """
            SELECT 'payment_order' AS source_kind, p.tenant_id,
                   p.id AS source_id, p.order_id AS related_id,
                   p.amount AS operational_amount, o.total AS expected_amount,
                   ABS(CAST(p.amount AS numeric) - CAST(o.total AS numeric)) AS difference
            FROM payments p
            JOIN orders o ON o.id = p.order_id AND o.tenant_id = p.tenant_id
            WHERE p.status::text = 'approved'
              AND ROUND(CAST(p.amount AS numeric) * 100)
                  IS DISTINCT FROM ROUND(CAST(o.total AS numeric) * 100)
            UNION ALL
            SELECT 'payment_finance' AS source_kind, p.tenant_id,
                   p.id AS source_id, ft.id AS related_id,
                   p.amount AS operational_amount, ft.amount AS expected_amount,
                   ABS(CAST(p.amount AS numeric) - CAST(ft.amount AS numeric)) AS difference
            FROM payments p
            JOIN finance_transactions ft
              ON ft.payment_id = p.id
             AND ft.tenant_id = p.tenant_id
             AND ft.status::text <> 'cancelled'
            WHERE p.status::text = 'approved'
              AND ROUND(CAST(p.amount AS numeric) * 100)
                  IS DISTINCT FROM ROUND(CAST(ft.amount AS numeric) * 100)
            UNION ALL
            SELECT 'purchase_finance' AS source_kind, ip.tenant_id,
                   ip.id AS source_id, ft.id AS related_id,
                   ip.total_amount AS operational_amount, ft.amount AS expected_amount,
                   ABS(CAST(ip.total_amount AS numeric) - CAST(ft.amount AS numeric)) AS difference
            FROM inventory_purchases ip
            JOIN finance_transactions ft
              ON ft.inventory_purchase_id = ip.id
             AND ft.tenant_id = ip.tenant_id
             AND ft.status::text <> 'cancelled'
            WHERE ip.status = 'confirmed'
              AND ROUND(CAST(ip.total_amount AS numeric) * 100)
                  IS DISTINCT FROM ROUND(CAST(ft.amount AS numeric) * 100)
            LIMIT 101
        """,
    },
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--schema", default="public")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def _validated_schema(schema: str) -> str:
    if not schema or not _IDENTIFIER_RE.fullmatch(schema):
        raise ValueError("Informe um schema PostgreSQL valido.")
    return schema


def _table_names(connection, schema: str) -> set[str]:
    rows = connection.execute(
        text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = :schema
        """),
        {"schema": schema},
    )
    return {row[0] for row in rows}


def _overall_status(findings: list[dict], blocked: bool) -> str:
    if blocked:
        return "BLOCKED"
    return "FAIL" if findings else "PASS"


def run(database_url: str, schema: str = "public") -> dict:
    if not database_url or not database_url.startswith(("postgresql://", "postgresql+")):
        raise ValueError("Informe DATABASE_URL apontando para PostgreSQL.")
    schema = _validated_schema(schema)
    engine = create_engine(database_url, pool_pre_ping=True)
    findings: list[dict] = []
    checks: list[dict] = []
    blocked = False
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '30s'"))
            connection.execute(text("SET LOCAL lock_timeout = '2s'"))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            if str(connection.execute(text("SHOW transaction_read_only")).scalar()).lower() != "on":
                raise RuntimeError("A auditoria nao conseguiu confirmar transaction_read_only=on.")

            tables = _table_names(connection, schema)
            missing = sorted(set(REQUIRED_TABLES) - tables)
            if missing:
                blocked = True
                checks.append({"status": "BLOCKED", "missing_tables": missing})
            else:
                for check in CHECKS:
                    missing_check_tables = sorted(set(check["tables"]) - tables)
                    if missing_check_tables:
                        blocked = True
                        checks.append({
                            "name": check["name"],
                            "classification": check["classification"],
                            "status": "BLOCKED",
                            "missing_tables": missing_check_tables,
                        })
                        continue
                    rows = connection.execute(text(check["query"])).mappings().fetchmany(101)
                    truncated = len(rows) > 100
                    result = {
                        "name": check["name"],
                        "classification": check["classification"],
                        "status": "FAIL" if rows else "PASS",
                        "count": min(len(rows), 100),
                        "truncated": truncated,
                        "sample": [dict(row) for row in rows[:10]],
                    }
                    checks.append(result)
                    if rows:
                        findings.append(result)
            connection.rollback()
    finally:
        engine.dispose()
    return {
        "audit": "finance-reconciliation",
        "status": _overall_status(findings, blocked),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "schema": schema,
        "checks": checks,
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run(args.database_url, args.schema)
    except (SQLAlchemyError, RuntimeError, ValueError) as exc:
        print(json.dumps({"audit": "finance-reconciliation", "status": "BLOCKED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    output = json.dumps(report, ensure_ascii=False, default=str) if args.as_json else json.dumps(report, ensure_ascii=False, indent=2, default=str)
    print(output)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

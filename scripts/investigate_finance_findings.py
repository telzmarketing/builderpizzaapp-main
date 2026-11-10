"""Read-only evidence report for the known finance reconciliation findings.

This command deliberately reports database evidence only.  It does not infer
whether a payment should be refunded/cancelled or whether a purchase should
be approved, rejected, or converted into a payable.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

REQUIRED_TABLES = (
    "orders",
    "payments",
    "inventory_purchases",
    "inventory_purchase_items",
    "inventory_items",
    "inventory_suppliers",
    "finance_transactions",
    "finance_obligations",
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


def _rows(connection, statement: str) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(text(statement)).mappings().all()]


def _payment_evidence(connection, schema: str) -> list[dict[str, Any]]:
    return _rows(
        connection,
        f"""
        SELECT
            p.id AS payment_id,
            p.tenant_id,
            p.order_id,
            p.amount AS payment_amount,
            p.status::text AS payment_status,
            p.method::text AS payment_method,
            p.gateway,
            p.provider,
            p.provider_payment_id,
            p.provider_status,
            p.created_at AS payment_created_at,
            p.updated_at AS payment_updated_at,
            p.paid_at,
            p.cancelled_at AS payment_cancelled_at,
            p.refunded_at,
            o.status::text AS order_status,
            o.total AS order_total,
            o.created_at AS order_created_at,
            o.updated_at AS order_updated_at,
            o.cancelled_at AS order_cancelled_at,
            o.cancelled_by,
            o.cancellation_reason,
            o.paid_at AS order_paid_at,
            COALESCE(
                jsonb_agg(
                    DISTINCT jsonb_build_object(
                        'transaction_id', ft.id,
                        'tenant_id', ft.tenant_id,
                        'status', ft.status,
                        'amount', ft.amount,
                        'paid_amount', ft.paid_amount,
                        'entry_type', ft.entry_type,
                        'origin_type', ft.origin_type,
                        'origin_id', ft.origin_id,
                        'order_id', ft.order_id,
                        'payment_id', ft.payment_id,
                        'obligation_id', ft.obligation_id,
                        'created_at', ft.created_at
                    )
                ) FILTER (WHERE ft.id IS NOT NULL),
                '[]'::jsonb
            ) AS finance_transactions,
            COALESCE(
                jsonb_agg(
                    DISTINCT jsonb_build_object(
                        'obligation_id', fo.id,
                        'tenant_id', fo.tenant_id,
                        'status', fo.status,
                        'total_amount', fo.total_amount,
                        'idempotency_key', fo.idempotency_key,
                        'created_at', fo.created_at
                    )
                ) FILTER (WHERE fo.id IS NOT NULL),
                '[]'::jsonb
            ) AS finance_obligations
        FROM {schema}.payments p
        JOIN {schema}.orders o
          ON o.id = p.order_id
         AND o.tenant_id IS NOT DISTINCT FROM p.tenant_id
        LEFT JOIN {schema}.finance_transactions ft
          ON ft.payment_id = p.id
         AND ft.tenant_id IS NOT DISTINCT FROM p.tenant_id
        LEFT JOIN {schema}.finance_obligations fo
          ON fo.id = ft.obligation_id
         AND fo.tenant_id = ft.tenant_id
        WHERE p.status::text = 'approved'
          AND o.status::text = 'cancelled'
        GROUP BY
            p.id, p.tenant_id, p.order_id, p.amount, p.status, p.method,
            p.gateway, p.provider, p.provider_payment_id, p.provider_status,
            p.created_at, p.updated_at, p.paid_at, p.cancelled_at,
            p.refunded_at, o.status, o.total, o.created_at, o.updated_at,
            o.cancelled_at, o.cancelled_by, o.cancellation_reason, o.paid_at
        ORDER BY p.created_at, p.id
        LIMIT 101
        """,
    )


def _purchase_evidence(connection, schema: str) -> list[dict[str, Any]]:
    return _rows(
        connection,
        f"""
        SELECT
            ip.id AS purchase_id,
            ip.tenant_id,
            ip.status AS purchase_status,
            ip.total_amount,
            ip.supplier_id,
            s.name AS supplier_name,
            s.document AS supplier_document,
            ip.source,
            ip.title,
            ip.purchase_date,
            ip.expected_date,
            ip.invoice_number,
            ip.requested_at,
            ip.created_at AS purchase_created_at,
            ip.updated_at AS purchase_updated_at,
            COALESCE(
                jsonb_agg(
                    DISTINCT jsonb_build_object(
                        'item_id', ipi.id,
                        'inventory_item_id', ipi.item_id,
                        'item_name', ii.name,
                        'sku', ii.sku,
                        'quantity', ipi.quantity,
                        'unit_cost', ipi.unit_cost,
                        'total_cost', ipi.total_cost
                    )
                ) FILTER (WHERE ipi.id IS NOT NULL),
                '[]'::jsonb
            ) AS items,
            COALESCE(
                jsonb_agg(
                    DISTINCT jsonb_build_object(
                        'transaction_id', ft.id,
                        'tenant_id', ft.tenant_id,
                        'status', ft.status,
                        'amount', ft.amount,
                        'paid_amount', ft.paid_amount,
                        'entry_type', ft.entry_type,
                        'origin_type', ft.origin_type,
                        'origin_id', ft.origin_id,
                        'inventory_purchase_id', ft.inventory_purchase_id,
                        'obligation_id', ft.obligation_id,
                        'created_at', ft.created_at
                    )
                ) FILTER (WHERE ft.id IS NOT NULL),
                '[]'::jsonb
            ) AS finance_transactions,
            COALESCE(
                jsonb_agg(
                    DISTINCT jsonb_build_object(
                        'obligation_id', fo.id,
                        'tenant_id', fo.tenant_id,
                        'status', fo.status,
                        'total_amount', fo.total_amount,
                        'supplier_name', fo.supplier_name,
                        'supplier_document', fo.supplier_document,
                        'idempotency_key', fo.idempotency_key,
                        'created_at', fo.created_at
                    )
                ) FILTER (WHERE fo.id IS NOT NULL),
                '[]'::jsonb
            ) AS finance_obligations
        FROM {schema}.inventory_purchases ip
        LEFT JOIN {schema}.inventory_suppliers s
          ON s.id = ip.supplier_id
         AND s.tenant_id IS NOT DISTINCT FROM ip.tenant_id
        LEFT JOIN {schema}.inventory_purchase_items ipi
          ON ipi.purchase_id = ip.id
         AND ipi.tenant_id IS NOT DISTINCT FROM ip.tenant_id
        LEFT JOIN {schema}.inventory_items ii
          ON ii.id = ipi.item_id
         AND ii.tenant_id IS NOT DISTINCT FROM ipi.tenant_id
        LEFT JOIN {schema}.finance_transactions ft
          ON ft.inventory_purchase_id = ip.id
         AND ft.tenant_id IS NOT DISTINCT FROM ip.tenant_id
        LEFT JOIN {schema}.finance_obligations fo
          ON fo.id = ft.obligation_id
         AND fo.tenant_id = ft.tenant_id
        WHERE ip.status = 'confirmed'
          AND (ip.total_amount IS NULL OR ip.total_amount = 0)
        GROUP BY
            ip.id, ip.tenant_id, ip.status, ip.total_amount, ip.supplier_id,
            s.name, s.document, ip.source, ip.title, ip.purchase_date,
            ip.expected_date, ip.invoice_number, ip.requested_at,
            ip.created_at, ip.updated_at
        ORDER BY ip.purchase_date, ip.id
        LIMIT 101
        """,
    )


def run(database_url: str, schema: str = "public") -> dict[str, Any]:
    if not database_url or not database_url.startswith(("postgresql://", "postgresql+")):
        raise ValueError("Informe DATABASE_URL apontando para PostgreSQL.")
    schema = _validated_schema(schema)
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '30s'"))
            connection.execute(text("SET LOCAL lock_timeout = '2s'"))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            read_only = str(connection.execute(text("SHOW transaction_read_only")).scalar()).lower()
            if read_only != "on":
                raise RuntimeError("A investigacao nao conseguiu confirmar transaction_read_only=on.")

            tables = _table_names(connection, schema)
            missing = sorted(set(REQUIRED_TABLES) - tables)
            if missing:
                connection.rollback()
                return {
                    "audit": "finance-findings-investigation",
                    "status": "BLOCKED",
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "read_only": True,
                    "schema": schema,
                    "missing_tables": missing,
                    "payments": [],
                    "purchases": [],
                }

            payments = _payment_evidence(connection, schema)
            purchases = _purchase_evidence(connection, schema)
            connection.rollback()
            return {
                "audit": "finance-findings-investigation",
                "status": "PASS",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "read_only": True,
                "schema": schema,
                "payments": payments,
                "purchases": purchases,
                "counts": {"payments": len(payments), "purchases": len(purchases)},
                "inference": False,
            }
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = run(args.database_url, args.schema)
    except (SQLAlchemyError, RuntimeError, ValueError) as exc:
        print(
            json.dumps(
                {"audit": "finance-findings-investigation", "status": "BLOCKED", "error": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    output = json.dumps(report, ensure_ascii=False, default=str, indent=not args.as_json)
    print(output)
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

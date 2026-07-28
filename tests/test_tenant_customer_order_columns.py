from pathlib import Path


def test_order_code_is_created_before_tenant_indexes_and_backfill():
    versions = Path(__file__).parents[1] / "backend/migrations/versions"
    expand = (
        versions / "20260726_tenant_customers_orders_expand.py"
    ).read_text(encoding="utf-8")
    backfill = (
        versions / "20260727_tenant_customers_orders_backfill.py"
    ).read_text(encoding="utf-8")

    column_at = expand.index(
        "ALTER TABLE orders ADD COLUMN IF NOT EXISTS order_code VARCHAR(10)"
    )
    scoped_indexes_at = expand.index(
        "for name, table, columns, predicate in SCOPED_UNIQUE_INDEXES:"
    )

    assert column_at < scoped_indexes_at
    assert '("orders", "order_code", "order_code IS NOT NULL")' in backfill


def test_delivery_person_email_is_created_before_scoped_index():
    migration = (
        Path(__file__).parents[1]
        / "backend/migrations/versions/20260730_tenant_operations_expand.py"
    ).read_text(encoding="utf-8")

    assert migration.index(
        "ADD COLUMN IF NOT EXISTS email VARCHAR(200)"
    ) < migration.index(
        "for name, table, columns, predicate in SCOPED_UNIQUES:"
    )

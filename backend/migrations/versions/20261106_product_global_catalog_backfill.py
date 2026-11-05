"""Backfill global pizza catalog rows from legacy product options.

This is an additive, tenant-scoped and idempotent data migration.  Legacy
rows remain untouched except for nullable global links and the nullable price
override required to preserve a legacy price when the deterministic global
price differs.
"""

from alembic import op


revision = "20261106_product_global_catalog_backfill"
down_revision = "20261106_product_global_links"
branch_labels = None
depends_on = None


def _backfill_sizes() -> None:
    op.execute(
        """
        WITH source AS (
            SELECT tenant_id,
                   trim(label) AS name,
                   description,
                   sort_order,
                   active,
                   is_default,
                   lower(regexp_replace(trim(label), '\\s+', ' ', 'g')) AS normalized_name
            FROM product_sizes
            WHERE tenant_id IS NOT NULL
              AND trim(label) <> ''
        ), grouped AS (
            SELECT tenant_id, normalized_name,
                   min(name) AS name,
                   min(description) AS description,
                   min(sort_order) AS sort_order,
                   bool_or(active) AS active,
                   bool_or(is_default) AS is_default
            FROM source
            GROUP BY tenant_id, normalized_name
        )
        INSERT INTO pizza_global_sizes
            (id, tenant_id, name, description, sort_order, active, is_default,
             created_at, updated_at)
        SELECT
            substr(md5('pizza_global_sizes:' || tenant_id || ':' || normalized_name), 1, 8) || '-' ||
            substr(md5('pizza_global_sizes:' || tenant_id || ':' || normalized_name), 9, 4) || '-' ||
            substr(md5('pizza_global_sizes:' || tenant_id || ':' || normalized_name), 13, 4) || '-' ||
            substr(md5('pizza_global_sizes:' || tenant_id || ':' || normalized_name), 17, 4) || '-' ||
            substr(md5('pizza_global_sizes:' || tenant_id || ':' || normalized_name), 21, 12),
            tenant_id, name, description, sort_order, active, is_default,
            now(),
            now()
        FROM grouped
        WHERE NOT EXISTS (
            SELECT 1
            FROM pizza_global_sizes existing
            WHERE existing.tenant_id = grouped.tenant_id
              AND lower(regexp_replace(trim(existing.name), '\\s+', ' ', 'g')) =
                  grouped.normalized_name
        )
        ON CONFLICT (tenant_id, name) DO NOTHING
        """
    )
    op.execute(
        """
        UPDATE product_sizes ps
        SET global_size_id = gs.id
        FROM pizza_global_sizes gs,
             (
            SELECT tenant_id,
                   product_id,
                   lower(regexp_replace(trim(label), '\\s+', ' ', 'g')) AS normalized_name
            FROM product_sizes
            WHERE tenant_id IS NOT NULL
              AND trim(label) <> ''
            GROUP BY tenant_id, product_id,
                     lower(regexp_replace(trim(label), '\\s+', ' ', 'g'))
            HAVING count(*) = 1
        ) safe
        WHERE ps.global_size_id IS NULL
          AND ps.tenant_id IS NOT NULL
          AND trim(ps.label) <> ''
          AND safe.tenant_id = ps.tenant_id
          AND safe.product_id = ps.product_id
          AND safe.normalized_name =
              lower(regexp_replace(trim(ps.label), '\\s+', ' ', 'g'))
          AND gs.tenant_id = ps.tenant_id
          AND lower(regexp_replace(trim(gs.name), '\\s+', ' ', 'g')) =
              lower(regexp_replace(trim(ps.label), '\\s+', ' ', 'g'))
        """
    )


def _backfill_options(option_kind: str, global_table: str, global_column: str) -> None:
    # The minimum legacy price is deterministic and lets every more expensive
    # product row retain its exact old amount through the override column.
    op.execute(
        f"""
        WITH source AS (
            SELECT tenant_id,
                   trim(name) AS name,
                   price_addition,
                   sort_order,
                   active,
                   lower(regexp_replace(trim(name), '\\s+', ' ', 'g')) AS normalized_name
            FROM product_crust_types
            WHERE tenant_id IS NOT NULL
              AND option_kind = '{option_kind}'
              AND trim(name) <> ''
        ), grouped AS (
            SELECT tenant_id, normalized_name,
                   min(name) AS name,
                   min(price_addition) AS price_addition,
                   min(sort_order) AS sort_order,
                   bool_or(active) AS active
            FROM source
            GROUP BY tenant_id, normalized_name
        )
        INSERT INTO {global_table}
            (id, tenant_id, name, description, price_addition, sort_order,
             active, created_at, updated_at)
        SELECT
            substr(md5('{global_table}:' || tenant_id || ':' || normalized_name), 1, 8) || '-' ||
            substr(md5('{global_table}:' || tenant_id || ':' || normalized_name), 9, 4) || '-' ||
            substr(md5('{global_table}:' || tenant_id || ':' || normalized_name), 13, 4) || '-' ||
            substr(md5('{global_table}:' || tenant_id || ':' || normalized_name), 17, 4) || '-' ||
            substr(md5('{global_table}:' || tenant_id || ':' || normalized_name), 21, 12),
            tenant_id, name, NULL, price_addition, sort_order, active,
            now(),
            now()
        FROM grouped
        WHERE NOT EXISTS (
            SELECT 1
            FROM {global_table} existing
            WHERE existing.tenant_id = grouped.tenant_id
              AND lower(regexp_replace(trim(existing.name), '\\s+', ' ', 'g')) =
                  grouped.normalized_name
        )
        ON CONFLICT (tenant_id, name) DO NOTHING
        """
    )
    op.execute(
        f"""
        UPDATE product_crust_types pct
        SET {global_column} = gc.id,
            price_addition_override = CASE
                WHEN pct.price_addition <> gc.price_addition
                    THEN pct.price_addition
                ELSE pct.price_addition_override
            END
        FROM {global_table} gc,
             (
            SELECT tenant_id,
                   product_id,
                   lower(regexp_replace(trim(name), '\\s+', ' ', 'g')) AS normalized_name
            FROM product_crust_types
            WHERE tenant_id IS NOT NULL
              AND option_kind = '{option_kind}'
              AND trim(name) <> ''
            GROUP BY tenant_id, product_id,
                     lower(regexp_replace(trim(name), '\\s+', ' ', 'g'))
            HAVING count(*) = 1
        ) safe
        WHERE {global_column} IS NULL
          AND pct.tenant_id IS NOT NULL
          AND pct.option_kind = '{option_kind}'
          AND trim(pct.name) <> ''
          AND safe.tenant_id = pct.tenant_id
          AND safe.product_id = pct.product_id
          AND safe.normalized_name =
              lower(regexp_replace(trim(pct.name), '\\s+', ' ', 'g'))
          AND gc.tenant_id = pct.tenant_id
          AND lower(regexp_replace(trim(gc.name), '\\s+', ' ', 'g')) =
              lower(regexp_replace(trim(pct.name), '\\s+', ' ', 'g'))
        """
    )


def upgrade() -> None:
    _backfill_sizes()
    _backfill_options("dough", "pizza_global_dough_types", "global_dough_type_id")
    _backfill_options("border", "pizza_global_crusts", "global_crust_id")


def downgrade() -> None:
    raise RuntimeError(
        "Forward-only migration: global catalog backfill must not be reversed automatically."
    )

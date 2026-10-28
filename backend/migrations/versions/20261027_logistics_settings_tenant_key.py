"""Align logistics settings identity with the tenant-scoped model.

The original operations migration kept ``id`` as a table-wide primary key
while the runtime model treats ``(tenant_id, id)`` as the identity.  A tenant
without an existing settings row therefore fails when the service creates its
``default`` row.  This forward-only repair makes the database contract match
the model without changing any settings values.
"""

from alembic import op


revision = "20261027_logistics_settings_tenant_key"
down_revision = "20261027_bi_mobile_analytics_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Do not guess ownership or silently discard duplicate settings.  The
    # release must stop and report the data problem for operator-led repair.
    op.execute(
        """
        DO $$
        DECLARE
            invalid_rows BIGINT;
            duplicate_tenants BIGINT;
            primary_key_name TEXT;
        BEGIN
            SELECT COUNT(*) INTO invalid_rows
            FROM logistics_settings
            WHERE tenant_id IS NULL;
            IF invalid_rows > 0 THEN
                RAISE EXCEPTION
                    'logistics_settings has % rows without tenant ownership; repair before migration',
                    invalid_rows;
            END IF;

            SELECT COUNT(*) INTO duplicate_tenants
            FROM (
                SELECT tenant_id FROM logistics_settings
                GROUP BY tenant_id HAVING COUNT(*) > 1
            ) duplicates;
            IF duplicate_tenants > 0 THEN
                RAISE EXCEPTION
                    'logistics_settings has % tenants with duplicate rows; repair before migration',
                    duplicate_tenants;
            END IF;

            SELECT con.conname INTO primary_key_name
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace ns ON ns.oid = rel.relnamespace
            WHERE ns.nspname = current_schema()
              AND rel.relname = 'logistics_settings'
              AND con.contype = 'p';

            IF primary_key_name IS NOT NULL THEN
                EXECUTE format(
                    'ALTER TABLE logistics_settings DROP CONSTRAINT %I',
                    primary_key_name
                );
            END IF;

            ALTER TABLE logistics_settings
                ALTER COLUMN tenant_id SET NOT NULL;
            ALTER TABLE logistics_settings
                ADD CONSTRAINT logistics_settings_pkey PRIMARY KEY (tenant_id, id);
        END $$;
        """
    )
    op.execute(
        "ALTER TABLE logistics_settings "
        "ADD COLUMN IF NOT EXISTS rate_per_delivery FLOAT DEFAULT 0.0"
    )


def downgrade() -> None:
    raise RuntimeError(
        "logistics_settings tenant identity is forward-only; restore from a backup if required."
    )

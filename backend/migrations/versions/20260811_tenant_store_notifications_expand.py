"""Expand tenant ownership for store social-proof notifications.

Revision ID: 20260811_tenant_store_notifications_expand
Revises: 20260810_tenant_backoffice_contract
"""
from alembic import op
import sqlalchemy as sa


revision = "20260811_tenant_store_notifications_expand"
down_revision = "20260810_tenant_backoffice_contract"
branch_labels = None
depends_on = None


TABLES = (
    "store_notification_settings",
    "store_notifications",
    "store_notification_days",
    "store_notification_impressions",
    "store_notification_captured",
)

SCOPED_UNIQUES = (
    ("uq_store_notification_settings_tenant_id_id", "store_notification_settings", "tenant_id, id", None),
    ("uq_mt_store_notification_settings_singleton", "store_notification_settings", "tenant_id", "tenant_id IS NOT NULL"),
    ("uq_store_notifications_tenant_id_id", "store_notifications", "tenant_id, id", None),
    ("uq_store_notification_days_tenant_id_id", "store_notification_days", "tenant_id, id", None),
    ("uq_store_notification_impressions_tenant_id_id", "store_notification_impressions", "tenant_id, id", None),
    ("uq_store_notification_captured_tenant_id_id", "store_notification_captured", "tenant_id, id", None),
    ("uq_mt_store_notification_captured_order", "store_notification_captured", "tenant_id, order_id", "order_id IS NOT NULL"),
)


def _create_scoped_unique(name: str, table: str, columns: str, where: str | None) -> None:
    predicate = f" WHERE {where}" if where else ""
    op.execute(sa.text(f"CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {table} ({columns}){predicate}"))


def upgrade() -> None:
    for table in TABLES:
        op.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS tenant_id VARCHAR"))
        op.execute(sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'fk_{table}_tenant'
                ) THEN
                    ALTER TABLE {table}
                    ADD CONSTRAINT fk_{table}_tenant
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id) NOT VALID;
                END IF;
            END $$;
            """
        ))
        op.execute(sa.text(f"CREATE INDEX IF NOT EXISTS ix_{table}_tenant_id ON {table} (tenant_id)"))

    legacy_tenant_id = "tenant-legacy-default"
    for table in TABLES:
        op.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET tenant_id=:tenant_id
                WHERE tenant_id IS NULL
                  AND EXISTS (SELECT 1 FROM tenants WHERE id=:tenant_id)
                """
            )
            .bindparams(tenant_id=legacy_tenant_id)
        )

    op.execute(sa.text(
        "UPDATE store_notification_settings "
        "SET id=:settings_id "
        "WHERE tenant_id=:tenant_id AND id='default' "
        "AND EXISTS (SELECT 1 FROM tenants WHERE id=:tenant_id)"
    ).bindparams(settings_id=f"store-notification-settings-{legacy_tenant_id}", tenant_id=legacy_tenant_id))

    for name, table, columns, where in SCOPED_UNIQUES:
        _create_scoped_unique(name, table, columns, where)


def downgrade() -> None:
    for name, _, _, _ in reversed(SCOPED_UNIQUES):
        op.execute(sa.text(f"DROP INDEX IF EXISTS {name}"))
    for table in reversed(TABLES):
        op.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS fk_{table}_tenant"))
        op.execute(sa.text(f"DROP INDEX IF EXISTS ix_{table}_tenant_id"))
        op.execute(sa.text(f"ALTER TABLE {table} DROP COLUMN IF EXISTS tenant_id"))

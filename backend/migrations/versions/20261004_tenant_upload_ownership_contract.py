"""Persist upload ownership and quarantine legacy references before namespace rollout."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20261004_tenant_upload_ownership_contract"
down_revision = "20261004_wave7_logistics_identity_contract"
branch_labels = None
depends_on = None

# Only tables that have an explicit tenant_id are candidates.  The migration
# records the reference for review; it deliberately does not create an asset
# row or move a file, because a bare legacy filename is not proof of ownership.
LEGACY_REFERENCE_SOURCES = (
    ("tenant_profiles", "tenant_id", "tenant_id", "logo_url"),
    ("products", "id", "tenant_id", "image_url"),
    ("promotions", "id", "tenant_id", "banner"),
    ("promotion_landing_pages", "id", "tenant_id", "image_url"),
    ("promotion_landing_pages", "id", "tenant_id", "image_url_2"),
    ("paid_traffic_creatives", "id", "tenant_id", "media_url"),
)


def _table_has_column(bind, table: str, column: str) -> bool:
    return bool(bind.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = :table AND column_name = :column
        LIMIT 1
    """), {"table": table, "column": column}).scalar())


def _record_legacy_references(bind) -> None:
    for table, id_column, tenant_column, url_column in LEGACY_REFERENCE_SOURCES:
        if not all(_table_has_column(bind, table, value) for value in (id_column, tenant_column, url_column)):
            continue
        # URL fields can be fully-qualified in some integrations.  Only the
        # historic local, un-namespaced /uploads/<filename> form is quarantined.
        op.execute(sa.text(f"""
            INSERT INTO tenant_upload_legacy_references
                (id, tenant_id, source_table, source_id, source_column, legacy_url, status, created_at)
            SELECT
                md5('{table}:' || source.{id_column}::text || ':' || '{url_column}'),
                source.{tenant_column},
                '{table}', source.{id_column}::text, '{url_column}', source.{url_column}, 'pending', NOW()
            FROM {table} source
            WHERE source.{tenant_column} IS NOT NULL
              AND source.{url_column} ~ '^/?uploads/[^/]+$'
            ON CONFLICT (source_table, source_id, source_column) DO NOTHING
        """))


def upgrade() -> None:
    op.create_table(
        "tenant_upload_assets",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(length=700), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("visibility", sa.String(length=10), nullable=False, server_default="public"),
        sa.Column("uploaded_by_admin_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("visibility IN ('public', 'private')", name="ck_tenant_upload_assets_visibility"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploaded_by_admin_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenant_upload_assets_tenant_id", "tenant_upload_assets", ["tenant_id"])
    op.create_index("uq_tenant_upload_assets_storage_key", "tenant_upload_assets", ["storage_key"], unique=True)
    op.create_index("ix_tenant_upload_assets_tenant_visibility", "tenant_upload_assets", ["tenant_id", "visibility"])

    op.create_table(
        "tenant_upload_legacy_references",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("source_table", sa.String(length=100), nullable=False),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.Column("source_column", sa.String(length=100), nullable=False),
        sa.Column("legacy_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_table", "source_id", "source_column", name="uq_tenant_upload_legacy_reference"),
    )
    op.create_index("ix_tenant_upload_legacy_references_tenant", "tenant_upload_legacy_references", ["tenant_id"])
    _record_legacy_references(op.get_bind())


def downgrade() -> None:
    # Removing the audit trail or ownership registry would make a rollback
    # silently expose tenant media again, so this migration is intentionally forward-only.
    pass

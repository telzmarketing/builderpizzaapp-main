"""Remove global marketing uniqueness superseded by tenant-scoped indexes.

Revision ID: 20261003_marketing_tenant_keys
Revises: 20261003_chatbot_tenant_keys
"""
from alembic import op
import sqlalchemy as sa


revision = "20261003_marketing_tenant_keys"
down_revision = "20261003_chatbot_tenant_keys"
branch_labels = None
depends_on = None


def _drop_single_column_unique(table: str, column: str) -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("""
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace ns ON ns.oid = rel.relnamespace
        WHERE ns.nspname = current_schema()
          AND rel.relname = :table
          AND con.contype = 'u'
          AND pg_get_constraintdef(con.oid) = :definition
    """), {"table": table, "definition": f"UNIQUE ({column})"}).scalars().all()
    for name in rows:
        op.drop_constraint(name, table, type_="unique")


def upgrade() -> None:
    for table, column in (
        ("visitor_profiles", "fingerprint"),
        ("tracking_links", "slug"),
        ("integration_connections", "integration_type"),
    ):
        _drop_single_column_unique(table, column)
    op.execute("ALTER TABLE marketing_settings ALTER COLUMN id DROP DEFAULT")
    op.execute("ALTER TABLE whatsapp_config ALTER COLUMN id DROP DEFAULT")


def downgrade() -> None:
    # Global uniqueness cannot be restored after legitimate per-tenant reuse.
    op.execute("ALTER TABLE marketing_settings ALTER COLUMN id SET DEFAULT 'default'")
    op.execute("ALTER TABLE whatsapp_config ALTER COLUMN id SET DEFAULT 'default'")

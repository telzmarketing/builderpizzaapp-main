"""Remove global chatbot keys superseded by tenant-scoped contracts.

Revision ID: 20261003_chatbot_tenant_keys
Revises: 20261003_marketing_workflow_tenant_isolation
"""
from alembic import op
import sqlalchemy as sa


revision = "20261003_chatbot_tenant_keys"
down_revision = "20261003_marketing_workflow_tenant_isolation"
branch_labels = None
depends_on = None


def _drop_global_session_unique() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text("""
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace ns ON ns.oid = rel.relnamespace
        WHERE ns.nspname = current_schema()
          AND rel.relname = 'chatbot_conversations'
          AND con.contype = 'u'
          AND pg_get_constraintdef(con.oid) ~ '^UNIQUE \\(session_id\\)$'
    """)).scalars().all()
    for name in rows:
        op.drop_constraint(name, "chatbot_conversations", type_="unique")


def upgrade() -> None:
    # The original singleton default is global. New settings IDs are generated
    # by ChatbotService and uniqueness is owned by uq_mt_chatbot_settings_singleton.
    op.execute("ALTER TABLE chatbot_settings ALTER COLUMN id DROP DEFAULT")
    _drop_global_session_unique()


def downgrade() -> None:
    # A global session key cannot be restored safely once different tenants use
    # the same browser session ID. Keep tenant-scoped data intact.
    op.execute("ALTER TABLE chatbot_settings ALTER COLUMN id SET DEFAULT 'default'")

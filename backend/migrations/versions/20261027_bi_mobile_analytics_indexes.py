"""Index tenant-scoped BI sales, storefront and attendance time ranges.

Only additive indexes are introduced. Existing order and attendance histories
remain unchanged. Index builds use the normal transactional Alembic path;
large installations should schedule this release in a maintenance window.
"""

from alembic import op


revision = "20261027_bi_mobile_analytics_indexes"
down_revision = "20261027_kds_dispatch_unit_completion"
branch_labels = None
depends_on = None


INDEXES = (
    ("ix_orders_tenant_created_at", "orders", ["tenant_id", "created_at"]),
    ("ix_visitor_events_tenant_created_at", "visitor_events", ["tenant_id", "created_at"]),
    ("ix_visitor_sessions_tenant_started_at", "visitor_sessions", ["tenant_id", "started_at"]),
    ("ix_chatbot_conversations_tenant_iniciada_em", "chatbot_conversations", ["tenant_id", "iniciada_em"]),
    ("ix_chatbot_conversations_tenant_encerrada_em", "chatbot_conversations", ["tenant_id", "encerrada_em"]),
)


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    raise RuntimeError("Forward-only: preserve tenant-scoped analytics access paths.")

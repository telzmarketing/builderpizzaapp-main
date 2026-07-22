"""Add tenant-aware customer contact risk and append-only history.

Revision ID: 20260812_customer_contact_risk
Revises: 20260811_tenant_store_notifications_expand
"""
from alembic import op
import sqlalchemy as sa

revision = "20260812_customer_contact_risk"
down_revision = "20260811_tenant_store_notifications_expand"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customer_channels", sa.Column("marketing_status", sa.String(30), nullable=False, server_default="active"))
    op.add_column("customer_channels", sa.Column("marketing_block_reason", sa.String(500), nullable=True))
    op.add_column("customer_channels", sa.Column("marketing_blocked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("customer_channels", sa.Column("marketing_status_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("ck_customer_channels_marketing_status", "customer_channels", "marketing_status IN ('active', 'blocked', 'opted_out', 'complaint_hold')")
    op.create_index("ix_customer_channels_tenant_marketing_status", "customer_channels", ["tenant_id", "marketing_status"])

    op.create_table(
        "customer_contact_risks",
        sa.Column("id", sa.String(), nullable=False), sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=False), sa.Column("channel", sa.String(40), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="low"),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("block_reason", sa.String(500)), sa.Column("blocked_at", sa.DateTime(timezone=True)),
        sa.Column("campaign_deliveries_15d", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_event_at", sa.DateTime(timezone=True)), sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id", "customer_id"], ["customers.tenant_id", "customers.id"], name="fk_customer_contact_risks_tenant_customer", ondelete="CASCADE"),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_customer_contact_risks_score"),
        sa.CheckConstraint("risk_level IN ('low', 'attention', 'high', 'blocked')", name="ck_customer_contact_risks_level"),
        sa.CheckConstraint("campaign_deliveries_15d >= 0", name="ck_customer_contact_risks_deliveries_15d"),
        sa.CheckConstraint("version >= 1", name="ck_customer_contact_risks_version"),
    )
    op.create_index("uq_customer_contact_risks_tenant_id_id", "customer_contact_risks", ["tenant_id", "id"], unique=True)
    op.create_index("uq_customer_contact_risks_tenant_customer_channel", "customer_contact_risks", ["tenant_id", "customer_id", "channel"], unique=True)
    op.create_index("ix_customer_contact_risks_tenant_level", "customer_contact_risks", ["tenant_id", "risk_level"])
    op.create_index("ix_customer_contact_risks_tenant_blocked", "customer_contact_risks", ["tenant_id", "is_blocked"])

    op.create_table(
        "customer_contact_risk_events",
        sa.Column("id", sa.String(), nullable=False), sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=False), sa.Column("customer_channel_id", sa.String()),
        sa.Column("risk_id", sa.String()), sa.Column("channel", sa.String(40), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False), sa.Column("points_delta", sa.Integer(), nullable=False),
        sa.Column("score_before", sa.Integer(), nullable=False), sa.Column("score_after", sa.Integer(), nullable=False),
        sa.Column("blocks_contact", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source_type", sa.String(50)), sa.Column("source_id", sa.String()), sa.Column("dedupe_key", sa.String(255)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tenant_id", "customer_id"], ["customers.tenant_id", "customers.id"], name="fk_customer_contact_risk_events_tenant_customer", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id", "customer_channel_id"], ["customer_channels.tenant_id", "customer_channels.id"], name="fk_customer_contact_risk_events_tenant_channel"),
        sa.ForeignKeyConstraint(["tenant_id", "risk_id"], ["customer_contact_risks.tenant_id", "customer_contact_risks.id"], name="fk_customer_contact_risk_events_tenant_risk"),
        sa.CheckConstraint("points_delta >= -100 AND points_delta <= 100", name="ck_contact_risk_events_points"),
        sa.CheckConstraint("score_before >= 0 AND score_before <= 100", name="ck_contact_risk_events_before"),
        sa.CheckConstraint("score_after >= 0 AND score_after <= 100", name="ck_contact_risk_events_after"),
    )
    op.create_index("uq_customer_contact_risk_events_tenant_id_id", "customer_contact_risk_events", ["tenant_id", "id"], unique=True)
    op.create_index("uq_customer_contact_risk_events_tenant_dedupe", "customer_contact_risk_events", ["tenant_id", "dedupe_key"], unique=True, postgresql_where=sa.text("dedupe_key IS NOT NULL"))
    op.create_index("ix_customer_contact_risk_events_lookup", "customer_contact_risk_events", ["tenant_id", "customer_id", "channel", "occurred_at"])
    op.create_index("ix_customer_contact_risk_events_risk", "customer_contact_risk_events", ["tenant_id", "risk_id", "occurred_at"])
    op.create_index("ix_customer_contact_risk_events_source", "customer_contact_risk_events", ["tenant_id", "source_type", "source_id"])


def downgrade() -> None:
    op.drop_table("customer_contact_risk_events")
    op.drop_table("customer_contact_risks")
    op.drop_index("ix_customer_channels_tenant_marketing_status", table_name="customer_channels")
    op.drop_constraint("ck_customer_channels_marketing_status", "customer_channels", type_="check")
    op.drop_column("customer_channels", "marketing_status_updated_at")
    op.drop_column("customer_channels", "marketing_blocked_at")
    op.drop_column("customer_channels", "marketing_block_reason")
    op.drop_column("customer_channels", "marketing_status")

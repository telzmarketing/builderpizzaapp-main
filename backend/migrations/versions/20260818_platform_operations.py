"""Add redacted platform errors and durable worker heartbeats.

Revision ID: 20260818_platform_operations
Revises: 20260817_platform_wave0
"""
from alembic import op
import sqlalchemy as sa

revision = "20260818_platform_operations"
down_revision = "20260817_platform_wave0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "platform_error_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="SET NULL")),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="error"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("error_code", sa.String(100)),
        sa.Column("exception_type", sa.String(160)),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("method", sa.String(12)),
        sa.Column("path", sa.String(300)),
        sa.Column("request_id", sa.String(100)),
        sa.Column("correlation_id", sa.String(100)),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("sample_context_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("acknowledged_by", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL")),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledgement_note", sa.Text()),
        sa.Column("resolved_by", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolution_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("severity IN ('info','warning','error','critical')", name="ck_platform_error_events_severity"),
        sa.CheckConstraint("status IN ('open','acknowledged','resolved')", name="ck_platform_error_events_status"),
        sa.CheckConstraint("occurrence_count > 0", name="ck_platform_error_events_occurrence_count"),
    )
    op.create_index("ix_platform_error_events_status_severity_seen", "platform_error_events", ["status", "severity", "last_seen_at"])
    op.create_index("ix_platform_error_events_tenant_seen", "platform_error_events", ["tenant_id", "last_seen_at"])
    op.create_index("ix_platform_error_events_request_id", "platform_error_events", ["request_id"])
    op.create_index(
        "uq_platform_error_events_open_fingerprint",
        "platform_error_events",
        [sa.text("coalesce(tenant_id, '')"), "source", "fingerprint"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )

    op.create_table(
        "platform_worker_heartbeats",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE")),
        sa.Column("worker_key", sa.String(100), nullable=False),
        sa.Column("instance_key", sa.String(120), nullable=False),
        sa.Column("queue_key", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("version", sa.String(80)),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('running','idle','degraded','stopped')", name="ck_platform_worker_heartbeats_status"),
        sa.UniqueConstraint("worker_key", "instance_key", name="uq_platform_worker_heartbeats_worker_instance"),
    )
    op.create_index("ix_platform_worker_heartbeats_queue_seen", "platform_worker_heartbeats", ["queue_key", "last_heartbeat_at"])
    op.create_index("ix_platform_worker_heartbeats_tenant_seen", "platform_worker_heartbeats", ["tenant_id", "last_heartbeat_at"])


def downgrade() -> None:
    op.drop_index(
        "ix_platform_worker_heartbeats_tenant_seen",
        table_name="platform_worker_heartbeats",
    )
    op.drop_index(
        "ix_platform_worker_heartbeats_queue_seen",
        table_name="platform_worker_heartbeats",
    )
    op.drop_table("platform_worker_heartbeats")

    op.drop_index(
        "uq_platform_error_events_open_fingerprint",
        table_name="platform_error_events",
    )
    op.drop_index(
        "ix_platform_error_events_request_id",
        table_name="platform_error_events",
    )
    op.drop_index(
        "ix_platform_error_events_tenant_seen",
        table_name="platform_error_events",
    )
    op.drop_index(
        "ix_platform_error_events_status_severity_seen",
        table_name="platform_error_events",
    )
    op.drop_table("platform_error_events")

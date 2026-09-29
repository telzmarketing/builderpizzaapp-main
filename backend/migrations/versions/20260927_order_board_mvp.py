"""Add isolated read-only order board devices, settings and timing.

Revision ID: 20260927_order_board_mvp
Revises: 20260926_dispatch_labels
"""
from alembic import op
import sqlalchemy as sa


revision = "20260927_order_board_mvp"
down_revision = "20260926_dispatch_labels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("ready_for_pickup_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_orders_order_board_active",
        "orders",
        ["tenant_id", "status", "fulfillment_type", "created_at"],
    )
    op.create_index(
        "ix_orders_order_board_delivered",
        "orders",
        ["tenant_id", "delivered_at"],
        postgresql_where=sa.text("status = 'delivered' AND delivered_at IS NOT NULL"),
    )
    op.create_index(
        "ix_orders_order_board_production_time",
        "orders",
        ["tenant_id", "ready_for_pickup_at"],
        postgresql_where=sa.text("ready_for_pickup_at IS NOT NULL AND preparation_started_at IS NOT NULL"),
    )

    op.create_table(
        "order_board_settings",
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("production_sla_minutes", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("dispatch_sla_minutes", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("completed_window_seconds", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("polling_interval_seconds", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("sound_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_orders", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("production_sla_minutes BETWEEN 1 AND 240", name="ck_order_board_settings_production_sla"),
        sa.CheckConstraint("dispatch_sla_minutes BETWEEN 1 AND 120", name="ck_order_board_settings_dispatch_sla"),
        sa.CheckConstraint("completed_window_seconds BETWEEN 30 AND 900", name="ck_order_board_settings_completed_window"),
        sa.CheckConstraint("polling_interval_seconds BETWEEN 3 AND 60", name="ck_order_board_settings_polling_interval"),
        sa.CheckConstraint("max_orders BETWEEN 10 AND 200", name="ck_order_board_settings_max_orders"),
    )
    op.create_table(
        "order_board_devices",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active','revoked')", name="ck_order_board_devices_status"),
    )
    op.create_index("ix_order_board_devices_tenant_status", "order_board_devices", ["tenant_id", "status"])
    op.create_index("uq_order_board_devices_token_hash", "order_board_devices", ["token_hash"], unique=True)

    op.create_table(
        "order_board_activations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("code_prefix", sa.String(4), nullable=False),
        sa.Column("code_salt", sa.String(32), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("claim_token_hash", sa.String(64), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True),
        sa.Column("device_id", sa.String(), sa.ForeignKey("order_board_devices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_by", sa.String(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending','approved','claimed','expired','cancelled')",
            name="ck_order_board_activations_status",
        ),
    )
    op.create_index("uq_order_board_activations_code_prefix", "order_board_activations", ["code_prefix"], unique=True)
    op.create_index("ix_order_board_activations_status_expires", "order_board_activations", ["status", "expires_at"])
    op.create_index("uq_order_board_activations_claim_hash", "order_board_activations", ["claim_token_hash"], unique=True)

    op.execute("""
        INSERT INTO order_board_settings (
            tenant_id, enabled, production_sla_minutes, dispatch_sla_minutes,
            completed_window_seconds, polling_interval_seconds, sound_enabled,
            max_orders, created_at, updated_at
        )
        SELECT id, FALSE, 20, 5, 120, 5, FALSE, 50, NOW(), NOW()
        FROM tenants
        ON CONFLICT (tenant_id) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index("uq_order_board_activations_claim_hash", table_name="order_board_activations")
    op.drop_index("ix_order_board_activations_status_expires", table_name="order_board_activations")
    op.drop_index("uq_order_board_activations_code_prefix", table_name="order_board_activations")
    op.drop_table("order_board_activations")
    op.drop_index("uq_order_board_devices_token_hash", table_name="order_board_devices")
    op.drop_index("ix_order_board_devices_tenant_status", table_name="order_board_devices")
    op.drop_table("order_board_devices")
    op.drop_table("order_board_settings")
    op.drop_index("ix_orders_order_board_production_time", table_name="orders")
    op.drop_index("ix_orders_order_board_delivered", table_name="orders")
    op.drop_index("ix_orders_order_board_active", table_name="orders")
    op.drop_column("orders", "ready_for_pickup_at")

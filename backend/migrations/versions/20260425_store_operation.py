"""store operation hours

Revision ID: 20260425_store_operation
Revises: 20260425_product_promotions
Create Date: 2026-04-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260425_store_operation"
down_revision = "20260425_product_promotions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "store_operation_settings",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), nullable=False, server_default="default"),
        sa.Column("manual_mode", sa.String(length=30), nullable=False, server_default="manual_open"),
        sa.Column("closed_message", sa.Text(), nullable=False, server_default="Loja fechada no momento."),
        sa.Column("allow_scheduled_orders", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("timezone", sa.String(length=80), nullable=False, server_default="America/Sao_Paulo"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_store_operation_settings_tenant_id", "store_operation_settings", ["tenant_id"])

    op.create_table(
        "store_weekly_schedules",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), nullable=False, server_default="default"),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_store_weekly_schedules_tenant_id", "store_weekly_schedules", ["tenant_id"])
    op.create_index("ix_store_weekly_schedules_weekday", "store_weekly_schedules", ["weekday"])

    op.create_table(
        "store_operation_intervals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("schedule_id", sa.String(), sa.ForeignKey("store_weekly_schedules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False, server_default="default"),
        sa.Column("open_time", sa.Time(), nullable=False),
        sa.Column("close_time", sa.Time(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_store_operation_intervals_schedule_id", "store_operation_intervals", ["schedule_id"])
    op.create_index("ix_store_operation_intervals_tenant_id", "store_operation_intervals", ["tenant_id"])

    op.create_table(
        "store_operation_exceptions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), nullable=False, server_default="default"),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("exception_type", sa.String(length=30), nullable=False),
        sa.Column("open_time", sa.Time(), nullable=True),
        sa.Column("close_time", sa.Time(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_store_operation_exceptions_tenant_id", "store_operation_exceptions", ["tenant_id"])
    op.create_index("ix_store_operation_exceptions_date", "store_operation_exceptions", ["date"])

    op.create_table(
        "store_operation_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(length=80), nullable=False, server_default="default"),
        sa.Column("admin_id", sa.String(), nullable=True),
        sa.Column("admin_email", sa.String(length=200), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_store_operation_logs_tenant_id", "store_operation_logs", ["tenant_id"])

    op.add_column("orders", sa.Column("is_scheduled", sa.Boolean(), nullable=True, server_default=sa.text("FALSE")))
    op.add_column("orders", sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "scheduled_for")
    op.drop_column("orders", "is_scheduled")
    op.drop_table("store_operation_logs")
    op.drop_table("store_operation_exceptions")
    op.drop_table("store_operation_intervals")
    op.drop_table("store_weekly_schedules")
    op.drop_table("store_operation_settings")

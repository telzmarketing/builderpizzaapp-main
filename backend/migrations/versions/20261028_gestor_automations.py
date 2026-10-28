"""Add tenant-scoped Gestor proactive automation rules and audit."""
from alembic import op
import sqlalchemy as sa


revision = "20261028_gestor_automations"
down_revision = "20261028_gestor_multimodal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gestor_automations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("created_by_admin_id", sa.String(), nullable=True),
        sa.Column("updated_by_admin_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("trigger_key", sa.String(length=80), nullable=False),
        sa.Column("conditions_json", sa.JSON(), nullable=False),
        sa.Column("actions_json", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_runs_per_hour", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("daily_cost_limit", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("daily_quantity_limit", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("max_actions_per_event", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("service_window_start", sa.String(length=5), nullable=False, server_default="08:00"),
        sa.Column("service_window_end", sa.String(length=5), nullable=False, server_default="22:00"),
        sa.Column("service_weekdays_json", sa.JSON(), nullable=False),
        sa.Column("opt_out_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_admin_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_gestor_automations_tenant_name"),
    )
    op.create_index(
        "ix_gestor_automations_tenant_enabled_trigger", "gestor_automations",
        ["tenant_id", "enabled", "trigger_key"],
    )

    op.create_table(
        "gestor_automation_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("automation_id", sa.String(), nullable=False),
        sa.Column("event_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("action_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_units", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("operation_ids_json", sa.JSON(), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["automation_id"], ["gestor_automations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "automation_id", "event_id", name="uq_gestor_automation_runs_event"),
    )
    op.create_index(
        "ix_gestor_automation_runs_tenant_status_created", "gestor_automation_runs",
        ["tenant_id", "status", "created_at"],
    )
    op.create_index(
        "ix_gestor_automation_runs_tenant_automation_created", "gestor_automation_runs",
        ["tenant_id", "automation_id", "created_at"],
    )

    op.create_table(
        "gestor_automation_audits",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("automation_id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=True),
        sa.Column("actor_admin_id", sa.String(), nullable=True),
        sa.Column("event", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["automation_id"], ["gestor_automations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["gestor_automation_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_admin_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_gestor_automation_audits_tenant_created", "gestor_automation_audits", ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_gestor_automation_audits_automation_created", "gestor_automation_audits", ["automation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_gestor_automation_audits_automation_created", table_name="gestor_automation_audits")
    op.drop_index("ix_gestor_automation_audits_tenant_created", table_name="gestor_automation_audits")
    op.drop_table("gestor_automation_audits")
    op.drop_index("ix_gestor_automation_runs_tenant_automation_created", table_name="gestor_automation_runs")
    op.drop_index("ix_gestor_automation_runs_tenant_status_created", table_name="gestor_automation_runs")
    op.drop_table("gestor_automation_runs")
    op.drop_index("ix_gestor_automations_tenant_enabled_trigger", table_name="gestor_automations")
    op.drop_table("gestor_automations")

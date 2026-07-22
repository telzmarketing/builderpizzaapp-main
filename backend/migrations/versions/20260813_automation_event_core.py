"""Tenant-aware transversal automation core.

Revision ID: 20260813_automation_event_core
Revises: 20260812_customer_contact_risk
"""
from alembic import op
import sqlalchemy as sa

revision = "20260813_automation_event_core"
down_revision = "20260812_customer_contact_risk"
branch_labels = None
depends_on = None

CHILDREN = ("automation_conditions", "automation_actions", "automation_executions", "automation_execution_logs", "automation_audit_logs")


def upgrade() -> None:
    op.add_column("marketing_automations", sa.Column("trigger_config_json", sa.Text(), nullable=False, server_default="{}"))
    op.add_column("automation_executions", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("automation_executions", sa.Column("locked_by", sa.String(120), nullable=True))
    for table in CHILDREN:
        op.add_column(table, sa.Column("tenant_id", sa.String(), nullable=True))
    op.execute("UPDATE automation_conditions c SET tenant_id=a.tenant_id FROM marketing_automations a WHERE a.id=c.automation_id")
    op.execute("UPDATE automation_actions c SET tenant_id=a.tenant_id FROM marketing_automations a WHERE a.id=c.automation_id")
    op.execute("UPDATE automation_executions c SET tenant_id=a.tenant_id FROM marketing_automations a WHERE a.id=c.automation_id")
    op.execute("UPDATE automation_execution_logs c SET tenant_id=a.tenant_id FROM marketing_automations a WHERE a.id=c.automation_id")
    op.execute("UPDATE automation_execution_logs c SET tenant_id=e.tenant_id FROM automation_executions e WHERE c.tenant_id IS NULL AND e.id=c.execution_id")
    op.execute("UPDATE automation_audit_logs c SET tenant_id=a.tenant_id FROM marketing_automations a WHERE a.id=c.automation_id")
    for table in CHILDREN:
        op.execute(f"UPDATE {table} SET tenant_id='tenant-legacy-default' WHERE tenant_id IS NULL")
        op.create_foreign_key(f"fk_{table}_tenant", table, "tenants", ["tenant_id"], ["id"])
        op.alter_column(table, "tenant_id", existing_type=sa.String(), nullable=False)
        op.create_index(f"ix_{table}_tenant", table, ["tenant_id"])

    op.create_table("automation_events",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("event_key", sa.String(120), nullable=False), sa.Column("event_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("aggregate_type", sa.String(80), nullable=False), sa.Column("aggregate_id", sa.String(), nullable=False),
        sa.Column("customer_id", sa.String()), sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"), sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("locked_at", sa.DateTime(timezone=True)), sa.Column("locked_by", sa.String(120)),
        sa.Column("processed_at", sa.DateTime(timezone=True)), sa.Column("last_error", sa.Text()),
        sa.Column("correlation_id", sa.String()), sa.Column("causation_id", sa.String()), sa.Column("dedupe_key", sa.String(300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_automation_events_tenant"),
        sa.ForeignKeyConstraint(["tenant_id", "customer_id"], ["customers.tenant_id", "customers.id"], name="fk_automation_events_tenant_customer"),
        sa.CheckConstraint("status IN ('pending','processing','processed','failed','dead')", name="ck_automation_events_status"),
        sa.CheckConstraint("attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts", name="ck_automation_events_attempts"),
        sa.UniqueConstraint("tenant_id", "dedupe_key", name="uq_automation_events_tenant_dedupe"))
    op.create_index("ix_automation_events_tenant_status_available", "automation_events", ["tenant_id", "status", "available_at"])
    op.create_index("ix_automation_events_tenant_key_occurred", "automation_events", ["tenant_id", "event_key", "occurred_at"])
    op.create_index("ix_automation_events_tenant_aggregate", "automation_events", ["tenant_id", "aggregate_type", "aggregate_id"])
    # Legacy customer_events ids are a different event namespace and cannot be remapped safely.
    op.execute("UPDATE automation_executions SET trigger_event_id=NULL WHERE trigger_event_id IS NOT NULL")
    op.execute("""DO $$ DECLARE n text; BEGIN FOR n IN SELECT conname FROM pg_constraint WHERE conrelid='automation_executions'::regclass AND contype='f' AND pg_get_constraintdef(oid) LIKE '%trigger_event_id%' LOOP EXECUTE format('ALTER TABLE automation_executions DROP CONSTRAINT %I', n); END LOOP; END $$""")
    op.create_foreign_key("fk_automation_executions_trigger_event", "automation_executions", "automation_events", ["trigger_event_id"], ["id"], ondelete="SET NULL")
    op.drop_constraint("uq_automation_executions_dedupe_key", "automation_executions", type_="unique")
    op.create_unique_constraint("uq_automation_executions_tenant_dedupe", "automation_executions", ["tenant_id", "dedupe_key"])
    op.create_index("ix_automation_executions_tenant_status_scheduled", "automation_executions", ["tenant_id", "status", "scheduled_at"])
    op.create_index("ix_automation_executions_tenant_status_locked", "automation_executions", ["tenant_id", "status", "locked_at"])


def downgrade() -> None:
    op.drop_index("ix_automation_executions_tenant_status_locked", table_name="automation_executions")
    op.drop_index("ix_automation_executions_tenant_status_scheduled", table_name="automation_executions")
    op.drop_constraint("uq_automation_executions_tenant_dedupe", "automation_executions", type_="unique")
    op.create_unique_constraint("uq_automation_executions_dedupe_key", "automation_executions", ["dedupe_key"])
    op.drop_constraint("fk_automation_executions_trigger_event", "automation_executions", type_="foreignkey")
    op.execute("UPDATE automation_executions SET trigger_event_id=NULL WHERE trigger_event_id IS NOT NULL")
    op.create_foreign_key("fk_automation_executions_trigger_event_id_customer_events", "automation_executions", "customer_events", ["trigger_event_id"], ["id"], ondelete="SET NULL")
    op.drop_table("automation_events")
    for table in reversed(CHILDREN):
        op.drop_index(f"ix_{table}_tenant", table_name=table)
        op.drop_constraint(f"fk_{table}_tenant", table, type_="foreignkey")
        op.drop_column(table, "tenant_id")
    op.drop_column("marketing_automations", "trigger_config_json")
    op.drop_column("automation_executions", "locked_by")
    op.drop_column("automation_executions", "locked_at")

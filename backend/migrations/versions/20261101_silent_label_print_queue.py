"""Add operational queue state to existing label print audit records.

The published browser-dialog result is preserved in ``result_status``.  The
new fields are for a future local/network print agent and do not send bytes to
an operating-system or network printer by themselves.
"""
from alembic import op
import sqlalchemy as sa


revision = "20261101_silent_label_print_queue"
down_revision = "20261101_kds_production_stations"
branch_labels = None
depends_on = None


TRANSPORT_CHECK = "transport_status IN ('enqueued','sent','confirmed','error')"


def _upgrade_table(table):
    op.add_column(table, sa.Column("transport_status", sa.String(20), nullable=False, server_default="enqueued"))
    op.add_column(table, sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column(table, sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"))
    op.add_column(table, sa.Column("agent_job_id", sa.String(160), nullable=True))
    op.add_column(table, sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column(table, sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_check_constraint(f"ck_{table}_transport_status", table, TRANSPORT_CHECK)
    op.create_index(f"ix_{table}_transport", table, ["tenant_id", "transport_status", "created_at"])


def upgrade() -> None:
    _upgrade_table("label_print_jobs")
    _upgrade_table("preparation_label_print_jobs")


def _downgrade_table(table):
    op.drop_index(f"ix_{table}_transport", table_name=table)
    op.drop_constraint(f"ck_{table}_transport_status", table_name=table, type_="check")
    for name in ("updated_at", "last_error", "next_attempt_at", "failed_at", "confirmed_at", "sent_at", "claimed_at", "agent_job_id", "max_attempts", "attempt_count", "transport_status"):
        op.drop_column(table, name)


def downgrade() -> None:
    _downgrade_table("preparation_label_print_jobs")
    _downgrade_table("label_print_jobs")

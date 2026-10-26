"""Audit preparation labels without fabricating an order relationship."""
from alembic import op
import sqlalchemy as sa

revision = "20261026_preparation_label_jobs"
down_revision = "20261026_preparation_execution_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "preparation_label_print_jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("execution_id", sa.String(), nullable=False),
        sa.Column("printer_id", sa.String(), nullable=True),
        sa.Column("template_id", sa.String(), nullable=True),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("job_type", sa.String(length=20), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("copies", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("result_status", sa.String(length=30), nullable=False, server_default="requested"),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id", "execution_id"], ["preparation_executions.tenant_id", "preparation_executions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["printer_id"], ["label_printers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["template_id"], ["label_templates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_preparation_label_jobs_idempotency"),
        sa.CheckConstraint("job_type IN ('print','reprint')", name="ck_preparation_label_jobs_type"),
        sa.CheckConstraint("result_status IN ('requested','dialog_opened')", name="ck_preparation_label_jobs_result"),
    )
    op.create_index("ix_preparation_label_jobs_tenant_execution", "preparation_label_print_jobs", ["tenant_id", "execution_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_preparation_label_jobs_tenant_execution", table_name="preparation_label_print_jobs")
    op.drop_table("preparation_label_print_jobs")

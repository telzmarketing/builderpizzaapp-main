"""Reviewable weekly PCP forecasts derived from completed orders."""
from alembic import op
import sqlalchemy as sa

revision = "20261026_pcp_weekly_plans"
down_revision = "20261026_preparation_label_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("pcp_weekly_plans",
        sa.Column("id", sa.String(), nullable=False), sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False), sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("source_window_start", sa.Date(), nullable=False), sa.Column("source_window_end", sa.Date(), nullable=False),
        sa.Column("suggestions_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("approved_by", sa.String(), nullable=True), sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["approved_by"], ["admin_users.id"], ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "week_start", name="uq_pcp_weekly_plans_tenant_week"))
    op.create_index("ix_pcp_weekly_plans_tenant_status", "pcp_weekly_plans", ["tenant_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_pcp_weekly_plans_tenant_status", table_name="pcp_weekly_plans")
    op.drop_table("pcp_weekly_plans")

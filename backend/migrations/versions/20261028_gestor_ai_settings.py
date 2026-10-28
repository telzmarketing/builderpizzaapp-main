"""Add tenant-scoped Gestor IA configuration without credentials."""
from alembic import op
import sqlalchemy as sa

revision = "20261028_gestor_ai_settings"
down_revision = "20261028_gestor_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gestor_ai_settings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("provider", sa.String(length=20), nullable=False, server_default="internal"),
        sa.Column("model", sa.String(length=120), nullable=False, server_default="internal-rules-v1"),
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0.2"),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="800"),
        sa.Column("system_instructions", sa.Text(), nullable=False, server_default=""),
        sa.Column("operational_rules", sa.Text(), nullable=False, server_default=""),
        sa.Column("monthly_token_limit", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("monthly_cost_limit", sa.Float(), nullable=False, server_default="0"),
        sa.Column("writes_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_gestor_ai_settings_tenant"),
    )
    op.create_index("ix_gestor_ai_settings_tenant", "gestor_ai_settings", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_gestor_ai_settings_tenant", table_name="gestor_ai_settings")
    op.drop_table("gestor_ai_settings")

"""Add one tenant-scoped credential shared by AI modules."""

from alembic import op
import sqlalchemy as sa


revision = "20261112_tenant_ai_credentials"
down_revision = "20261112_print_order_imports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_ai_credentials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("api_key", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_ai_credentials_tenant"),
        sa.CheckConstraint("provider IN ('openai','claude')", name="ck_tenant_ai_credentials_provider"),
    )
    op.create_index("ix_tenant_ai_credentials_tenant", "tenant_ai_credentials", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_tenant_ai_credentials_tenant", table_name="tenant_ai_credentials")
    op.drop_table("tenant_ai_credentials")

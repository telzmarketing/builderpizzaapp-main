"""Persist structured, tenant-scoped commercial customer memory."""
from alembic import op
import sqlalchemy as sa


revision = "20261029_customer_commercial_memory"
down_revision = "20261029_inventory_receipt_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_commercial_memory",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=False),
        sa.Column("memory_key", sa.String(length=160), nullable=False),
        sa.Column("memory_type", sa.String(length=40), nullable=False, server_default="preference"),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="crm"),
        sa.Column("confidence", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_customer_commercial_memory_tenant", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name="fk_customer_commercial_memory_customer", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "customer_id", "memory_key", name="uq_customer_commercial_memory_key"),
    )
    op.create_index("ix_customer_commercial_memory_tenant_customer", "customer_commercial_memory", ["tenant_id", "customer_id"])
    op.create_index("ix_customer_commercial_memory_active", "customer_commercial_memory", ["tenant_id", "active"])


def downgrade() -> None:
    op.drop_index("ix_customer_commercial_memory_active", table_name="customer_commercial_memory")
    op.drop_index("ix_customer_commercial_memory_tenant_customer", table_name="customer_commercial_memory")
    op.drop_table("customer_commercial_memory")

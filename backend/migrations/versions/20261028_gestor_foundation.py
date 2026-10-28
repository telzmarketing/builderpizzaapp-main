"""Create the tenant-scoped Gestor administrative foundation."""
from alembic import op
import sqlalchemy as sa


revision = "20261028_gestor_foundation"
down_revision = "20261028_product_category_capabilities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gestor_authorized_contacts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("admin_user_id", sa.String(), nullable=False),
        sa.Column("phone_normalized", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("requires_reauth", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admin_users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "admin_user_id"],
            ["tenant_memberships.tenant_id", "tenant_memberships.user_id"],
            name="fk_gestor_contacts_tenant_admin_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "phone_normalized", name="uq_gestor_contacts_tenant_phone"),
    )
    op.create_index("ix_gestor_contacts_tenant_active", "gestor_authorized_contacts", ["tenant_id", "active"])

    op.create_table(
        "gestor_operations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("requested_by_admin_id", sa.String(), nullable=True),
        sa.Column("channel", sa.String(length=40), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("tool_name", sa.String(length=120), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING_CONFIRMATION"),
        sa.Column("arguments_json", sa.JSON(), nullable=False),
        sa.Column("preview_json", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("confirmation_token_hash", sa.String(length=128), nullable=True),
        sa.Column("confirmation_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_admin_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_gestor_operations_tenant_idempotency"),
    )
    op.create_index("ix_gestor_operations_tenant_status_created", "gestor_operations", ["tenant_id", "status", "created_at"])
    op.create_index("ix_gestor_operations_tenant_created", "gestor_operations", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_gestor_operations_tenant_created", table_name="gestor_operations")
    op.drop_index("ix_gestor_operations_tenant_status_created", table_name="gestor_operations")
    op.drop_table("gestor_operations")
    op.drop_index("ix_gestor_contacts_tenant_active", table_name="gestor_authorized_contacts")
    op.drop_table("gestor_authorized_contacts")

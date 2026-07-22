"""Add the multi-tenant foundation tables.

Revision ID: 20260721_multi_tenant_foundation
Revises: 20260704_campaign_contact_lists
Create Date: 2026-07-21

This additive migration intentionally does not tenantize existing business tables
and does not seed or backfill the legacy tenant.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260721_multi_tenant_foundation"
down_revision = "20260704_campaign_contact_lists"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("tenants",
        sa.Column("id", sa.String(), nullable=False), sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False), sa.Column("legal_name", sa.String(250)),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("timezone", sa.String(80), nullable=False, server_default="America/Sao_Paulo"),
        sa.Column("locale", sa.String(20), nullable=False, server_default="pt-BR"),
        sa.Column("is_legacy", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)), sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('active', 'suspended', 'disabled')", name="ck_tenants_status"))
    op.create_index("uq_tenants_slug_lower", "tenants", [sa.text("lower(slug)")], unique=True)
    op.create_index("ix_tenants_status", "tenants", ["status"])
    op.create_index("uq_tenants_single_legacy", "tenants", ["is_legacy"], unique=True, postgresql_where=sa.text("is_legacy = true AND deleted_at IS NULL"))

    op.create_table("tenant_memberships",
        sa.Column("id", sa.String(), nullable=False), sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False), sa.Column("role", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("invited_by", sa.String()), sa.Column("joined_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["admin_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["admin_users.id"], ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_tenant_memberships_tenant_user"),
        sa.CheckConstraint("role IN ('owner', 'admin', 'manager', 'operator', 'viewer')", name="ck_tenant_memberships_role"),
        sa.CheckConstraint("status IN ('active', 'invited', 'suspended', 'revoked')", name="ck_tenant_memberships_status"))
    op.create_index("ix_tenant_memberships_user_status", "tenant_memberships", ["user_id", "status"])
    op.create_index("ix_tenant_memberships_tenant_status", "tenant_memberships", ["tenant_id", "status"])
    op.create_index("uq_tenant_memberships_default_active_user", "tenant_memberships", ["user_id"], unique=True, postgresql_where=sa.text("is_default = true AND status = 'active'"))

    op.create_table("platform_roles", sa.Column("id", sa.String(), primary_key=True), sa.Column("key", sa.String(50), nullable=False, unique=True), sa.Column("name", sa.String(100), nullable=False), sa.Column("description", sa.Text()), sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_platform_roles_key", "platform_roles", ["key"])
    op.create_table("platform_permissions", sa.Column("id", sa.String(), primary_key=True), sa.Column("key", sa.String(100), nullable=False, unique=True), sa.Column("name", sa.String(100), nullable=False), sa.Column("description", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_platform_permissions_key", "platform_permissions", ["key"])
    op.create_table("platform_role_permissions", sa.Column("id", sa.String(), primary_key=True), sa.Column("role_id", sa.String(), sa.ForeignKey("platform_roles.id", ondelete="CASCADE"), nullable=False), sa.Column("permission_id", sa.String(), sa.ForeignKey("platform_permissions.id", ondelete="CASCADE"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("role_id", "permission_id", name="uq_platform_role_permissions_role_permission"))
    op.create_index("ix_platform_role_permissions_role_id", "platform_role_permissions", ["role_id"])
    op.create_index("ix_platform_role_permissions_permission_id", "platform_role_permissions", ["permission_id"])
    op.create_table("platform_user_roles", sa.Column("id", sa.String(), primary_key=True), sa.Column("user_id", sa.String(), sa.ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False), sa.Column("role_id", sa.String(), sa.ForeignKey("platform_roles.id", ondelete="CASCADE"), nullable=False), sa.Column("granted_by", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("user_id", "role_id", name="uq_platform_user_roles_user_role"))
    op.create_index("ix_platform_user_roles_user_id", "platform_user_roles", ["user_id"])
    op.create_index("ix_platform_user_roles_role_id", "platform_user_roles", ["role_id"])

    op.create_table("platform_audit_logs", sa.Column("id", sa.String(), primary_key=True), sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="SET NULL")), sa.Column("actor_user_id", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL")), sa.Column("actor_label", sa.String(200), nullable=False), sa.Column("actor_role", sa.String(50)), sa.Column("action", sa.String(100), nullable=False), sa.Column("resource_type", sa.String(100)), sa.Column("resource_id", sa.String(100)), sa.Column("request_id", sa.String(100)), sa.Column("correlation_id", sa.String(100)), sa.Column("ip_address", sa.String(50)), sa.Column("user_agent", sa.Text()), sa.Column("metadata_json", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_platform_audit_logs_tenant_created", "platform_audit_logs", ["tenant_id", "created_at"])
    op.create_index("ix_platform_audit_logs_actor_created", "platform_audit_logs", ["actor_user_id", "created_at"])
    op.create_index("ix_platform_audit_logs_resource", "platform_audit_logs", ["resource_type", "resource_id"])
    op.create_index("ix_platform_audit_logs_request_id", "platform_audit_logs", ["request_id"])
    op.create_index("ix_platform_audit_logs_correlation_id", "platform_audit_logs", ["correlation_id"])


def downgrade() -> None:
    op.drop_table("platform_audit_logs")
    op.drop_table("platform_user_roles")
    op.drop_table("platform_role_permissions")
    op.drop_table("platform_permissions")
    op.drop_table("platform_roles")
    op.drop_table("tenant_memberships")
    op.drop_table("tenants")

"""tenant public domain foundation

Revision ID: 20260725_tenant_domains
Revises: 20260724_tenant_catalog_backfill
"""
from alembic import op
import sqlalchemy as sa

revision = "20260725_tenant_domains"
down_revision = "20260724_tenant_catalog_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_domains",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("hostname", sa.String(length=253), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("verification_token_hash", sa.String(length=64), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("kind IN ('subdomain', 'custom')", name="ck_tenant_domains_kind"),
        sa.CheckConstraint("status IN ('pending', 'verified', 'active')", name="ck_tenant_domains_status"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_tenant_domains_hostname_lower", "tenant_domains", [sa.text("lower(hostname)")], unique=True)
    op.create_index("ix_tenant_domains_tenant_status", "tenant_domains", ["tenant_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tenant_domains_tenant_status", table_name="tenant_domains")
    op.drop_index("uq_tenant_domains_hostname_lower", table_name="tenant_domains")
    op.drop_table("tenant_domains")

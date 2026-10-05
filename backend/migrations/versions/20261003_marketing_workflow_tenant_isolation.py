"""Tenant-scope marketing approval workflows and comments.

Revision ID: 20261003_marketing_workflow_tenant_isolation
Revises: 20261002_marketing_workflow_foundation
"""
from alembic import op
import sqlalchemy as sa


revision = "20261003_marketing_workflow_tenant_isolation"
down_revision = "20261002_marketing_workflow_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for table in ("marketing_workflows", "marketing_workflow_comments"):
        op.add_column(table, sa.Column("tenant_id", sa.String(), nullable=True))

    # Existing workflow rows belong to the seeded legacy company.  This is an
    # explicit, auditable backfill; no row is silently made visible to every
    # tenant.
    bind.execute(sa.text(
        "UPDATE marketing_workflows SET tenant_id='tenant-legacy-default' "
        "WHERE tenant_id IS NULL"
    ))
    bind.execute(sa.text(
        "UPDATE marketing_workflow_comments c SET tenant_id=w.tenant_id "
        "FROM marketing_workflows w "
        "WHERE c.workflow_id=w.id AND c.tenant_id IS NULL"
    ))
    missing = bind.execute(sa.text(
        "SELECT 1 FROM marketing_workflows w LEFT JOIN tenants t ON t.id=w.tenant_id "
        "WHERE w.tenant_id IS NULL OR t.id IS NULL OR t.deleted_at IS NOT NULL LIMIT 1"
    )).scalar()
    if missing:
        raise RuntimeError("Contract gate failed for marketing_workflows: invalid tenant ownership")
    missing = bind.execute(sa.text(
        "SELECT 1 FROM marketing_workflow_comments c LEFT JOIN tenants t ON t.id=c.tenant_id "
        "WHERE c.tenant_id IS NULL OR t.id IS NULL OR t.deleted_at IS NOT NULL LIMIT 1"
    )).scalar()
    if missing:
        raise RuntimeError("Contract gate failed for marketing_workflow_comments: invalid tenant ownership")

    op.create_foreign_key(
        "fk_marketing_workflows_tenant_id_tenants", "marketing_workflows",
        "tenants", ["tenant_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        "fk_marketing_workflow_comments_tenant_id_tenants", "marketing_workflow_comments",
        "tenants", ["tenant_id"], ["id"], ondelete="RESTRICT"
    )
    op.alter_column("marketing_workflows", "tenant_id", existing_type=sa.String(), nullable=False)
    op.alter_column("marketing_workflow_comments", "tenant_id", existing_type=sa.String(), nullable=False)
    op.create_index("ix_marketing_workflows_tenant_created", "marketing_workflows", ["tenant_id", "created_at"])
    op.create_index("ix_marketing_workflow_comments_tenant_workflow", "marketing_workflow_comments", ["tenant_id", "workflow_id"])


def downgrade() -> None:
    op.drop_index("ix_marketing_workflow_comments_tenant_workflow", table_name="marketing_workflow_comments")
    op.drop_index("ix_marketing_workflows_tenant_created", table_name="marketing_workflows")
    op.drop_constraint("fk_marketing_workflow_comments_tenant_id_tenants", "marketing_workflow_comments", type_="foreignkey")
    op.drop_constraint("fk_marketing_workflows_tenant_id_tenants", "marketing_workflows", type_="foreignkey")
    op.drop_column("marketing_workflow_comments", "tenant_id")
    op.drop_column("marketing_workflows", "tenant_id")

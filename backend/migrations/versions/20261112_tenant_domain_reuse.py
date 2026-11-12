"""Allow reuse of hostnames whose previous binding was removed.

Removed tenant-domain rows remain as immutable lifecycle history.  The active
hostname registry must only exclude concurrent non-removed bindings.
"""

from alembic import op
import sqlalchemy as sa


revision = "20261112_tenant_domain_reuse"
down_revision = "20261112_finance_budgets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("uq_tenant_domains_hostname_lower", table_name="tenant_domains")
    op.create_index(
        "uq_tenant_domains_hostname_lower",
        "tenant_domains",
        [sa.text("lower(hostname)")],
        unique=True,
        postgresql_where=sa.text("status <> 'removed'"),
    )


def downgrade() -> None:
    op.drop_index("uq_tenant_domains_hostname_lower", table_name="tenant_domains")
    op.create_index(
        "uq_tenant_domains_hostname_lower",
        "tenant_domains",
        [sa.text("lower(hostname)")],
        unique=True,
    )

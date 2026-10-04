"""Remove the global Email Marketing configuration identifier default.

Revision ID: 20261003_email_marketing_tenant_config
Revises: 20261003_whatsapp_meta_webhook_tenant_keys
"""
from alembic import op
import sqlalchemy as sa


revision = "20261003_email_marketing_tenant_config"
down_revision = "20261003_whatsapp_meta_webhook_tenant_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    duplicates = bind.execute(sa.text("""
        SELECT tenant_id
        FROM email_config
        WHERE tenant_id IS NOT NULL
        GROUP BY tenant_id
        HAVING COUNT(*) > 1
    """)).scalar()
    if duplicates:
        raise RuntimeError("email_config possui mais de uma configuracao para a mesma empresa")
    op.execute("ALTER TABLE email_config ALTER COLUMN id DROP DEFAULT")


def downgrade() -> None:
    # Do not restore a global singleton default after tenant-specific configs exist.
    pass

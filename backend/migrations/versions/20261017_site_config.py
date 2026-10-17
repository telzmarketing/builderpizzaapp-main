"""Restore the existing singleton site configuration without replacing its data.

This table was previously created only by the optional startup bootstrap.
Keep its legacy schema and public API contract; tenant branding is outside
this repair. Existing installations may already contain customized content.
"""
from alembic import op


revision = "20261017_site_config"
down_revision = "20261014_tenant_domain_ssl"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE TABLE IF NOT EXISTS site_config ("
        "id VARCHAR PRIMARY KEY DEFAULT 'default', "
        "content TEXT NOT NULL DEFAULT '{}', "
        "updated_at TIMESTAMPTZ DEFAULT NOW())"
    )
    op.execute(
        "INSERT INTO site_config (id, content) VALUES ('default', '{}') "
        "ON CONFLICT (id) DO NOTHING"
    )


def downgrade():
    raise RuntimeError(
        "Site configuration is forward-only; existing branding and settings must be preserved."
    )

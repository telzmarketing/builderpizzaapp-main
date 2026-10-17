"""Restore delivery runtime columns omitted from migrations.

These fields already belong to the delivery domain and were previously added
only by the optional startup bootstrap. Do not create credentials or replace
any existing hashes, documents, payment keys or delivery confirmations.
"""
from alembic import op


revision = "20261017_delivery_schema"
down_revision = "20261017_site_config"
branch_labels = None
depends_on = None


def upgrade():
    for definition in (
        "password_hash TEXT",
        "cpf VARCHAR(14)",
        "cnh VARCHAR(20)",
        "pix_key VARCHAR(200)",
    ):
        op.execute(f"ALTER TABLE delivery_persons ADD COLUMN IF NOT EXISTS {definition}")
    op.execute("ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS confirmation_code VARCHAR(4)")
    op.execute("ALTER TABLE deliveries ADD COLUMN IF NOT EXISTS confirmed_by_code_at TIMESTAMPTZ")
    op.execute("ALTER TABLE logistics_settings ADD COLUMN IF NOT EXISTS rate_per_delivery FLOAT DEFAULT 0.0")


def downgrade():
    raise RuntimeError(
        "Delivery schema is forward-only; credentials, documents and confirmations must be preserved."
    )

"""Add tenant-scoped Pagar.me gateway configuration.

Revision ID: 20260923_pagarme_tenant_gateway
Revises: 20260922_tenant_gateway_configuration
"""
from alembic import op
import sqlalchemy as sa


revision = "20260923_pagarme_tenant_gateway"
down_revision = "20260922_tenant_gateway_configuration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = "payment_gateway_config"
    op.add_column(table, sa.Column("pagarme_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column(table, sa.Column("pagarme_environment", sa.String(20), nullable=False, server_default="sandbox"))
    op.add_column(table, sa.Column("pagarme_public_key", sa.String(300), nullable=True))
    op.add_column(table, sa.Column("pagarme_secret_key", sa.String(500), nullable=True))
    op.add_column(table, sa.Column("pagarme_webhook_secret", sa.String(500), nullable=True))
    op.add_column(table, sa.Column("pagarme_pix_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column(table, sa.Column("pagarme_credit_card_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column(table, sa.Column("pagarme_max_installments", sa.Integer(), nullable=False, server_default="1"))
    op.add_column(table, sa.Column("pagarme_last_health_check_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("pagarme_last_health_check_status", sa.String(30), nullable=False, server_default="not_tested"))
    op.add_column(table, sa.Column("pagarme_last_health_check_message", sa.Text(), nullable=True))


def downgrade() -> None:
    table = "payment_gateway_config"
    for column in (
        "pagarme_last_health_check_message", "pagarme_last_health_check_status",
        "pagarme_last_health_check_at", "pagarme_max_installments",
        "pagarme_credit_card_enabled", "pagarme_pix_enabled",
        "pagarme_webhook_secret", "pagarme_secret_key", "pagarme_public_key",
        "pagarme_environment", "pagarme_enabled",
    ):
        op.drop_column(table, column)

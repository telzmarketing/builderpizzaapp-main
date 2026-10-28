"""Add the isolated official Meta channel for Gestor WhatsApp."""
from alembic import op
import sqlalchemy as sa


revision = "20261028_gestor_whatsapp_channel"
down_revision = "20261028_gestor_ai_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gestor_whatsapp_channels",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("phone_number_id", sa.String(length=120), nullable=False),
        sa.Column("business_account_id", sa.String(length=120), nullable=False),
        sa.Column("display_phone_number", sa.String(length=40), nullable=True),
        sa.Column("verify_token_hash", sa.String(length=128), nullable=False),
        sa.Column("app_secret_ref", sa.String(length=200), nullable=False),
        sa.Column("integration_connection_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending_secret"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["integration_connection_id"], ["integration_connections.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("phone_number_id", name="uq_gestor_whatsapp_phone_number_id"),
        sa.UniqueConstraint("tenant_id", name="uq_gestor_whatsapp_tenant_channel"),
    )
    op.create_index(
        "ix_gestor_whatsapp_channels_tenant_status",
        "gestor_whatsapp_channels", ["tenant_id", "status"],
    )

    op.create_table(
        "gestor_whatsapp_messages",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("channel_id", sa.String(), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=False),
        sa.Column("from_phone", sa.String(length=32), nullable=False),
        sa.Column("message_type", sa.String(length=40), nullable=False),
        sa.Column("text_body", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="RECEIVED"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_id"], ["gestor_whatsapp_channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "provider_message_id", name="uq_gestor_whatsapp_message_provider"),
    )
    op.create_index(
        "ix_gestor_whatsapp_messages_channel_status",
        "gestor_whatsapp_messages", ["channel_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_gestor_whatsapp_messages_channel_status", table_name="gestor_whatsapp_messages")
    op.drop_table("gestor_whatsapp_messages")
    op.drop_index("ix_gestor_whatsapp_channels_tenant_status", table_name="gestor_whatsapp_channels")
    op.drop_table("gestor_whatsapp_channels")

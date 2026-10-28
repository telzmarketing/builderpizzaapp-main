"""Add the isolated asynchronous outbound queue for Gestor Meta WhatsApp."""
from alembic import op
import sqlalchemy as sa


revision = "20261028_gestor_whatsapp_outbox"
down_revision = "20261028_gestor_whatsapp_channel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "gestor_whatsapp_channels",
        sa.Column("access_token_ref", sa.String(length=200), nullable=True),
    )
    op.create_table(
        "gestor_whatsapp_outbox",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("channel_id", sa.String(), nullable=False),
        sa.Column("operation_id", sa.String(), nullable=False),
        sa.Column("recipient_phone", sa.String(length=32), nullable=False),
        sa.Column("message_type", sa.String(length=20), nullable=False, server_default="text"),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("template_name", sa.String(length=200), nullable=True),
        sa.Column("template_language", sa.String(length=20), nullable=True),
        sa.Column("template_variables", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_id"], ["gestor_whatsapp_channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["operation_id"], ["gestor_operations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "operation_id", name="uq_gestor_whatsapp_outbox_operation"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_gestor_whatsapp_outbox_idempotency"),
    )
    op.create_index(
        "ix_gestor_whatsapp_outbox_tenant_status_due",
        "gestor_whatsapp_outbox", ["tenant_id", "status", "next_attempt_at"],
    )
    op.create_index(
        "ix_gestor_whatsapp_outbox_channel_created",
        "gestor_whatsapp_outbox", ["channel_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_gestor_whatsapp_outbox_channel_created", table_name="gestor_whatsapp_outbox")
    op.drop_index("ix_gestor_whatsapp_outbox_tenant_status_due", table_name="gestor_whatsapp_outbox")
    op.drop_table("gestor_whatsapp_outbox")
    op.drop_column("gestor_whatsapp_channels", "access_token_ref")

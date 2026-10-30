"""Add an optional tenant-scoped Gateway transport selection to Gestor."""
from alembic import op
import sqlalchemy as sa


revision = "20261028_gestor_gateway_instance"
down_revision = "20261028_gestor_automations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "gestor_whatsapp_channels",
        sa.Column("whatsapp_gateway_instance_id", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        "fk_gestor_whatsapp_channel_gateway_instance",
        "gestor_whatsapp_channels",
        "whatsapp_gateway_instances",
        ["whatsapp_gateway_instance_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_gestor_whatsapp_channels_gateway_instance",
        "gestor_whatsapp_channels",
        ["tenant_id", "whatsapp_gateway_instance_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_gestor_whatsapp_channels_gateway_instance", table_name="gestor_whatsapp_channels")
    op.drop_constraint("fk_gestor_whatsapp_channel_gateway_instance", "gestor_whatsapp_channels", type_="foreignkey")
    op.drop_column("gestor_whatsapp_channels", "whatsapp_gateway_instance_id")

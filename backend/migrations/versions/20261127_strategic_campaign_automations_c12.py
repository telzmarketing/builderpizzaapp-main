"""C12: campaign-scoped WhatsApp automation definitions."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261127_strategic_campaign_automations_c12"
down_revision = "20261126_strategic_campaigns_c11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategic_campaign_automations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("automation_key", sa.String(80), nullable=False),
        sa.Column("event_key", sa.String(120), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False, server_default="whatsapp"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("definition", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("generated_from", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "campaign_id"],
            ["strategic_campaigns.tenant_id", "strategic_campaigns.id"],
            name="fk_strategic_campaign_automations_campaign",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tenant_id", "campaign_id", "automation_key", name="uq_strategic_campaign_automations_key"),
        sa.CheckConstraint("channel = 'whatsapp'", name="ck_strategic_campaign_automations_channel"),
    )
    op.create_index(
        "ix_strategic_campaign_automations_tenant_campaign",
        "strategic_campaign_automations",
        ["tenant_id", "campaign_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_strategic_campaign_automations_tenant_campaign", table_name="strategic_campaign_automations")
    op.drop_table("strategic_campaign_automations")

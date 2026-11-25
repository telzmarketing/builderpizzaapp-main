"""Create the phase 1 strategic campaign contract."""

from alembic import op
import sqlalchemy as sa


revision = "20261125_strategic_campaigns_phase1"
down_revision = "20261125_schema_index_repairs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(
        """
        DO $$
        BEGIN
            CREATE TYPE strategiccampaignstatus AS ENUM ('draft', 'scheduled', 'active', 'paused', 'sold_out', 'ended', 'archived');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
        """
    ))
    campaign_status = sa.Enum("draft", "scheduled", "active", "paused", "sold_out", "ended", "archived", name="strategiccampaignstatus", create_type=False)
    op.create_table(
        "strategic_campaigns",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("commercial_name", sa.String(200)),
        sa.Column("slug", sa.String(180), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", campaign_status, nullable=False, server_default="draft"),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("ends_at", sa.DateTime(timezone=True)),
        sa.Column("published_version", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_strategic_campaigns_tenant_slug"),
    )
    op.create_index("ix_strategic_campaigns_tenant_status", "strategic_campaigns", ["tenant_id", "status"])
    op.create_table(
        "strategic_offers",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("strategic_campaigns.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.id", ondelete="RESTRICT")),
        sa.Column("kit_id", sa.String(), sa.ForeignKey("promotional_kits.id", ondelete="RESTRICT")),
        sa.Column("price_original", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("price_promotional", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "campaign_id", "code", name="uq_strategic_offers_tenant_campaign_code"),
    )
    op.create_index("ix_strategic_offers_tenant_campaign", "strategic_offers", ["tenant_id", "campaign_id"])
    op.create_table(
        "strategic_campaign_versions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("campaign_id", sa.String(), sa.ForeignKey("strategic_campaigns.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "campaign_id", "version", name="uq_strategic_campaign_versions_number"),
    )
    op.create_index("ix_strategic_campaign_versions_tenant_campaign", "strategic_campaign_versions", ["tenant_id", "campaign_id"])
    op.add_column("orders", sa.Column("strategic_campaign_id", sa.String(), sa.ForeignKey("strategic_campaigns.id", ondelete="SET NULL"), nullable=True))
    op.add_column("orders", sa.Column("strategic_offer_id", sa.String(), sa.ForeignKey("strategic_offers.id", ondelete="SET NULL"), nullable=True))
    op.add_column("orders", sa.Column("strategic_offer_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "strategic_offer_snapshot")
    op.drop_column("orders", "strategic_offer_id")
    op.drop_column("orders", "strategic_campaign_id")
    op.drop_index("ix_strategic_campaign_versions_tenant_campaign", table_name="strategic_campaign_versions")
    op.drop_table("strategic_campaign_versions")
    op.drop_index("ix_strategic_offers_tenant_campaign", table_name="strategic_offers")
    op.drop_table("strategic_offers")
    op.drop_index("ix_strategic_campaigns_tenant_status", table_name="strategic_campaigns")
    op.drop_table("strategic_campaigns")
    sa.Enum(name="strategiccampaignstatus").drop(op.get_bind(), checkfirst=True)

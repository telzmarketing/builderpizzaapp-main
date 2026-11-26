"""Add soft archive support to strategic campaign offers."""

from alembic import op
import sqlalchemy as sa


revision = "20261125_strategic_offer_archive_c2"
down_revision = "20261125_strategic_campaign_marketing_phase7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("strategic_offers", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_strategic_offers_tenant_campaign_archived",
        "strategic_offers",
        ["tenant_id", "campaign_id", "archived_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_strategic_offers_tenant_campaign_archived", table_name="strategic_offers")
    op.drop_column("strategic_offers", "archived_at")

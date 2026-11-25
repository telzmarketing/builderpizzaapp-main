"""Add commercial presentation and availability fields to strategic offers."""

from alembic import op
import sqlalchemy as sa


revision = "20261125_strategic_campaign_offers_phase2"
down_revision = "20261125_strategic_campaigns_phase1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("strategic_offers", sa.Column("quantity_limit", sa.Integer()))
    op.add_column("strategic_offers", sa.Column("max_per_customer", sa.Integer()))
    op.add_column("strategic_offers", sa.Column("sales_starts_at", sa.DateTime(timezone=True)))
    op.add_column("strategic_offers", sa.Column("sales_ends_at", sa.DateTime(timezone=True)))
    op.add_column("strategic_offers", sa.Column("show_when_sold_out", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("strategic_offers", sa.Column("button_text", sa.String(120)))
    op.add_column("strategic_offers", sa.Column("image_desktop_url", sa.Text()))
    op.add_column("strategic_offers", sa.Column("image_mobile_url", sa.Text()))
    op.add_column("strategic_offers", sa.Column("badge_text", sa.String(80)))
    op.add_column("strategic_offers", sa.Column("highlighted", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    for column in ("highlighted", "badge_text", "image_mobile_url", "image_desktop_url", "button_text", "show_when_sold_out", "sales_ends_at", "sales_starts_at", "max_per_customer", "quantity_limit"):
        op.drop_column("strategic_offers", column)

"""Add guarded commercialization settings to strategic campaigns."""

from alembic import op
import sqlalchemy as sa


revision = "20261125_strategic_campaign_commercial_phase5"
down_revision = "20261125_strategic_campaign_visual_phase3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("strategic_campaigns", sa.Column("commercial_config", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("strategic_campaigns", "commercial_config")

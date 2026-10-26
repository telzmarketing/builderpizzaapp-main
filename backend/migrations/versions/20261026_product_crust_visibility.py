"""Add an explicit product flag for showing crust options."""

from alembic import op
import sqlalchemy as sa


revision = "20261026_product_crust_visibility"
down_revision = "20261026_pcp_weekly_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("show_crust_options", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("products", "show_crust_options")

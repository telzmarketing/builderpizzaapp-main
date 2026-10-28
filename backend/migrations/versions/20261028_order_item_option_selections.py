"""Persist the validated customer option selections on order items."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261028_order_item_option_selections"
down_revision = "20261028_product_option_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_items",
        sa.Column("option_selections", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.create_check_constraint(
        "ck_order_items_option_selections_array",
        "order_items",
        "jsonb_typeof(option_selections) = 'array'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_order_items_option_selections_array", "order_items", type="check")
    op.drop_column("order_items", "option_selections")

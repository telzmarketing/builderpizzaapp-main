"""Persist the authenticated operator that creates a manual order."""
from alembic import op
import sqlalchemy as sa


revision = "20261026_manual_order_actor_audit"
down_revision = "20261026_kds_stock_gate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("created_by_admin_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "fk_orders_created_by_admin_id_admin_users",
        "orders",
        "admin_users",
        ["created_by_admin_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_orders_created_by_admin_id_admin_users", "orders", type_="foreignkey")
    op.drop_column("orders", "created_by_admin_id")

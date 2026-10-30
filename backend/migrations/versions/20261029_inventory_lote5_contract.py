"""Add auditable replenishment metadata to canonical inventory purchases.

Forward-only. Existing purchases remain unchanged; requests are non-confirmed
purchase records and do not create stock movements.
"""
from alembic import op
import sqlalchemy as sa

revision = "20261029_inventory_lote5_contract"
down_revision = "20261029_delivery_item_qr_confirmations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inventory_purchases", sa.Column("source", sa.String(length=40), nullable=True))
    op.add_column("inventory_purchases", sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("inventory_purchases", sa.Column("requested_by_admin_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "fk_inventory_purchases_requested_by_admin",
        "inventory_purchases", "admin_users", ["requested_by_admin_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_inventory_purchases_tenant_source_status", "inventory_purchases", ["tenant_id", "source", "status"])


def downgrade() -> None:
    op.drop_index("ix_inventory_purchases_tenant_source_status", table_name="inventory_purchases")
    op.drop_constraint("fk_inventory_purchases_requested_by_admin", "inventory_purchases", type_="foreignkey")
    op.drop_column("inventory_purchases", "requested_by_admin_id")
    op.drop_column("inventory_purchases", "requested_at")
    op.drop_column("inventory_purchases", "source")

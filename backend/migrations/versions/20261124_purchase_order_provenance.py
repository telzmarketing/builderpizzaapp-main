"""Add quotation provenance and optimistic versioning to canonical inventory purchases."""
from alembic import op
import sqlalchemy as sa

revision = "20261124_purchase_order_provenance"
down_revision = "20261124_purchase_quotation_foundation"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("inventory_purchases", sa.Column("quotation_id", sa.String(36), nullable=True))
    op.add_column("inventory_purchases", sa.Column("requisition_id", sa.String(36), nullable=True))
    op.add_column("inventory_purchases", sa.Column("award_snapshot", sa.JSON(), nullable=True))
    op.add_column("inventory_purchases", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("inventory_purchases", sa.Column("approved_by_admin_id", sa.String(), nullable=True))
    op.create_foreign_key("fk_inventory_purchases_quotation", "inventory_purchases", "purchase_quotations", ["tenant_id", "quotation_id"], ["tenant_id", "id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_inventory_purchases_approved_by", "inventory_purchases", "admin_users", ["approved_by_admin_id"], ["id"], ondelete="SET NULL")
    op.create_check_constraint("ck_inventory_purchase_version", "inventory_purchases", "version > 0")
    op.add_column("inventory_purchase_items", sa.Column("quotation_offer_id", sa.String(36), nullable=True))
    op.create_foreign_key("fk_inventory_purchase_items_offer", "inventory_purchase_items", "purchase_quotation_offers", ["tenant_id", "quotation_offer_id"], ["tenant_id", "id"], ondelete="RESTRICT")
    op.create_index("uq_inventory_purchase_items_tenant_offer", "inventory_purchase_items", ["tenant_id", "quotation_offer_id"], unique=True)

def downgrade() -> None:
    op.drop_index("uq_inventory_purchase_items_tenant_offer", table_name="inventory_purchase_items")
    op.drop_constraint("fk_inventory_purchase_items_offer", "inventory_purchase_items", type_="foreignkey")
    op.drop_column("inventory_purchase_items", "quotation_offer_id")
    op.drop_constraint("ck_inventory_purchase_version", "inventory_purchases", type_="check")
    op.drop_constraint("fk_inventory_purchases_approved_by", "inventory_purchases", type_="foreignkey")
    op.drop_constraint("fk_inventory_purchases_quotation", "inventory_purchases", type_="foreignkey")
    for name in ("approved_by_admin_id", "version", "award_snapshot", "requisition_id", "quotation_id"):
        op.drop_column("inventory_purchases", name)

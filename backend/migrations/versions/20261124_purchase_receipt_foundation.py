"""Add tenant-scoped physical purchase receipts and stock posting provenance."""
from alembic import op
import sqlalchemy as sa

revision = "20261124_purchase_receipt_foundation"
down_revision = "20261124_purchase_order_provenance"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("purchase_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("purchase_id", sa.String(36), nullable=False), sa.Column("document_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("notes", sa.Text), sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("received_by_admin_id", sa.String, sa.ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id", "purchase_id"], ["inventory_purchases.tenant_id", "inventory_purchases.id"], name="fk_purchase_receipts_purchase", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "document_id"], ["inventory_receipt_documents.tenant_id", "inventory_receipt_documents.id"], name="fk_purchase_receipts_document", ondelete="SET NULL"),
        sa.CheckConstraint("status IN ('draft','submitted','posted','rejected')", name="ck_purchase_receipts_status"),
        sa.CheckConstraint("version > 0", name="ck_purchase_receipts_version"))
    op.create_index("uq_purchase_receipts_tenant_id_id", "purchase_receipts", ["tenant_id", "id"], unique=True)
    op.create_index("ix_purchase_receipts_tenant_status", "purchase_receipts", ["tenant_id", "status"])
    op.create_table("purchase_receipt_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("receipt_id", sa.String(36), nullable=False), sa.Column("purchase_item_id", sa.String(36), nullable=False), sa.Column("item_id", sa.String, nullable=False),
        sa.Column("location_id", sa.String, nullable=False), sa.Column("quantity_received", sa.Numeric(20, 6), nullable=False),
        sa.Column("quantity_rejected", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(20, 8), nullable=False, server_default="0"), sa.Column("lot_code", sa.String(120)),
        sa.Column("manufactured_on", sa.Date), sa.Column("expires_on", sa.Date), sa.Column("temperature_c", sa.Numeric(8, 2)), sa.Column("quality_status", sa.String(20), nullable=False, server_default="accepted"), sa.Column("inspection_notes", sa.Text), sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["tenant_id", "receipt_id"], ["purchase_receipts.tenant_id", "purchase_receipts.id"], name="fk_purchase_receipt_items_receipt", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id", "purchase_item_id"], ["inventory_purchase_items.tenant_id", "inventory_purchase_items.id"], name="fk_purchase_receipt_items_purchase_item", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "item_id"], ["inventory_items.tenant_id", "inventory_items.id"], name="fk_purchase_receipt_items_item", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "location_id"], ["inventory_locations.tenant_id", "inventory_locations.id"], name="fk_purchase_receipt_items_location", ondelete="RESTRICT"),
        sa.CheckConstraint("quantity_received > 0 AND quantity_rejected >= 0 AND quantity_rejected <= quantity_received", name="ck_purchase_receipt_items_quantity"), sa.CheckConstraint("quality_status IN ('accepted','quarantine','rejected')", name="ck_purchase_receipt_items_quality_status"))
    op.create_index("uq_purchase_receipt_items_tenant_id_id", "purchase_receipt_items", ["tenant_id", "id"], unique=True)
    op.create_index("uq_purchase_receipt_items_position", "purchase_receipt_items", ["tenant_id", "receipt_id", "position"], unique=True)

def downgrade() -> None:
    op.drop_index("uq_purchase_receipt_items_position", table_name="purchase_receipt_items")
    op.drop_index("uq_purchase_receipt_items_tenant_id_id", table_name="purchase_receipt_items")
    op.drop_table("purchase_receipt_items")
    op.drop_index("ix_purchase_receipts_tenant_status", table_name="purchase_receipts")
    op.drop_index("uq_purchase_receipts_tenant_id_id", table_name="purchase_receipts")
    op.drop_table("purchase_receipts")

"""Add tenant-scoped purchase quotation foundation."""
from alembic import op
import sqlalchemy as sa

revision = "20261124_purchase_quotation_foundation"
down_revision = "20261124_purchase_requisition_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("purchase_quotations",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requisition_id", sa.String(36), nullable=False), sa.Column("code", sa.String(40), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("response_due", sa.Date), sa.Column("notes", sa.Text), sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_by_admin_id", sa.String, sa.ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False), sa.Column("awarded_supplier_id", sa.String, sa.ForeignKey("inventory_suppliers.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id", "requisition_id"], ["purchase_requisitions.tenant_id", "purchase_requisitions.id"], name="fk_purchase_quotations_requisition", ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_purchase_quotations_tenant_code"), sa.CheckConstraint("status IN ('draft','open','closed','awarded','cancelled')", name="ck_purchase_quotations_status"), sa.CheckConstraint("version > 0", name="ck_purchase_quotations_version"))
    op.create_index("uq_purchase_quotations_tenant_id_id", "purchase_quotations", ["tenant_id", "id"], unique=True)
    op.create_index("ix_purchase_quotations_tenant_status", "purchase_quotations", ["tenant_id", "status"])
    op.create_table("purchase_quotation_suppliers",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False), sa.Column("quotation_id", sa.String(36), nullable=False), sa.Column("supplier_id", sa.String, nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="invited"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id", "quotation_id"], ["purchase_quotations.tenant_id", "purchase_quotations.id"], name="fk_purchase_quotation_suppliers_quotation", ondelete="CASCADE"), sa.ForeignKeyConstraint(["tenant_id", "supplier_id"], ["inventory_suppliers.tenant_id", "inventory_suppliers.id"], name="fk_purchase_quotation_suppliers_supplier", ondelete="RESTRICT"), sa.UniqueConstraint("tenant_id", "quotation_id", "supplier_id", name="uq_purchase_quotation_suppliers_tenant_quotation_supplier"), sa.CheckConstraint("status IN ('invited','responded','declined')", name="ck_purchase_quotation_suppliers_status"))
    op.create_index("uq_purchase_quotation_suppliers_tenant_id_id", "purchase_quotation_suppliers", ["tenant_id", "id"], unique=True)
    op.create_table("purchase_quotation_lines",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False), sa.Column("quotation_id", sa.String(36), nullable=False), sa.Column("item_id", sa.String, nullable=False), sa.Column("unit_id", sa.String, nullable=False), sa.Column("quantity", sa.Numeric(20, 6), nullable=False), sa.Column("position", sa.Integer, nullable=False, server_default="0"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id", "quotation_id"], ["purchase_quotations.tenant_id", "purchase_quotations.id"], name="fk_purchase_quotation_lines_quotation", ondelete="CASCADE"), sa.ForeignKeyConstraint(["tenant_id", "item_id"], ["inventory_items.tenant_id", "inventory_items.id"], name="fk_purchase_quotation_lines_item", ondelete="RESTRICT"), sa.ForeignKeyConstraint(["tenant_id", "unit_id"], ["inventory_units.tenant_id", "inventory_units.id"], name="fk_purchase_quotation_lines_unit", ondelete="RESTRICT"), sa.CheckConstraint("quantity > 0", name="ck_purchase_quotation_lines_quantity"), sa.CheckConstraint("position >= 0", name="ck_purchase_quotation_lines_position"))
    op.create_index("uq_purchase_quotation_lines_tenant_id_id", "purchase_quotation_lines", ["tenant_id", "id"], unique=True)
    op.create_index("uq_purchase_quotation_lines_position", "purchase_quotation_lines", ["tenant_id", "quotation_id", "position"], unique=True)
    op.create_table("purchase_quotation_offers",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False), sa.Column("quotation_id", sa.String(36), nullable=False), sa.Column("quotation_line_id", sa.String(36), nullable=False), sa.Column("supplier_id", sa.String, nullable=False), sa.Column("unit_price", sa.Numeric(20, 8), nullable=False), sa.Column("conversion_factor", sa.Numeric(20, 8), nullable=False, server_default="1"), sa.Column("freight", sa.Numeric(20, 8), nullable=False, server_default="0"), sa.Column("discount", sa.Numeric(20, 8), nullable=False, server_default="0"), sa.Column("payment_terms", sa.String(120)), sa.Column("delivery_days", sa.Integer), sa.Column("valid_until", sa.Date), sa.Column("notes", sa.Text), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id", "quotation_id"], ["purchase_quotations.tenant_id", "purchase_quotations.id"], name="fk_purchase_quotation_offers_quotation", ondelete="CASCADE"), sa.ForeignKeyConstraint(["tenant_id", "quotation_line_id"], ["purchase_quotation_lines.tenant_id", "purchase_quotation_lines.id"], name="fk_purchase_quotation_offers_line", ondelete="CASCADE"), sa.ForeignKeyConstraint(["tenant_id", "supplier_id"], ["inventory_suppliers.tenant_id", "inventory_suppliers.id"], name="fk_purchase_quotation_offers_supplier", ondelete="RESTRICT"), sa.UniqueConstraint("tenant_id", "quotation_line_id", "supplier_id", name="uq_purchase_quotation_offers_line_supplier"), sa.CheckConstraint("unit_price >= 0 AND freight >= 0 AND discount >= 0", name="ck_purchase_quotation_offers_nonnegative"), sa.CheckConstraint("conversion_factor > 0", name="ck_purchase_quotation_offers_conversion"))
    op.create_index("uq_purchase_quotation_offers_tenant_id_id", "purchase_quotation_offers", ["tenant_id", "id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_purchase_quotation_offers_tenant_id_id", table_name="purchase_quotation_offers"); op.drop_table("purchase_quotation_offers")
    op.drop_index("uq_purchase_quotation_lines_position", table_name="purchase_quotation_lines"); op.drop_index("uq_purchase_quotation_lines_tenant_id_id", table_name="purchase_quotation_lines"); op.drop_table("purchase_quotation_lines")
    op.drop_index("uq_purchase_quotation_suppliers_tenant_id_id", table_name="purchase_quotation_suppliers"); op.drop_table("purchase_quotation_suppliers")
    op.drop_index("ix_purchase_quotations_tenant_status", table_name="purchase_quotations"); op.drop_index("uq_purchase_quotations_tenant_id_id", table_name="purchase_quotations"); op.drop_table("purchase_quotations")

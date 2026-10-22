"""Add tenant-owned received fiscal document evidence.

The document is an inbound fiscal artifact for review.  It never creates a
stock movement, payable, or fiscal authorization as a side effect.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261022_inventory_receipt_documents"
down_revision = "20261021_inventory_recipe_details"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "inventory_receipt_documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("purchase_id", sa.String(), nullable=True),
        sa.Column("supplier_id", sa.String(), nullable=True),
        sa.Column("document_model", sa.String(10), nullable=False, server_default="NFe"),
        sa.Column("status", sa.String(30), nullable=False, server_default="uploaded"),
        sa.Column("access_key", sa.String(44), nullable=True),
        sa.Column("series", sa.String(10), nullable=True),
        sa.Column("number", sa.String(20), nullable=True),
        sa.Column("issuer_document", sa.String(20), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=True),
        sa.Column("parser_version", sa.String(40), nullable=False, server_default="stdlib-xml-v1"),
        sa.Column("raw_xml", sa.Text(), nullable=False),
        sa.Column("extracted_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("validation_errors_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "purchase_id"],
            ["inventory_purchases.tenant_id", "inventory_purchases.id"],
            name="fk_inventory_receipt_document_purchase",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "supplier_id"],
            ["inventory_suppliers.tenant_id", "inventory_suppliers.id"],
            name="fk_inventory_receipt_document_supplier",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("status IN ('uploaded','processing','review_required','validated','rejected')", name="ck_inventory_receipt_document_status"),
        sa.CheckConstraint("length(content_sha256) = 64", name="ck_inventory_receipt_document_hash"),
        sa.CheckConstraint("document_model IN ('NFe','NFCe')", name="ck_inventory_receipt_document_model"),
    )
    op.create_index("uq_inventory_receipt_documents_tenant_id_id", "inventory_receipt_documents", ["tenant_id", "id"], unique=True)
    op.create_index("uq_inventory_receipt_documents_tenant_hash", "inventory_receipt_documents", ["tenant_id", "content_sha256"], unique=True)
    op.create_index("uq_inventory_receipt_documents_tenant_access_key", "inventory_receipt_documents", ["tenant_id", "access_key"], unique=True, postgresql_where=sa.text("access_key IS NOT NULL"))
    op.create_index("uq_inventory_receipt_documents_tenant_idempotency", "inventory_receipt_documents", ["tenant_id", "idempotency_key"], unique=True, postgresql_where=sa.text("idempotency_key IS NOT NULL"))
    op.create_index("ix_inventory_receipt_documents_tenant_status", "inventory_receipt_documents", ["tenant_id", "status"])

    op.create_table(
        "inventory_receipt_document_lines",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("supplier_code", sa.String(80), nullable=True),
        sa.Column("gtin", sa.String(20), nullable=True),
        sa.Column("description", sa.String(220), nullable=False),
        sa.Column("quantity", sa.Numeric(20, 6), nullable=False),
        sa.Column("commercial_unit", sa.String(20), nullable=True),
        sa.Column("unit_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("total_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("inventory_item_id", sa.String(), nullable=True),
        sa.Column("association_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("extracted_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["inventory_receipt_documents.tenant_id", "inventory_receipt_documents.id"],
            name="fk_inventory_receipt_document_line_document",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "inventory_item_id"],
            ["inventory_items.tenant_id", "inventory_items.id"],
            name="fk_inventory_receipt_document_line_item",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("line_number > 0", name="ck_inventory_receipt_document_line_number"),
        sa.CheckConstraint("quantity > 0 AND CAST(quantity AS VARCHAR) <> 'NaN'", name="ck_inventory_receipt_document_line_quantity"),
        sa.CheckConstraint("association_status IN ('pending','matched','ignored')", name="ck_inventory_receipt_document_line_association"),
    )
    op.create_index("uq_inventory_receipt_document_lines_tenant_id_id", "inventory_receipt_document_lines", ["tenant_id", "id"], unique=True)
    op.create_index("uq_inventory_receipt_document_lines_document_line", "inventory_receipt_document_lines", ["tenant_id", "document_id", "line_number"], unique=True)
    op.create_index("ix_inventory_receipt_document_lines_document_id", "inventory_receipt_document_lines", ["document_id"])
    op.create_index("ix_inventory_receipt_document_lines_inventory_item_id", "inventory_receipt_document_lines", ["inventory_item_id"])


def downgrade():
    raise RuntimeError("Forward-only: received fiscal evidence is an audit record.")

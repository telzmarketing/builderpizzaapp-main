"""Allow tenant-owned PDF and camera evidence for inbound receipts."""
from alembic import op
import sqlalchemy as sa

revision = "20261022_receipt_pdf_camera_evidence"
down_revision = "20261022_kds_attempt_consumption"
branch_labels = None
depends_on = None

def upgrade():
    op.alter_column("inventory_receipt_documents", "raw_xml", existing_type=sa.Text(), nullable=True)
    op.add_column("inventory_receipt_documents", sa.Column("raw_content", sa.LargeBinary(), nullable=True))
    op.add_column("inventory_receipt_documents", sa.Column("source_filename", sa.String(255), nullable=True))
    op.add_column("inventory_receipt_documents", sa.Column("source_mime_type", sa.String(120), nullable=True))
    op.add_column("inventory_receipt_documents", sa.Column("extraction_method", sa.String(40), nullable=False, server_default="xml"))
    op.add_column("inventory_receipt_documents", sa.Column("extraction_error", sa.String(500), nullable=True))

def downgrade():
    op.drop_column("inventory_receipt_documents", "extraction_error")
    op.drop_column("inventory_receipt_documents", "extraction_method")
    op.drop_column("inventory_receipt_documents", "source_mime_type")
    op.drop_column("inventory_receipt_documents", "source_filename")
    op.drop_column("inventory_receipt_documents", "raw_content")
    op.alter_column("inventory_receipt_documents", "raw_xml", existing_type=sa.Text(), nullable=False)

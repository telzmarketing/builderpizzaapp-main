"""Add optimistic versioning to inbound inventory documents."""
from alembic import op
import sqlalchemy as sa

revision = "20261029_inventory_receipt_version"
down_revision = "20261029_inventory_lote5_contract"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("inventory_receipt_documents", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

def downgrade() -> None:
    op.drop_column("inventory_receipt_documents", "version")

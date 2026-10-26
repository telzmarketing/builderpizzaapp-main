"""Mark received inventory items that require kitchen portioning."""
from alembic import op
import sqlalchemy as sa

revision = "20261026_inventory_portionable"
down_revision = "20261026_manual_order_actor_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inventory_items", sa.Column("portionable", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("inventory_receipt_document_lines", sa.Column("portionable", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("inventory_items", "portionable")
    op.drop_column("inventory_receipt_document_lines", "portionable")

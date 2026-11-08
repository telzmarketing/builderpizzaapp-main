"""Store the technical sheet used by portioning operations."""
from alembic import op
import sqlalchemy as sa

revision = "20261110_portioning_technical_sheet"
down_revision = "20261109_inventory_unit_item_weights"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inventory_portion_configs", sa.Column("technical_instructions", sa.Text(), nullable=True))
    op.add_column("inventory_portion_configs", sa.Column("handling_instructions", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("inventory_portion_configs", "handling_instructions")
    op.drop_column("inventory_portion_configs", "technical_instructions")

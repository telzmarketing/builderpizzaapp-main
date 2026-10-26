"""Persist preparation quantity, portion weight and output lot metadata."""
from alembic import op
import sqlalchemy as sa

revision = "20261026_preparation_execution_metadata"
down_revision = "20261026_inventory_portionable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("preparation_executions", sa.Column("output_lot_code", sa.String(length=120), nullable=True))
    op.add_column("preparation_executions", sa.Column("expires_on", sa.Date(), nullable=True))
    op.add_column("preparation_executions", sa.Column("portion_grams", sa.Numeric(20, 6), nullable=True))
    op.add_column("preparation_executions", sa.Column("prepared_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for column in ("prepared_at", "portion_grams", "expires_on", "output_lot_code"):
        op.drop_column("preparation_executions", column)

"""Track stock consumption per immutable KDS production attempt."""
from alembic import op
import sqlalchemy as sa

revision = "20261022_kds_attempt_consumption"
down_revision = "20261022_kds_production"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "production_attempt_consumptions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("attempt_id", sa.String(), nullable=False),
        sa.Column("inventory_item_id", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 6), nullable=False),
        sa.Column("unit_cost", sa.Numeric(24, 8), nullable=False, server_default="0"),
        sa.Column("movement_ids", sa.JSON(), nullable=False),
        sa.Column("operation_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "attempt_id"], ["production_attempts.tenant_id", "production_attempts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "inventory_item_id"], ["inventory_items.tenant_id", "inventory_items.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("quantity > 0", name="ck_production_attempt_consumption_quantity"),
    )
    op.create_index("uq_production_attempt_consumptions_tenant_id_id", "production_attempt_consumptions", ["tenant_id", "id"], unique=True)
    op.create_index("uq_production_attempt_consumptions_attempt_item", "production_attempt_consumptions", ["tenant_id", "attempt_id", "inventory_item_id"], unique=True)

def downgrade():
    raise RuntimeError("Forward-only: preserve production consumption history.")

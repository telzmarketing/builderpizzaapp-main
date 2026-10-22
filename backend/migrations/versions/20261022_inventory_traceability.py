"""Add immutable lot opening and genealogy evidence."""
from alembic import op
import sqlalchemy as sa

revision = "20261022_inventory_traceability"
down_revision = "20261022_finance_fiscal_obligations"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "inventory_lot_openings",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("lot_id", sa.String(), nullable=False), sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rule_code", sa.String(80), nullable=False), sa.Column("resulting_expires_at", sa.DateTime(timezone=True)),
        sa.Column("idempotency_key", sa.String(200), nullable=False), sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("notes", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "lot_id"], ["inventory_lots.tenant_id", "inventory_lots.id"], name="fk_inventory_lot_opening_lot", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["admin_users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("length(trim(rule_code)) > 0", name="ck_inventory_lot_opening_rule"),
        sa.CheckConstraint("resulting_expires_at IS NULL OR resulting_expires_at >= opened_at", name="ck_inventory_lot_opening_dates"),
    )
    op.create_index("uq_inventory_lot_openings_tenant_id_id", "inventory_lot_openings", ["tenant_id", "id"], unique=True)
    op.create_index("uq_inventory_lot_openings_tenant_lot_key", "inventory_lot_openings", ["tenant_id", "lot_id", "idempotency_key"], unique=True)
    op.create_index("ix_inventory_lot_openings_tenant_lot", "inventory_lot_openings", ["tenant_id", "lot_id", "opened_at"])
    op.create_table(
        "inventory_lot_genealogy",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("source_lot_id", sa.String(), nullable=False), sa.Column("target_lot_id", sa.String(), nullable=False),
        sa.Column("operation_id", sa.String(), nullable=False), sa.Column("quantity", sa.Numeric(20, 6), nullable=False),
        sa.Column("unit_id", sa.String(), nullable=False), sa.Column("relation_type", sa.String(40), nullable=False, server_default="transformation"),
        sa.Column("actor_id", sa.String(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "source_lot_id"], ["inventory_lots.tenant_id", "inventory_lots.id"], name="fk_inventory_genealogy_source", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "target_lot_id"], ["inventory_lots.tenant_id", "inventory_lots.id"], name="fk_inventory_genealogy_target", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "operation_id"], ["inventory_operations.tenant_id", "inventory_operations.id"], name="fk_inventory_genealogy_operation", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["admin_users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("source_lot_id <> target_lot_id", name="ck_inventory_genealogy_distinct_lots"),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_genealogy_quantity"),
    )
    op.create_index("uq_inventory_lot_genealogy_tenant_id_id", "inventory_lot_genealogy", ["tenant_id", "id"], unique=True)
    op.create_index("uq_inventory_lot_genealogy_tenant_operation_source", "inventory_lot_genealogy", ["tenant_id", "operation_id", "source_lot_id", "target_lot_id"], unique=True)
    op.create_index("ix_inventory_lot_genealogy_source", "inventory_lot_genealogy", ["tenant_id", "source_lot_id", "created_at"])
    op.create_index("ix_inventory_lot_genealogy_target", "inventory_lot_genealogy", ["tenant_id", "target_lot_id", "created_at"])

def downgrade():
    raise RuntimeError("Forward-only: preserve lot opening and genealogy evidence.")

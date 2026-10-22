"""Add tenant-safe preparation recipes, orders and incremental executions."""
from alembic import op
import sqlalchemy as sa

revision = "20261022_preparation_execution"
down_revision = "20261022_inventory_traceability"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("inventory_operation_recipes",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(180), nullable=False), sa.Column("output_item_id", sa.String(), nullable=False),
        sa.Column("output_unit_id", sa.String(), nullable=False), sa.Column("yield_quantity", sa.Numeric(20,6), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"), sa.Column("instructions", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"), sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id","output_item_id"], ["inventory_items.tenant_id","inventory_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id","output_unit_id"], ["inventory_units.tenant_id","inventory_units.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["admin_users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("yield_quantity > 0", name="ck_operation_recipe_yield"), sa.CheckConstraint("version_number > 0", name="ck_operation_recipe_version"))
    op.create_index("uq_inventory_operation_recipes_tenant_id_id", "inventory_operation_recipes", ["tenant_id","id"], unique=True)
    op.create_index("uq_inventory_operation_recipes_tenant_name_version", "inventory_operation_recipes", ["tenant_id","name","version_number"], unique=True)
    op.create_table("inventory_operation_recipe_items",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("tenant_id", sa.String(), nullable=False), sa.Column("recipe_id", sa.String(), nullable=False),
        sa.Column("item_id", sa.String(), nullable=False), sa.Column("unit_id", sa.String(), nullable=False), sa.Column("quantity", sa.Numeric(20,6), nullable=False), sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["tenant_id","recipe_id"], ["inventory_operation_recipes.tenant_id","inventory_operation_recipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id","item_id"], ["inventory_items.tenant_id","inventory_items.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["tenant_id","unit_id"], ["inventory_units.tenant_id","inventory_units.id"], ondelete="RESTRICT"), sa.CheckConstraint("quantity > 0", name="ck_operation_recipe_item_quantity"))
    op.create_index("uq_inventory_operation_recipe_items_tenant_id_id", "inventory_operation_recipe_items", ["tenant_id","id"], unique=True)
    op.create_table("preparation_orders",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("tenant_id", sa.String(), nullable=False), sa.Column("recipe_id", sa.String(), nullable=False), sa.Column("target_quantity", sa.Numeric(20,6), nullable=False),
        sa.Column("produced_quantity", sa.Numeric(20,6), nullable=False, server_default="0"), sa.Column("lost_quantity", sa.Numeric(20,6), nullable=False, server_default="0"), sa.Column("discarded_quantity", sa.Numeric(20,6), nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"), sa.Column("scheduled_for", sa.DateTime(timezone=True)), sa.Column("version", sa.Integer(), nullable=False, server_default="1"), sa.Column("idempotency_key", sa.String(200), nullable=False), sa.Column("actor_id", sa.String(), nullable=False), sa.Column("notes", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["tenant_id","recipe_id"], ["inventory_operation_recipes.tenant_id","inventory_operation_recipes.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["actor_id"], ["admin_users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("target_quantity > 0", name="ck_preparation_order_target"), sa.CheckConstraint("status IN ('draft','approved','scheduled','waiting','in_progress','paused','partially_completed','blocked','completed','cancelled')", name="ck_preparation_order_status"))
    op.create_index("uq_preparation_orders_tenant_id_id", "preparation_orders", ["tenant_id","id"], unique=True); op.create_index("ix_preparation_orders_queue", "preparation_orders", ["tenant_id","status","scheduled_for"])
    op.create_table("preparation_executions",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("tenant_id", sa.String(), nullable=False), sa.Column("order_id", sa.String(), nullable=False), sa.Column("produced_quantity", sa.Numeric(20,6), nullable=False, server_default="0"), sa.Column("lost_quantity", sa.Numeric(20,6), nullable=False, server_default="0"), sa.Column("discarded_quantity", sa.Numeric(20,6), nullable=False, server_default="0"), sa.Column("operation_id", sa.String()), sa.Column("output_lot_id", sa.String()), sa.Column("idempotency_key", sa.String(200), nullable=False), sa.Column("actor_id", sa.String(), nullable=False), sa.Column("notes", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["tenant_id","order_id"], ["preparation_orders.tenant_id","preparation_orders.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["tenant_id","operation_id"], ["inventory_operations.tenant_id","inventory_operations.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["tenant_id","output_lot_id"], ["inventory_lots.tenant_id","inventory_lots.id"], ondelete="RESTRICT"), sa.ForeignKeyConstraint(["actor_id"], ["admin_users.id"], ondelete="RESTRICT"), sa.CheckConstraint("produced_quantity >= 0 AND lost_quantity >= 0 AND discarded_quantity >= 0 AND (produced_quantity + lost_quantity + discarded_quantity) > 0", name="ck_preparation_execution_quantities"))
    op.create_index("uq_preparation_executions_tenant_id_id", "preparation_executions", ["tenant_id","id"], unique=True); op.create_index("uq_preparation_executions_tenant_order_key", "preparation_executions", ["tenant_id","order_id","idempotency_key"], unique=True)

def downgrade():
    raise RuntimeError("Forward-only: preserve preparation history.")

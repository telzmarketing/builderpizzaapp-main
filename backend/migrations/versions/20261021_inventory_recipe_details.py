"""Add versioned technical instructions and explicit normalized recipe units.

No inference or rewriting of legacy units, quantities, public names or images.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261021_inventory_recipe_details"
down_revision = "20261021_inventory_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("inventory_recipe_versions", sa.Column("instructions", sa.Text(), nullable=True))
    op.add_column("inventory_recipe_versions", sa.Column("preparation_steps", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("inventory_recipe_versions", sa.Column("reference_image_url", sa.String(700), nullable=True))
    op.create_check_constraint("ck_inventory_recipe_steps_array", "inventory_recipe_versions", "jsonb_typeof(preparation_steps) = 'array'")

    op.add_column("inventory_recipe_items", sa.Column("unit_id", sa.String(), nullable=True))
    op.add_column("inventory_recipe_items", sa.Column("entered_unit_id", sa.String(), nullable=True))
    op.add_column("inventory_recipe_items", sa.Column("entered_quantity", sa.Numeric(20, 6), nullable=True))
    op.add_column("inventory_recipe_items", sa.Column("conversion_factor_snapshot", sa.Numeric(24, 12), nullable=True))
    op.add_column("inventory_recipe_items", sa.Column("position", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("inventory_recipe_items", sa.Column("public_name", sa.String(180), nullable=True))
    op.add_column("inventory_recipe_items", sa.Column("show_public", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("inventory_recipe_items", sa.Column("allow_removal", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_foreign_key("fk_inventory_recipe_item_unit", "inventory_recipe_items", "inventory_units", ["tenant_id", "unit_id"], ["tenant_id", "id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_inventory_recipe_item_entered_unit", "inventory_recipe_items", "inventory_units", ["tenant_id", "entered_unit_id"], ["tenant_id", "id"], ondelete="RESTRICT")
    for name, condition in (
        ("ck_inventory_recipe_item_position", "position >= 0"),
        ("ck_inventory_recipe_item_unit_owner", "unit_id IS NULL OR tenant_id IS NOT NULL"),
        ("ck_inventory_recipe_item_public_name", "NOT show_public OR (public_name IS NOT NULL AND length(trim(public_name)) > 0)"),
        ("ck_inventory_recipe_item_conversion", "(entered_unit_id IS NULL AND entered_quantity IS NULL AND conversion_factor_snapshot IS NULL) OR (tenant_id IS NOT NULL AND unit_id IS NOT NULL AND entered_unit_id IS NOT NULL AND entered_quantity IS NOT NULL AND conversion_factor_snapshot IS NOT NULL AND entered_quantity > 0 AND conversion_factor_snapshot > 0 AND quantity > 0 AND quantity = round(entered_quantity * conversion_factor_snapshot, 6))"),
        ("ck_inventory_recipe_items_entered_quantity_finite", "CAST(entered_quantity AS VARCHAR) <> 'NaN'"),
        ("ck_inventory_recipe_items_conversion_factor_snapshot_finite", "CAST(conversion_factor_snapshot AS VARCHAR) <> 'NaN'"),
    ):
        op.create_check_constraint(name, "inventory_recipe_items", condition)

    op.add_column("order_item_cmv_snapshots", sa.Column("composition_json", postgresql.JSONB(none_as_null=True), nullable=True))
    op.create_check_constraint("ck_order_item_cmv_composition_object", "order_item_cmv_snapshots", "composition_json IS NULL OR jsonb_typeof(composition_json) = 'object'")
    for table in ("order_items", "table_session_items"):
        op.add_column(table, sa.Column("customizations", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))
        op.create_check_constraint(f"ck_{table}_customizations_array", table, "jsonb_typeof(customizations) = 'array'")
    op.drop_constraint("ck_inventory_operation_kind", "inventory_operations", type_="check")
    op.create_check_constraint("ck_inventory_operation_kind", "inventory_operations", "kind IN ('manual_in','manual_out','transfer','loss','adjustment_in','adjustment_out','order_sale','order_sale_reversal','order_sale_loss','reservation','reservation_release','receipt','preparation','compensation','unit_definition','packaging_definition','lot_definition','lot_state','recipe_publication','recipe_archive')")


def downgrade():
    raise RuntimeError("Forward-only: preserve technical recipe versions and frozen conversion evidence.")

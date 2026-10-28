"""Add tenant-owned configurable product option groups and values.

This migration is additive. Existing pizza, drink and order contracts remain
unchanged; the new catalog configuration is opt-in until a product receives
an active option group.
"""
from alembic import op
import sqlalchemy as sa


revision = "20261028_product_option_groups"
down_revision = "20261027_logistics_settings_tenant_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_option_groups",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("selection_type", sa.String(16), nullable=False, server_default="single"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("min_selections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_selections", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_product_option_groups_tenant_id_tenants"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "product_id"],
            ["products.tenant_id", "products.id"],
            name="fk_product_option_groups_tenant_product",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("selection_type IN ('single','multiple','quantity','text')", name="ck_product_option_groups_selection_type"),
        sa.CheckConstraint("sort_order >= 0", name="ck_product_option_groups_sort_order"),
        sa.CheckConstraint("min_selections >= 0 AND max_selections >= min_selections", name="ck_product_option_groups_selection_bounds"),
        sa.CheckConstraint("NOT required OR min_selections >= 1", name="ck_product_option_groups_required_minimum"),
        sa.CheckConstraint("selection_type <> 'single' OR max_selections <= 1", name="ck_product_option_groups_single_maximum"),
    )
    op.create_index("uq_product_option_groups_tenant_id_id", "product_option_groups", ["tenant_id", "id"], unique=True)
    op.create_unique_constraint("uq_product_option_groups_product_key", "product_option_groups", ["tenant_id", "product_id", "key"])

    op.create_table(
        "product_options",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=True),
        sa.Column("group_id", sa.String(), nullable=False),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("price_addition", sa.Float(), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_product_options_tenant_id_tenants"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "group_id"],
            ["product_option_groups.tenant_id", "product_option_groups.id"],
            name="fk_product_options_tenant_group",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("sort_order >= 0", name="ck_product_options_sort_order"),
        sa.CheckConstraint("price_addition >= 0", name="ck_product_options_price_addition"),
    )
    op.create_index("uq_product_options_tenant_id_id", "product_options", ["tenant_id", "id"], unique=True)
    op.create_unique_constraint("uq_product_options_group_key", "product_options", ["tenant_id", "group_id", "key"])


def downgrade() -> None:
    op.drop_constraint("uq_product_options_group_key", "product_options", type="unique")
    op.drop_index("uq_product_options_tenant_id_id", table_name="product_options")
    op.drop_table("product_options")
    op.drop_constraint("uq_product_option_groups_product_key", "product_option_groups", type="unique")
    op.drop_index("uq_product_option_groups_tenant_id_id", table_name="product_option_groups")
    op.drop_table("product_option_groups")

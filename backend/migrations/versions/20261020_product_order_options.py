"""Preserve validated product options in orders and table sessions."""
from alembic import op
import sqlalchemy as sa

revision = "20261020_product_order_options"
down_revision = "20261017_runtime_schema"
branch_labels = None
depends_on = None


def upgrade():
    for name, kind in (
        ("selected_border_id", sa.String()), ("selected_border_name", sa.String(100)),
        ("selected_drink_variant_id", sa.String()),
    ):
        op.add_column("order_items", sa.Column(name, kind, nullable=True))
    for name, kind in (
        ("selected_size_id", sa.String()), ("selected_size", sa.String(50)),
        ("selected_crust_type_id", sa.String()), ("selected_crust_type_name", sa.String(100)),
        ("selected_border_id", sa.String()), ("selected_border_name", sa.String(100)),
        ("selected_drink_variant_id", sa.String()), ("selected_drink_variant_name", sa.String(100)),
    ):
        op.add_column("table_session_items", sa.Column(name, kind, nullable=True))
    op.add_column("table_session_items", sa.Column("flavor_division", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("table_session_items", sa.Column("flavors", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.create_foreign_key("fk_order_items_tenant_border", "order_items", "product_crust_types", ["tenant_id", "selected_border_id"], ["tenant_id", "id"])
    op.create_foreign_key("fk_order_items_tenant_drink_variant", "order_items", "product_drink_variants", ["tenant_id", "selected_drink_variant_id"], ["tenant_id", "id"])
    op.create_foreign_key("fk_table_session_items_tenant_size", "table_session_items", "product_sizes", ["tenant_id", "selected_size_id"], ["tenant_id", "id"])
    op.create_foreign_key("fk_table_session_items_tenant_crust", "table_session_items", "product_crust_types", ["tenant_id", "selected_crust_type_id"], ["tenant_id", "id"])
    op.create_foreign_key("fk_table_session_items_tenant_border", "table_session_items", "product_crust_types", ["tenant_id", "selected_border_id"], ["tenant_id", "id"])
    op.create_foreign_key("fk_table_session_items_tenant_drink_variant", "table_session_items", "product_drink_variants", ["tenant_id", "selected_drink_variant_id"], ["tenant_id", "id"])


def downgrade():
    for name, table in (("fk_table_session_items_tenant_drink_variant", "table_session_items"), ("fk_table_session_items_tenant_border", "table_session_items"), ("fk_table_session_items_tenant_crust", "table_session_items"), ("fk_table_session_items_tenant_size", "table_session_items"), ("fk_order_items_tenant_drink_variant", "order_items"), ("fk_order_items_tenant_border", "order_items")):
        op.drop_constraint(name, table, type_="foreignkey")
    for name in ("flavors", "flavor_division", "selected_drink_variant_name", "selected_drink_variant_id", "selected_border_name", "selected_border_id", "selected_crust_type_name", "selected_crust_type_id", "selected_size", "selected_size_id"):
        op.drop_column("table_session_items", name)
    for name in ("selected_drink_variant_id", "selected_border_name", "selected_border_id"):
        op.drop_column("order_items", name)

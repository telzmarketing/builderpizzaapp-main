"""Add tenant-scoped global pizza catalog configuration."""

from alembic import op
import sqlalchemy as sa


revision = "20261106_global_catalog"
down_revision = "20261106_production_vision_capture_rules"
branch_labels = None
depends_on = None


def _create(table, price=False, default=False):
    columns = [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text),
    ]
    if price:
        columns.append(sa.Column("price_addition", sa.Float, nullable=False, server_default="0"))
    columns.extend([
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
    ])
    if default:
        columns.append(sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()))
    columns.extend([
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "name", name=f"uq_{table}_tenant_name"),
    ])
    op.create_table(table, *columns)
    op.create_index(f"ix_{table}_tenant_active_order", table, ["tenant_id", "active", "sort_order"])


def upgrade() -> None:
    _create("pizza_global_sizes", default=True)
    _create("pizza_global_dough_types", price=True)
    _create("pizza_global_crusts", price=True)


def downgrade() -> None:
    for table in ("pizza_global_crusts", "pizza_global_dough_types", "pizza_global_sizes"):
        op.drop_index(f"ix_{table}_tenant_active_order", table_name=table)
        op.drop_table(table)

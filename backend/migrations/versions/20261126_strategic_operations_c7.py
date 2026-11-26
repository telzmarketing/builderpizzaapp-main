"""Link strategic reservations to canonical scheduled-order operations."""

from alembic import op
import sqlalchemy as sa


revision = "20261126_strategic_operations_c7"
down_revision = "20261126_strategic_capacity_reservations_c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("strategic_reservations", sa.Column("order_id", sa.String(), nullable=True))
    op.add_column(
        "strategic_reservations",
        sa.Column("operational_released_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_strategic_reservations_order",
        "strategic_reservations",
        "orders",
        ["tenant_id", "order_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_strategic_reservations_tenant_order",
        "strategic_reservations",
        ["tenant_id", "order_id"],
    )
    op.create_index(
        "ix_strategic_reservations_tenant_operational_release",
        "strategic_reservations",
        ["tenant_id", "status", "operational_released_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_strategic_reservations_tenant_operational_release",
        table_name="strategic_reservations",
    )
    op.drop_constraint(
        "uq_strategic_reservations_tenant_order",
        "strategic_reservations",
        type_="unique",
    )
    op.drop_constraint(
        "fk_strategic_reservations_order",
        "strategic_reservations",
        type_="foreignkey",
    )
    op.drop_column("strategic_reservations", "operational_released_at")
    op.drop_column("strategic_reservations", "order_id")

"""Add cancelled status and protect minimum-stock confirmations."""

from alembic import op


revision = "20261112_inventory_purchase_status"
down_revision = "20261112_inventory_purchase_titles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_inventory_purchases_status",
        "inventory_purchases",
        "status IN ('draft', 'requested', 'confirmed', 'cancelled')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_inventory_purchases_status", "inventory_purchases", type_="check")

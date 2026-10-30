"""Persist tenant-scoped, idempotent item QR confirmations for delivery."""
from alembic import op
import sqlalchemy as sa


revision = "20261029_delivery_item_qr_confirmations"
down_revision = "20261029_catalog_product_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "delivery_item_confirmations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("delivery_id", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("order_item_id", sa.String(), nullable=False),
        sa.Column("label_volume_id", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "delivery_id"],
            ["deliveries.tenant_id", "deliveries.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "order_item_id"],
            ["order_items.tenant_id", "order_items.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["label_volume_id"], ["label_volumes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["delivery_persons.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "token_hash", name="uq_delivery_item_confirmations_token"),
        sa.UniqueConstraint(
            "tenant_id", "delivery_id", "label_volume_id",
            name="uq_delivery_item_confirmations_volume",
        ),
    )
    op.create_index(
        "ix_delivery_item_confirmations_delivery",
        "delivery_item_confirmations",
        ["tenant_id", "delivery_id", "confirmed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_delivery_item_confirmations_delivery", table_name="delivery_item_confirmations")
    op.drop_table("delivery_item_confirmations")

"""product variation promotions

Revision ID: 20260425_product_promotions
Revises: 20260424_pizza_size_descriptions
Create Date: 2026-04-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260425_product_promotions"
down_revision = "20260424_pizza_size_descriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_promotions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("product_id", sa.String(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("valid_weekdays", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("start_time", sa.String(length=5), nullable=True),
        sa.Column("end_time", sa.String(length=5), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("discount_type", sa.String(length=30), nullable=False, server_default="fixed_price"),
        sa.Column("default_value", sa.Float(), nullable=True),
        sa.Column("timezone", sa.String(length=80), nullable=False, server_default="America/Sao_Paulo"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("ix_product_promotions_product_id", "product_promotions", ["product_id"])

    op.create_table(
        "product_promotion_combinations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("promotion_id", sa.String(), sa.ForeignKey("product_promotions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_size_id", sa.String(), sa.ForeignKey("product_sizes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("product_crust_type_id", sa.String(), sa.ForeignKey("product_crust_types.id", ondelete="CASCADE"), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("promotional_value", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.UniqueConstraint(
            "promotion_id",
            "product_size_id",
            "product_crust_type_id",
            name="uq_product_promotion_combination",
        ),
    )
    op.create_index("ix_product_promotion_combinations_promotion_id", "product_promotion_combinations", ["promotion_id"])
    op.create_index("ix_product_promotion_combinations_product_size_id", "product_promotion_combinations", ["product_size_id"])
    op.create_index("ix_product_promotion_combinations_product_crust_type_id", "product_promotion_combinations", ["product_crust_type_id"])

    op.add_column("order_items", sa.Column("selected_size_id", sa.String(), nullable=True))
    op.add_column("order_items", sa.Column("selected_crust_type_id", sa.String(), nullable=True))
    op.add_column("order_items", sa.Column("flavor_count", sa.Integer(), nullable=True, server_default="1"))
    op.add_column("order_items", sa.Column("standard_unit_price", sa.Float(), nullable=True))
    op.add_column("order_items", sa.Column("applied_unit_price", sa.Float(), nullable=True))
    op.add_column("order_items", sa.Column("promotion_id", sa.String(), nullable=True))
    op.add_column("order_items", sa.Column("promotion_name", sa.String(length=200), nullable=True))
    op.add_column("order_items", sa.Column("promotion_discount", sa.Float(), nullable=True, server_default="0"))
    op.add_column("order_items", sa.Column("promotion_blocked", sa.Boolean(), nullable=True, server_default=sa.text("FALSE")))
    op.add_column("order_items", sa.Column("promotion_block_reason", sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column("order_items", "promotion_block_reason")
    op.drop_column("order_items", "promotion_blocked")
    op.drop_column("order_items", "promotion_discount")
    op.drop_column("order_items", "promotion_name")
    op.drop_column("order_items", "promotion_id")
    op.drop_column("order_items", "applied_unit_price")
    op.drop_column("order_items", "standard_unit_price")
    op.drop_column("order_items", "flavor_count")
    op.drop_column("order_items", "selected_crust_type_id")
    op.drop_column("order_items", "selected_size_id")
    op.drop_table("product_promotion_combinations")
    op.drop_table("product_promotions")

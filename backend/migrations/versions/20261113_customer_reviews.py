"""Add tenant-scoped customer reviews and moderation state."""

from alembic import op
import sqlalchemy as sa


revision = "20261113_customer_reviews"
down_revision = "20261113_campaign_highlight_target"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("order_id", sa.String, nullable=False),
        sa.Column("order_item_id", sa.String, nullable=True),
        sa.Column("product_id", sa.String, nullable=True),
        sa.Column("delivery_id", sa.String, nullable=True),
        sa.Column("customer_id", sa.String, sa.ForeignKey("customers.id", ondelete="SET NULL")),
        sa.Column("review_type", sa.String(20), nullable=False),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text),
        sa.Column("author_name", sa.String(200)),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("source", sa.String(20), nullable=False, server_default="customer"),
        sa.Column("moderation_note", sa.Text),
        sa.Column("moderated_by_admin_id", sa.String, sa.ForeignKey("admin_users.id", ondelete="SET NULL")),
        sa.Column("moderated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id", "order_id"], ["orders.tenant_id", "orders.id"], ondelete="RESTRICT", name="fk_customer_reviews_tenant_order"),
        sa.ForeignKeyConstraint(["tenant_id", "order_item_id"], ["order_items.tenant_id", "order_items.id"], ondelete="RESTRICT", name="fk_customer_reviews_tenant_order_item"),
        sa.ForeignKeyConstraint(["tenant_id", "product_id"], ["products.tenant_id", "products.id"], ondelete="RESTRICT", name="fk_customer_reviews_tenant_product"),
        sa.ForeignKeyConstraint(["tenant_id", "delivery_id"], ["deliveries.tenant_id", "deliveries.id"], ondelete="RESTRICT", name="fk_customer_reviews_tenant_delivery"),
        sa.CheckConstraint("review_type IN ('order','item','delivery')", name="ck_customer_reviews_type"),
        sa.CheckConstraint("status IN ('pending','approved','rejected')", name="ck_customer_reviews_status"),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_customer_reviews_rating"),
    )
    op.create_index("ix_customer_reviews_tenant_status_created", "customer_reviews", ["tenant_id", "status", "created_at"])
    op.create_index("ix_customer_reviews_tenant_product_status", "customer_reviews", ["tenant_id", "product_id", "status"])
    op.create_index("ix_customer_reviews_tenant_order", "customer_reviews", ["tenant_id", "order_id"])


def downgrade() -> None:
    op.drop_index("ix_customer_reviews_tenant_order", table_name="customer_reviews")
    op.drop_index("ix_customer_reviews_tenant_product_status", table_name="customer_reviews")
    op.drop_index("ix_customer_reviews_tenant_status_created", table_name="customer_reviews")
    op.drop_table("customer_reviews")

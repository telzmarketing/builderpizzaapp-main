"""C11: composicoes multissubcategoria e grupos comerciais estrategicos."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261126_strategic_campaigns_c11"
down_revision = "20261126_strategic_campaign_publish_rbac_c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("strategic_offers", sa.Column("reference_type", sa.String(30), nullable=False, server_default="product"))
    op.add_column("strategic_offers", sa.Column("pricing_strategy", sa.String(30), nullable=False, server_default="catalog"))
    op.add_column("strategic_offers", sa.Column("discount_percent", sa.Numeric(8, 4), nullable=True))
    op.add_column("strategic_offers", sa.Column("discount_amount", sa.Numeric(20, 2), nullable=True))
    op.add_column("strategic_offers", sa.Column("fixed_promotional_price", sa.Numeric(20, 2), nullable=True))
    op.add_column("strategic_offers", sa.Column("composition_revision", sa.Integer(), nullable=False, server_default="1"))
    op.execute("UPDATE strategic_offers SET reference_type = CASE WHEN kit_id IS NOT NULL THEN 'kit' ELSE 'product' END")
    op.create_check_constraint("ck_strategic_offers_reference_type", "strategic_offers", "reference_type IN ('product','kit','subcategory','mixed_subcategories')")
    op.create_check_constraint("ck_strategic_offers_pricing_strategy", "strategic_offers", "pricing_strategy IN ('catalog','percentage','fixed_discount','fixed_price')")
    op.create_check_constraint("ck_strategic_offers_composition_revision", "strategic_offers", "composition_revision > 0")

    op.create_table(
        "strategic_offer_components",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("offer_id", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("subcategory_id", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("allow_repeated_products", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "restrictions",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id", "offer_id"], ["strategic_offers.tenant_id", "strategic_offers.id"], name="fk_strategic_offer_components_offer", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id", "subcategory_id"], ["product_categories.tenant_id", "product_categories.id"], name="fk_strategic_offer_components_subcategory", ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", "offer_id", "position", name="uq_strategic_offer_components_position"),
        sa.UniqueConstraint("tenant_id", "offer_id", "subcategory_id", name="uq_strategic_offer_components_subcategory"),
        sa.CheckConstraint("position >= 0", name="ck_strategic_offer_components_position"),
        sa.CheckConstraint("quantity > 0", name="ck_strategic_offer_components_quantity"),
    )
    op.create_index("ix_strategic_offer_components_tenant_offer", "strategic_offer_components", ["tenant_id", "offer_id"])

    # Existing orders predate the explicit channel contract. Preserve that
    # uncertainty instead of falsely attributing historical sales to landing.
    op.add_column("orders", sa.Column("entry_channel", sa.String(30), nullable=True))
    op.execute("UPDATE orders SET entry_channel = 'legacy_unknown' WHERE entry_channel IS NULL")
    op.alter_column("orders", "entry_channel", existing_type=sa.String(30), nullable=False)
    op.create_check_constraint(
        "ck_orders_entry_channel",
        "orders",
        "entry_channel IN ('legacy_unknown','landing_page','pdv','operations','phone','whatsapp','counter')",
    )
    op.create_table(
        "order_commercial_groups",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("group_type", sa.String(30), nullable=False, server_default="strategic_offer"),
        sa.Column("strategic_campaign_id", sa.String(), nullable=False),
        sa.Column("strategic_offer_id", sa.String(), nullable=False),
        sa.Column("campaign_version", sa.Integer(), nullable=False),
        sa.Column("composition_revision", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("entry_channel", sa.String(30), nullable=False),
        sa.Column("pricing_strategy", sa.String(30), nullable=False),
        sa.Column("original_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("promotional_amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("commercial_snapshot", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id", "order_id"], ["orders.tenant_id", "orders.id"], name="fk_order_commercial_groups_order", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id", "strategic_campaign_id"], ["strategic_campaigns.tenant_id", "strategic_campaigns.id"], name="fk_order_commercial_groups_campaign", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "strategic_offer_id"], ["strategic_offers.tenant_id", "strategic_offers.id"], name="fk_order_commercial_groups_offer", ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_order_commercial_groups_tenant_id"),
        sa.UniqueConstraint("tenant_id", "order_id", "position", name="uq_order_commercial_groups_position"),
        sa.CheckConstraint("quantity > 0", name="ck_order_commercial_groups_quantity"),
    )
    op.create_index("ix_order_commercial_groups_tenant_offer", "order_commercial_groups", ["tenant_id", "strategic_offer_id", "created_at"])
    op.add_column("order_items", sa.Column("commercial_group_id", sa.String(), nullable=True))
    op.add_column("order_items", sa.Column("commercial_group_position", sa.Integer(), nullable=True))
    op.add_column("order_items", sa.Column("source_subcategory_id", sa.String(), nullable=True))
    op.create_foreign_key(
        "fk_order_items_commercial_group",
        "order_items",
        "order_commercial_groups",
        ["tenant_id", "commercial_group_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_order_items_source_subcategory",
        "order_items",
        "product_categories",
        ["tenant_id", "source_subcategory_id"],
        ["tenant_id", "id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "strategic_offer_redemptions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("offer_id", sa.String(), nullable=False),
        sa.Column("commercial_group_id", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="confirmed"),
        sa.Column("entry_channel", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id", "offer_id"], ["strategic_offers.tenant_id", "strategic_offers.id"], name="fk_strategic_offer_redemptions_offer", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "commercial_group_id"], ["order_commercial_groups.tenant_id", "order_commercial_groups.id"], name="fk_strategic_offer_redemptions_group", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "order_id"], ["orders.tenant_id", "orders.id"], name="fk_strategic_offer_redemptions_order", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "customer_id"], ["customers.tenant_id", "customers.id"], name="fk_strategic_offer_redemptions_customer", ondelete="RESTRICT"),
        sa.UniqueConstraint("tenant_id", "commercial_group_id", name="uq_strategic_offer_redemptions_group"),
        sa.CheckConstraint("quantity > 0", name="ck_strategic_offer_redemptions_quantity"),
        sa.CheckConstraint("status IN ('confirmed','released','cancelled','refunded')", name="ck_strategic_offer_redemptions_status"),
    )
    op.create_index("ix_strategic_offer_redemptions_offer_status", "strategic_offer_redemptions", ["tenant_id", "offer_id", "status"])
    op.create_index("ix_strategic_offer_redemptions_customer", "strategic_offer_redemptions", ["tenant_id", "offer_id", "customer_id", "status"])
    op.create_index("ix_strategic_offer_redemptions_order_status", "strategic_offer_redemptions", ["tenant_id", "order_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_strategic_offer_redemptions_order_status", table_name="strategic_offer_redemptions")
    op.drop_index("ix_strategic_offer_redemptions_customer", table_name="strategic_offer_redemptions")
    op.drop_index("ix_strategic_offer_redemptions_offer_status", table_name="strategic_offer_redemptions")
    op.drop_table("strategic_offer_redemptions")
    op.drop_constraint("fk_order_items_source_subcategory", "order_items", type_="foreignkey")
    op.drop_constraint("fk_order_items_commercial_group", "order_items", type_="foreignkey")
    op.drop_column("order_items", "source_subcategory_id")
    op.drop_column("order_items", "commercial_group_position")
    op.drop_column("order_items", "commercial_group_id")
    op.drop_index("ix_order_commercial_groups_tenant_offer", table_name="order_commercial_groups")
    op.drop_table("order_commercial_groups")
    op.drop_constraint("ck_orders_entry_channel", "orders", type_="check")
    op.drop_column("orders", "entry_channel")
    op.drop_index("ix_strategic_offer_components_tenant_offer", table_name="strategic_offer_components")
    op.drop_table("strategic_offer_components")
    op.drop_constraint("ck_strategic_offers_composition_revision", "strategic_offers", type_="check")
    op.drop_constraint("ck_strategic_offers_pricing_strategy", "strategic_offers", type_="check")
    op.drop_constraint("ck_strategic_offers_reference_type", "strategic_offers", type_="check")
    op.drop_column("strategic_offers", "composition_revision")
    op.drop_column("strategic_offers", "fixed_promotional_price")
    op.drop_column("strategic_offers", "discount_amount")
    op.drop_column("strategic_offers", "discount_percent")
    op.drop_column("strategic_offers", "pricing_strategy")
    op.drop_column("strategic_offers", "reference_type")

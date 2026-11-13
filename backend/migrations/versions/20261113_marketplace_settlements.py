"""Add tenant-scoped marketplace settlement records."""
from alembic import op
import sqlalchemy as sa

revision = "20261113_marketplace_settlements"
down_revision = "20261112_tenant_ai_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_settlements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("order_id", sa.String, sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="expected"),
        sa.Column("gross_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("store_discount_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("marketplace_discount_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("delivery_fee", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("service_fee", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("commission_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("expected_net_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("received_net_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("variance_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("external_settlement_reference", sa.String(180)),
        sa.Column("expected_settlement_at", sa.DateTime(timezone=True)),
        sa.Column("settled_at", sa.DateTime(timezone=True)),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("notes", sa.String(1000)),
        sa.Column("created_by_admin_id", sa.String, sa.ForeignKey("admin_users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("provider IN ('partner_99','ifood','keeta')", name="ck_marketplace_settlements_provider"),
        sa.CheckConstraint("status IN ('expected','partially_received','received','divergent','cancelled','quarantined')", name="ck_marketplace_settlements_status"),
    )
    op.create_index("uq_marketplace_settlements_tenant_provider_order", "marketplace_settlements", ["tenant_id", "provider", "order_id"], unique=True)
    op.create_index("uq_marketplace_settlements_tenant_idempotency", "marketplace_settlements", ["tenant_id", "idempotency_key"], unique=True)
    op.create_index("ix_marketplace_settlements_tenant_status", "marketplace_settlements", ["tenant_id", "status"])


def downgrade() -> None:
    op.drop_table("marketplace_settlements")

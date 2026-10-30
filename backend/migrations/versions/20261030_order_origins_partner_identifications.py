"""Persist order origins and tenant-scoped partner identifications.

Legacy orders are classified as own sales. The partner order number is kept in
its own column so ``external_reference`` remains available for idempotency.
This migration is intentionally forward-only because removing these fields
would erase operational origin evidence.
"""
from alembic import op
import sqlalchemy as sa


revision = "20261030_order_origins_partner_identifications"
down_revision = "20261030_backfill_legacy_border_option_kind"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column(
        "order_origin", sa.String(length=20), nullable=False, server_default="own",
    ))
    op.add_column("orders", sa.Column(
        "partner_order_number", sa.String(length=120), nullable=True,
    ))
    op.create_check_constraint(
        "ck_orders_order_origin", "orders",
        "order_origin IN ('own','partner_99','ifood','keeta')",
    )
    op.create_table(
        "partner_identification_configs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("partner_code", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("logo_url", sa.String(length=500), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_partner_identification_configs_tenant_id_tenants", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "partner_code IN ('own','partner_99','ifood','keeta')",
            name="ck_partner_identification_configs_partner_code",
        ),
    )
    op.create_index(
        "uq_partner_identification_configs_tenant_partner",
        "partner_identification_configs", ["tenant_id", "partner_code"], unique=True,
    )
    op.create_index(
        "ix_partner_identification_configs_tenant",
        "partner_identification_configs", ["tenant_id"], unique=False,
    )


def downgrade() -> None:
    raise RuntimeError(
        "Forward-only migration: order origin and partner identification evidence must be preserved."
    )

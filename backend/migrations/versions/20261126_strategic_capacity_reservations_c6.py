"""Add tenant-scoped strategic campaign capacity slots and reservations."""

from alembic import op
import sqlalchemy as sa


revision = "20261126_strategic_capacity_reservations_c6"
down_revision = "20261125_strategic_offer_archive_c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_strategic_campaigns_tenant_id",
        "strategic_campaigns",
        ["tenant_id", "id"],
    )
    op.create_unique_constraint(
        "uq_strategic_offers_tenant_id",
        "strategic_offers",
        ["tenant_id", "id"],
    )

    op.create_table(
        "strategic_capacity_slots",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("offer_id", sa.String(), nullable=True),
        sa.Column("offer_scope", sa.String(), nullable=False, server_default="*"),
        sa.Column("label", sa.String(length=160), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("capacity_total", sa.Integer(), nullable=False),
        sa.Column("capacity_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("ends_at > starts_at", name="ck_strategic_capacity_slot_period"),
        sa.CheckConstraint(
            "offer_scope = COALESCE(offer_id, '*')",
            name="ck_strategic_capacity_slot_offer_scope",
        ),
        sa.CheckConstraint("capacity_total > 0", name="ck_strategic_capacity_slot_total"),
        sa.CheckConstraint(
            "capacity_used >= 0 AND capacity_used <= capacity_total",
            name="ck_strategic_capacity_slot_usage",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "campaign_id"],
            ["strategic_campaigns.tenant_id", "strategic_campaigns.id"],
            name="fk_strategic_capacity_slots_campaign",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "offer_id"],
            ["strategic_offers.tenant_id", "strategic_offers.id"],
            name="fk_strategic_capacity_slots_offer",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_strategic_capacity_slots_tenant_id"),
        sa.UniqueConstraint(
            "tenant_id", "campaign_id", "offer_scope", "starts_at",
            name="uq_strategic_capacity_slot_scope_start",
        ),
    )
    op.create_index(
        "ix_strategic_capacity_slots_tenant_campaign_start",
        "strategic_capacity_slots",
        ["tenant_id", "campaign_id", "starts_at"],
    )
    op.create_index(
        "ix_strategic_capacity_slots_tenant_offer_start",
        "strategic_capacity_slots",
        ["tenant_id", "offer_id", "starts_at"],
    )

    op.create_table(
        "strategic_reservations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("campaign_id", sa.String(), nullable=False),
        sa.Column("offer_id", sa.String(), nullable=True),
        sa.Column("slot_id", sa.String(), nullable=False),
        sa.Column("customer_reference", sa.String(length=200), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="held"),
        sa.Column("payment_mode", sa.String(length=20), nullable=False, server_default="no_payment"),
        sa.Column("amount_total", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("amount_paid", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("release_reason", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("quantity > 0", name="ck_strategic_reservation_quantity"),
        sa.CheckConstraint(
            "status IN ('held','confirmed','released','expired','cancelled')",
            name="ck_strategic_reservation_status",
        ),
        sa.CheckConstraint(
            "payment_mode IN ('no_payment','partial','full')",
            name="ck_strategic_reservation_payment_mode",
        ),
        sa.CheckConstraint(
            "amount_total >= 0 AND amount_paid >= 0 AND amount_paid <= amount_total",
            name="ck_strategic_reservation_amounts",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "campaign_id"],
            ["strategic_campaigns.tenant_id", "strategic_campaigns.id"],
            name="fk_strategic_reservations_campaign",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "offer_id"],
            ["strategic_offers.tenant_id", "strategic_offers.id"],
            name="fk_strategic_reservations_offer",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "slot_id"],
            ["strategic_capacity_slots.tenant_id", "strategic_capacity_slots.id"],
            name="fk_strategic_reservations_slot",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key",
            name="uq_strategic_reservations_tenant_idempotency",
        ),
    )
    op.create_index(
        "ix_strategic_reservations_tenant_campaign_status",
        "strategic_reservations",
        ["tenant_id", "campaign_id", "status", "created_at"],
    )
    op.create_index(
        "ix_strategic_reservations_tenant_slot_status_expiry",
        "strategic_reservations",
        ["tenant_id", "slot_id", "status", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_strategic_reservations_tenant_slot_status_expiry", table_name="strategic_reservations")
    op.drop_index("ix_strategic_reservations_tenant_campaign_status", table_name="strategic_reservations")
    op.drop_table("strategic_reservations")
    op.drop_index("ix_strategic_capacity_slots_tenant_offer_start", table_name="strategic_capacity_slots")
    op.drop_index("ix_strategic_capacity_slots_tenant_campaign_start", table_name="strategic_capacity_slots")
    op.drop_table("strategic_capacity_slots")
    op.drop_constraint("uq_strategic_offers_tenant_id", "strategic_offers", type_="unique")
    op.drop_constraint("uq_strategic_campaigns_tenant_id", "strategic_campaigns", type_="unique")

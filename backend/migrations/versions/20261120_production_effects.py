"""Create immutable tenant-scoped production effects."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "20261120_production_effects"
down_revision = "20261120_order_amendments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    source_effect_fk = sa.ForeignKeyConstraint(
        ["tenant_id", "source_effect_id"],
        ["production_effects.tenant_id", "production_effects.id"],
        ondelete="RESTRICT",
        name="fk_production_effects_source_effect",
    )

    op.create_table(
        "production_effects",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("business_key", sa.String(200), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("order_id", sa.String, nullable=False),
        sa.Column("attempt_id", sa.String, nullable=True),
        sa.Column("source_effect_id", sa.String, nullable=True),
        sa.Column("actor_id", sa.String, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("cost_total", sa.Numeric(24, 8), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(20, 2), nullable=False, server_default="0"),
        sa.Column("snapshot_json", sa.JSON().with_variant(JSONB(), "postgresql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["tenant_id", "order_id"],
            ["orders.tenant_id", "orders.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "attempt_id"],
            ["production_attempts.tenant_id", "production_attempts.id"],
            ondelete="RESTRICT",
        ),
        # SQLite cannot add a foreign key with ALTER TABLE.  Define it inline
        # there; PostgreSQL receives it after the composite unique index is
        # created below, as required for the referenced key.
        *( [source_effect_fk] if is_sqlite else [] ),
        sa.CheckConstraint("kind IN ('loss','reproduction','bonification')", name="ck_production_effect_kind"),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_production_effect_request_hash_length"),
        sa.CheckConstraint("cost_total >= 0", name="ck_production_effect_cost_total_nonnegative"),
        sa.CheckConstraint("discount_amount >= 0", name="ck_production_effect_discount_amount_nonnegative"),
        sa.CheckConstraint(
            "length(trim(id)) > 0 AND length(trim(tenant_id)) > 0 "
            "AND length(trim(business_key)) > 0 AND length(trim(idempotency_key)) > 0 "
            "AND length(trim(order_id)) > 0 AND length(trim(actor_id)) > 0 "
            "AND length(trim(reason)) > 0",
            name="ck_production_effect_required_text_nonempty",
        ),
        sa.CheckConstraint(
            "(attempt_id IS NULL OR length(trim(attempt_id)) > 0) "
            "AND (source_effect_id IS NULL OR length(trim(source_effect_id)) > 0)",
            name="ck_production_effect_optional_ids_nonempty",
        ),
        sa.CheckConstraint(
            "(kind IN ('loss','reproduction') AND attempt_id IS NOT NULL) "
            "OR (kind = 'bonification' AND attempt_id IS NULL)",
            name="ck_production_effect_attempt_by_kind",
        ),
        sa.CheckConstraint(
            "(kind = 'reproduction' AND source_effect_id IS NOT NULL) "
            "OR (kind IN ('loss','bonification') AND source_effect_id IS NULL)",
            name="ck_production_effect_source_by_kind",
        ),
    )
    op.create_index("uq_production_effects_tenant_id_id", "production_effects", ["tenant_id", "id"], unique=True)
    op.create_index(
        "uq_production_effects_tenant_kind_business_key",
        "production_effects",
        ["tenant_id", "kind", "business_key"],
        unique=True,
    )
    op.create_index(
        "uq_production_effects_tenant_kind_idempotency_key",
        "production_effects",
        ["tenant_id", "kind", "idempotency_key"],
        unique=True,
    )
    # PostgreSQL requires the referenced unique key to exist before creating
    # a self-referencing composite FK.  The table-level FK cannot be emitted
    # inside create_table because the tenant/id unique index is created just
    # afterward.
    if not is_sqlite:
        op.create_foreign_key(
            "fk_production_effects_source_effect",
            "production_effects",
            "production_effects",
            ["tenant_id", "source_effect_id"],
            ["tenant_id", "id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    # Effects are immutable stock/financial history.  Do not remove the table
    # on a live database once any effect exists; offline SQL generation remains
    # available for inspected rollback plans.
    if not op.get_context().as_sql:
        has_history = op.get_bind().execute(
            sa.text("SELECT EXISTS (SELECT 1 FROM production_effects)")
        ).scalar()
        if has_history:
            raise RuntimeError("Refusing to downgrade production_effects because it contains history")

    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_production_effects_source_effect", "production_effects", type="foreignkey")
    op.drop_index("uq_production_effects_tenant_kind_idempotency_key", table_name="production_effects")
    op.drop_index("uq_production_effects_tenant_kind_business_key", table_name="production_effects")
    op.drop_index("uq_production_effects_tenant_id_id", table_name="production_effects")
    op.drop_table("production_effects")

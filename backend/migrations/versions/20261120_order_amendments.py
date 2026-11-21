"""Add revisioned checkout composition history without changing existing orders."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261120_order_amendments"
down_revision = "20261117_combo_landing"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("orders", sa.Column("composition_revision", sa.Integer(), nullable=False, server_default="0"))
    op.create_check_constraint("ck_orders_composition_revision", "orders", "composition_revision >= 0")
    # ``idempotency_keys.id`` is globally unique, but the amendment must also
    # prove that the claimed key belongs to the same tenant as the order.  The
    # supporting unique index makes that tenant boundary enforceable by a
    # composite foreign key without changing the earlier idempotency migration.
    op.create_index(
        "uq_idempotency_keys_tenant_id_id",
        "idempotency_keys",
        ["tenant_id", "id"],
        unique=True,
    )
    op.create_table(
        "order_amendments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("idempotency_key_id", sa.String(), nullable=False),
        sa.Column("actor_id", sa.String(100), nullable=False),
        sa.Column("actor_name", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("before_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("after_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id", "order_id"], ["orders.tenant_id", "orders.id"],
                                name="fk_order_amendments_tenant_order", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "idempotency_key_id"],
            ["idempotency_keys.tenant_id", "idempotency_keys.id"],
            name="fk_order_amendments_tenant_idempotency_key",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("revision > 0", name="ck_order_amendments_revision"),
    )
    op.create_index("uq_order_amendments_revision", "order_amendments", ["tenant_id", "order_id", "revision"], unique=True)
    op.create_index("uq_order_amendments_claim", "order_amendments", ["idempotency_key_id"], unique=True)
    op.execute("""
        CREATE FUNCTION reject_order_amendment_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Order amendment history is immutable';
        END; $$
    """)
    op.execute("""
        CREATE TRIGGER order_amendments_immutable BEFORE UPDATE OR DELETE ON order_amendments
        FOR EACH ROW EXECUTE FUNCTION reject_order_amendment_mutation()
    """)


def downgrade():
    # Amendment history and revision numbers are part of the audit trail.  A
    # live downgrade must fail closed instead of silently deleting them.  Keep
    # offline SQL rendering available for review/rollback scripts.
    if not op.get_context().as_sql:
        has_history = op.get_bind().execute(sa.text(
            "SELECT EXISTS (SELECT 1 FROM order_amendments) "
            "OR EXISTS (SELECT 1 FROM orders WHERE composition_revision > 0)"
        )).scalar()
        if has_history:
            raise RuntimeError(
                "Refusing to downgrade order_amendments because amendment history exists"
            )

    op.drop_table("order_amendments")
    op.drop_index("uq_idempotency_keys_tenant_id_id", table_name="idempotency_keys")
    op.execute("DROP FUNCTION reject_order_amendment_mutation()")
    op.drop_constraint("ck_orders_composition_revision", "orders", type_="check")
    op.drop_column("orders", "composition_revision")

"""Add tenant-scoped purchase requisition foundation."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261124_purchase_requisition_foundation"
down_revision = "20261122_print_agent_protocol"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_requisitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("requested_by_admin_id", sa.String, sa.ForeignKey("admin_users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("needed_by", sa.Date),
        sa.Column("reason", sa.String(500)),
        sa.Column("notes", sa.Text),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "code", name="uq_purchase_requisitions_tenant_code"),
        sa.CheckConstraint("status IN ('draft','submitted','approved','sourcing','ordered','partially_fulfilled','fulfilled','rejected','cancelled')", name="ck_purchase_requisitions_status"),
        sa.CheckConstraint("priority IN ('normal','urgent','emergency')", name="ck_purchase_requisitions_priority"),
        sa.CheckConstraint("version > 0", name="ck_purchase_requisitions_version"),
    )
    op.create_index("uq_purchase_requisitions_tenant_id_id", "purchase_requisitions", ["tenant_id", "id"], unique=True)
    op.create_index("ix_purchase_requisitions_tenant_status", "purchase_requisitions", ["tenant_id", "status"])
    op.create_index("ix_purchase_requisitions_tenant_requester", "purchase_requisitions", ["tenant_id", "requested_by_admin_id"])

    op.create_table(
        "purchase_requisition_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requisition_id", sa.String(36), nullable=False),
        sa.Column("item_id", sa.String, nullable=False),
        sa.Column("unit_id", sa.String, nullable=False),
        sa.Column("quantity", sa.Numeric(20, 6), nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id", "requisition_id"], ["purchase_requisitions.tenant_id", "purchase_requisitions.id"], name="fk_purchase_requisition_items_requisition", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id", "item_id"], ["inventory_items.tenant_id", "inventory_items.id"], name="fk_purchase_requisition_items_item", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "unit_id"], ["inventory_units.tenant_id", "inventory_units.id"], name="fk_purchase_requisition_items_unit", ondelete="RESTRICT"),
        sa.CheckConstraint("quantity > 0 AND CAST(quantity AS VARCHAR) <> 'NaN'", name="ck_purchase_requisition_items_quantity"),
        sa.CheckConstraint("position >= 0", name="ck_purchase_requisition_items_position"),
    )
    op.create_index("uq_purchase_requisition_items_tenant_id_id", "purchase_requisition_items", ["tenant_id", "id"], unique=True)
    op.create_index("uq_purchase_requisition_items_position", "purchase_requisition_items", ["tenant_id", "requisition_id", "position"], unique=True)

    op.create_table(
        "purchase_requisition_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requisition_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("from_status", sa.String(30)),
        sa.Column("to_status", sa.String(30), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("actor_admin_id", sa.String, sa.ForeignKey("admin_users.id", name="fk_purchase_requisition_events_actor", ondelete="SET NULL")),
        sa.Column("reason", sa.String(500)),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id", "requisition_id"], ["purchase_requisitions.tenant_id", "purchase_requisitions.id"], name="fk_purchase_requisition_events_requisition", ondelete="RESTRICT"),
        sa.CheckConstraint("sequence > 0", name="ck_purchase_requisition_events_sequence"),
    )
    op.create_index("uq_purchase_requisition_events_tenant_id_id", "purchase_requisition_events", ["tenant_id", "id"], unique=True)
    op.create_index("uq_purchase_requisition_events_sequence", "purchase_requisition_events", ["tenant_id", "requisition_id", "sequence"], unique=True)
    op.execute("""
        CREATE FUNCTION reject_purchase_requisition_event_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Purchase requisition events are immutable'; END; $$
    """)
    op.execute("""
        CREATE TRIGGER purchase_requisition_events_immutable BEFORE UPDATE OR DELETE ON purchase_requisition_events
        FOR EACH ROW EXECUTE FUNCTION reject_purchase_requisition_event_mutation()
    """)


def downgrade() -> None:
    if not op.get_context().as_sql:
        has_history = op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM purchase_requisition_events) OR EXISTS (SELECT 1 FROM purchase_requisitions)" )).scalar()
        if has_history:
            raise RuntimeError("Refusing to downgrade purchase requisition history")
    op.execute("DROP TRIGGER IF EXISTS purchase_requisition_events_immutable ON purchase_requisition_events")
    op.execute("DROP FUNCTION IF EXISTS reject_purchase_requisition_event_mutation()")
    op.drop_index("uq_purchase_requisition_events_sequence", table_name="purchase_requisition_events")
    op.drop_index("uq_purchase_requisition_events_tenant_id_id", table_name="purchase_requisition_events")
    op.drop_table("purchase_requisition_events")
    op.drop_index("uq_purchase_requisition_items_position", table_name="purchase_requisition_items")
    op.drop_index("uq_purchase_requisition_items_tenant_id_id", table_name="purchase_requisition_items")
    op.drop_table("purchase_requisition_items")
    op.drop_index("ix_purchase_requisitions_tenant_requester", table_name="purchase_requisitions")
    op.drop_index("ix_purchase_requisitions_tenant_status", table_name="purchase_requisitions")
    op.drop_index("uq_purchase_requisitions_tenant_id_id", table_name="purchase_requisitions")
    op.drop_table("purchase_requisitions")

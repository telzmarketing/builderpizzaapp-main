"""Add tenant-scoped ERP print center MVP."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "20261121_print_center"
down_revision = "20261121_payment_amendment_settlement"
branch_labels = None
depends_on = None
J = sa.JSON().with_variant(JSONB(), "postgresql")

def upgrade():
    op.create_table("print_stations", sa.Column("id", sa.String(36), primary_key=True), sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False), sa.Column("code", sa.String(80), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("hostname", sa.String(255)), sa.Column("connected", sa.Boolean, nullable=False, server_default="false"), sa.Column("last_seen_at", sa.DateTime(timezone=True)), sa.Column("active", sa.Boolean, nullable=False, server_default="true"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("tenant_id", "code", name="uq_print_stations_tenant_code"))
    op.create_index("ix_print_stations_tenant_active", "print_stations", ["tenant_id", "active"])
    op.create_table("print_printers", sa.Column("id", sa.String(36), primary_key=True), sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False), sa.Column("station_id", sa.String(36), sa.ForeignKey("print_stations.id", ondelete="RESTRICT"), nullable=False), sa.Column("code", sa.String(80), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("connection_type", sa.String(20), nullable=False, server_default="windows"), sa.Column("driver_name", sa.String(160)), sa.Column("status", sa.String(20), nullable=False, server_default="unknown"), sa.Column("printer_type", sa.String(20), nullable=False, server_default="standard"), sa.Column("capabilities", J, nullable=False, server_default="{}"), sa.Column("active", sa.Boolean, nullable=False, server_default="true"), sa.Column("last_seen_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("tenant_id", "station_id", "code", name="uq_print_printers_station_code"))
    op.create_index("ix_print_printers_tenant_active", "print_printers", ["tenant_id", "active"])
    op.create_table("print_routing_rules", sa.Column("id", sa.String(36), primary_key=True), sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False), sa.Column("sector", sa.String(40), nullable=False), sa.Column("document_type", sa.String(60), nullable=False), sa.Column("printer_id", sa.String(36), sa.ForeignKey("print_printers.id", ondelete="RESTRICT"), nullable=False), sa.Column("copies", sa.Integer, nullable=False, server_default="1"), sa.Column("priority", sa.Integer, nullable=False, server_default="0"), sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"), sa.Column("created_by_admin_id", sa.String, sa.ForeignKey("admin_users.id", ondelete="SET NULL")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("tenant_id", "sector", "document_type", "printer_id", name="uq_print_routing_rule"), sa.CheckConstraint("copies > 0 AND copies <= 20", name="ck_print_routing_rule_copies"))
    op.create_index("ix_print_routing_rules_tenant_sector", "print_routing_rules", ["tenant_id", "sector"])
    op.create_table("print_jobs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False), sa.Column("station_id", sa.String(36), sa.ForeignKey("print_stations.id", ondelete="RESTRICT")), sa.Column("printer_id", sa.String(36), sa.ForeignKey("print_printers.id", ondelete="RESTRICT"), nullable=False), sa.Column("external_job_id", sa.String(120), nullable=False), sa.Column("idempotency_key", sa.String(200), nullable=False), sa.Column("sector", sa.String(40), nullable=False), sa.Column("document_type", sa.String(60), nullable=False), sa.Column("document_format", sa.String(20), nullable=False), sa.Column("payload_ref", sa.String(1000), nullable=False), sa.Column("payload_metadata", J, nullable=False, server_default="{}"), sa.Column("copies", sa.Integer, nullable=False, server_default="1"), sa.Column("priority", sa.Integer, nullable=False, server_default="0"), sa.Column("status", sa.String(30), nullable=False, server_default="pending"), sa.Column("attempts", sa.Integer, nullable=False, server_default="0"), sa.Column("last_error", sa.Text), sa.Column("created_by_admin_id", sa.String, sa.ForeignKey("admin_users.id", ondelete="SET NULL")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_print_jobs_tenant_idempotency"), sa.UniqueConstraint("tenant_id", "external_job_id", name="uq_print_jobs_tenant_external_id"), sa.CheckConstraint("copies > 0 AND copies <= 20", name="ck_print_jobs_copies"), sa.CheckConstraint("status IN ('pending','received','queued','processing','spooler_submitted','printed','error','cancelled','uncertain')", name="ck_print_jobs_status"))
    op.create_index("ix_print_jobs_tenant_status_priority", "print_jobs", ["tenant_id", "status", "priority", "created_at"])
    op.create_table("print_job_events", sa.Column("id", sa.String(36), primary_key=True), sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False), sa.Column("job_id", sa.String(36), sa.ForeignKey("print_jobs.id", ondelete="CASCADE"), nullable=False), sa.Column("from_status", sa.String(30)), sa.Column("to_status", sa.String(30), nullable=False), sa.Column("message", sa.String(500)), sa.Column("actor_id", sa.String, sa.ForeignKey("admin_users.id", ondelete="SET NULL")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_print_job_events_tenant_job_created", "print_job_events", ["tenant_id", "job_id", "created_at"])

def downgrade():
    if not op.get_context().as_sql:
        has_history = op.get_bind().execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM print_stations) "
                "OR EXISTS (SELECT 1 FROM print_printers) "
                "OR EXISTS (SELECT 1 FROM print_routing_rules) "
                "OR EXISTS (SELECT 1 FROM print_jobs) "
                "OR EXISTS (SELECT 1 FROM print_job_events)"
            )
        ).scalar()
        if has_history:
            raise RuntimeError("Refusing to downgrade print_center because print history exists")

    op.drop_index("ix_print_job_events_tenant_job_created", table_name="print_job_events"); op.drop_table("print_job_events")
    op.drop_index("ix_print_jobs_tenant_status_priority", table_name="print_jobs"); op.drop_table("print_jobs")
    op.drop_index("ix_print_routing_rules_tenant_sector", table_name="print_routing_rules"); op.drop_table("print_routing_rules")
    op.drop_index("ix_print_printers_tenant_active", table_name="print_printers"); op.drop_table("print_printers")
    op.drop_index("ix_print_stations_tenant_active", table_name="print_stations"); op.drop_table("print_stations")

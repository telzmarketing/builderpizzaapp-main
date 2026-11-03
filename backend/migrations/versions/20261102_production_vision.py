"""Add the tenant-scoped Production Vision persistence slice."""
from alembic import op
import sqlalchemy as sa

revision = "20261102_production_vision"
down_revision = "20261101_kds_delivery_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("production_vision_cameras",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False), sa.Column("identifier", sa.String(80), nullable=False), sa.Column("manufacturer", sa.String(120)), sa.Column("model", sa.String(120)), sa.Column("ip_address", sa.String(120)), sa.Column("port", sa.Integer), sa.Column("protocol", sa.String(20), nullable=False, server_default="rtsp"), sa.Column("connection_url", sa.Text), sa.Column("username", sa.String(120)), sa.Column("credentials_encrypted", sa.Text), sa.Column("station_id", sa.String(20), nullable=False), sa.Column("resolution", sa.String(40)), sa.Column("orientation", sa.String(40)), sa.Column("installation_height_cm", sa.Integer), sa.Column("status", sa.String(12), nullable=False, server_default="inactive"), sa.Column("last_connected_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_production_vision_camera_status"))
    op.create_index("uq_production_vision_cameras_tenant_identifier", "production_vision_cameras", ["tenant_id", "identifier"], unique=True)
    op.create_index("ix_production_vision_cameras_tenant_station", "production_vision_cameras", ["tenant_id", "station_id"])
    op.create_table("production_vision_sessions",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False), sa.Column("production_unit_id", sa.String, nullable=False), sa.Column("stage", sa.String(40), nullable=False), sa.Column("operator_id", sa.String, sa.ForeignKey("admin_users.id", ondelete="SET NULL")), sa.Column("status", sa.String(12), nullable=False, server_default="active"), sa.Column("idempotency_key", sa.String(200)), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("expected_photo_count", sa.Integer, nullable=False, server_default="5"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id", "production_unit_id"], ["production_units.tenant_id", "production_units.id"], ondelete="RESTRICT"), sa.CheckConstraint("status IN ('active','complete','partial')", name="ck_production_vision_session_status"))
    op.create_index("uq_production_vision_sessions_tenant_id_id", "production_vision_sessions", ["tenant_id", "id"], unique=True)
    op.create_index("uq_production_vision_sessions_idempotency", "production_vision_sessions", ["tenant_id", "idempotency_key"], unique=True, postgresql_where=sa.text("idempotency_key IS NOT NULL"))
    op.create_index("ix_production_vision_sessions_tenant_status", "production_vision_sessions", ["tenant_id", "status", "started_at"])
    op.create_table("production_vision_photos",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False), sa.Column("session_id", sa.String(36), nullable=False), sa.Column("idempotency_key", sa.String(200), nullable=False), sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("original_storage_key", sa.Text, nullable=False), sa.Column("processed_storage_key", sa.Text), sa.Column("content_type", sa.String(120)), sa.Column("width", sa.Integer), sa.Column("height", sa.Integer), sa.Column("byte_size", sa.Integer), sa.Column("is_final", sa.Boolean, nullable=False, server_default=sa.false()), sa.Column("metadata_json", sa.JSON, nullable=False, server_default=sa.text("'{}'")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.ForeignKeyConstraint(["tenant_id", "session_id"], ["production_vision_sessions.tenant_id", "production_vision_sessions.id"], ondelete="RESTRICT"))
    op.create_index("uq_production_vision_photos_idempotency", "production_vision_photos", ["tenant_id", "session_id", "idempotency_key"], unique=True)
    op.create_index("ix_production_vision_photos_session_captured", "production_vision_photos", ["tenant_id", "session_id", "captured_at"])


def downgrade() -> None:
    op.drop_index("ix_production_vision_photos_session_captured", table_name="production_vision_photos")
    op.drop_index("uq_production_vision_photos_idempotency", table_name="production_vision_photos")
    op.drop_table("production_vision_photos")
    op.drop_index("ix_production_vision_sessions_tenant_status", table_name="production_vision_sessions")
    op.drop_index("uq_production_vision_sessions_idempotency", table_name="production_vision_sessions")
    op.drop_index("uq_production_vision_sessions_tenant_id_id", table_name="production_vision_sessions")
    op.drop_table("production_vision_sessions")
    op.drop_index("ix_production_vision_cameras_tenant_station", table_name="production_vision_cameras")
    op.drop_index("uq_production_vision_cameras_tenant_identifier", table_name="production_vision_cameras")
    op.drop_table("production_vision_cameras")

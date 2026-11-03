"""Complete Production Vision objects for databases with the original 20261102 layout.

This migration is deliberately additive.  The first Production Vision migration was
already applied in some environments before the expanded models were published, so
every DDL operation is guarded by PostgreSQL catalog inspection.
"""

from alembic import op
import sqlalchemy as sa


revision = "20261103_production_vision_expansion"
down_revision = "20261102_production_vision"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists(name):
    return _inspector().has_table(name)


def _column_exists(table, column):
    return any(item["name"] == column for item in _inspector().get_columns(table))


def _index_exists(table, name):
    return any(item["name"] == name for item in _inspector().get_indexes(table))


def _fk_exists(table, referred_table, local_columns):
    expected = tuple(local_columns)
    return any(
        fk.get("referred_table") == referred_table
        and tuple(fk.get("constrained_columns") or ()) == expected
        for fk in _inspector().get_foreign_keys(table)
    )


def _add_column(table, column):
    if not _column_exists(table, column.name):
        op.add_column(table, column)


def _add_index(name, table, columns, *, unique=False, where=None):
    if not _index_exists(table, name):
        kwargs = {"unique": unique}
        if where is not None:
            kwargs["postgresql_where"] = sa.text(where)
        op.create_index(name, table, columns, **kwargs)


def _add_fk(name, table, columns, referred_table, referred_columns, *, ondelete):
    if not _fk_exists(table, referred_table, columns):
        op.create_foreign_key(name, table, referred_table, columns, referred_columns, ondelete=ondelete)


def _create_tables():
    s = sa
    if not _table_exists("production_vision_settings"):
        op.create_table(
            "production_vision_settings",
            s.Column("id", s.String(36), primary_key=True),
            s.Column("tenant_id", s.String, s.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
            s.Column("photos_per_session", s.Integer, nullable=False, server_default="5"),
            s.Column("max_width_px", s.Integer, nullable=False, server_default="1280"),
            s.Column("image_format", s.String(10), nullable=False, server_default="webp"),
            s.Column("image_quality", s.Integer, nullable=False, server_default="80"),
            s.Column("retention_days", s.Integer, nullable=False, server_default="7"),
            s.Column("updated_at", s.DateTime(timezone=True), nullable=False, server_default=s.func.now()),
        )
    _add_index("uq_production_vision_settings_tenant", "production_vision_settings", ["tenant_id"], unique=True)

    if not _table_exists("production_vision_zones"):
        op.create_table(
            "production_vision_zones",
            s.Column("id", s.String(36), primary_key=True),
            s.Column("tenant_id", s.String, s.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
            s.Column("name", s.String(120), nullable=False),
            s.Column("identifier", s.String(80), nullable=False),
            s.Column("station_id", s.String(20), nullable=False),
            s.Column("camera_id", s.String(36), s.ForeignKey("production_vision_cameras.id", ondelete="SET NULL")),
            s.Column("status", s.String(12), nullable=False, server_default="active"),
            s.Column("created_at", s.DateTime(timezone=True), nullable=False, server_default=s.func.now()),
            s.Column("updated_at", s.DateTime(timezone=True), nullable=False, server_default=s.func.now()),
            s.CheckConstraint("status IN ('active','inactive')", name="ck_production_vision_zone_status"),
        )
    _add_index("uq_production_vision_zones_tenant_identifier", "production_vision_zones", ["tenant_id", "identifier"], unique=True)
    _add_index("ix_production_vision_zones_tenant_station", "production_vision_zones", ["tenant_id", "station_id"])

    if not _table_exists("production_vision_zone_occupancies"):
        op.create_table(
            "production_vision_zone_occupancies",
            s.Column("id", s.String(36), primary_key=True),
            s.Column("tenant_id", s.String, s.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
            s.Column("zone_id", s.String(36), nullable=False),
            s.Column("session_id", s.String(36), nullable=False),
            s.Column("idempotency_key", s.String(200), nullable=False),
            s.Column("occupied_at", s.DateTime(timezone=True), nullable=False, server_default=s.func.now()),
            s.Column("released_at", s.DateTime(timezone=True)),
            s.ForeignKeyConstraint(["tenant_id", "zone_id"], ["production_vision_zones.tenant_id", "production_vision_zones.id"], ondelete="RESTRICT"),
            s.ForeignKeyConstraint(["tenant_id", "session_id"], ["production_vision_sessions.tenant_id", "production_vision_sessions.id"], ondelete="RESTRICT"),
        )
    _add_index("uq_production_vision_zone_occupancy_idempotency", "production_vision_zone_occupancies", ["tenant_id", "idempotency_key"], unique=True)
    _add_index("uq_production_vision_zone_active", "production_vision_zone_occupancies", ["tenant_id", "zone_id"], unique=True, where="released_at IS NULL")

    if not _table_exists("production_vision_history_events"):
        op.create_table(
            "production_vision_history_events",
            s.Column("id", s.String(36), primary_key=True),
            s.Column("tenant_id", s.String, s.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
            s.Column("session_id", s.String(36)),
            s.Column("photo_id", s.String(36)),
            s.Column("event_type", s.String(60), nullable=False),
            s.Column("payload_json", s.JSON, nullable=False, server_default=s.text("'{}'")),
            s.Column("created_at", s.DateTime(timezone=True), nullable=False, server_default=s.func.now()),
            s.ForeignKeyConstraint(["tenant_id", "session_id"], ["production_vision_sessions.tenant_id", "production_vision_sessions.id"], ondelete="SET NULL"),
            s.ForeignKeyConstraint(["tenant_id", "photo_id"], ["production_vision_photos.tenant_id", "production_vision_photos.id"], ondelete="SET NULL"),
        )
    _add_index("ix_production_vision_history_session_created", "production_vision_history_events", ["tenant_id", "session_id", "created_at"])
    _add_index("ix_production_vision_history_photo_created", "production_vision_history_events", ["tenant_id", "photo_id", "created_at"])

    if not _table_exists("production_vision_incidents"):
        op.create_table(
            "production_vision_incidents",
            s.Column("id", s.String(36), primary_key=True),
            s.Column("tenant_id", s.String, s.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
            s.Column("session_id", s.String(36), s.ForeignKey("production_vision_sessions.id", ondelete="SET NULL")),
            s.Column("photo_id", s.String(36), s.ForeignKey("production_vision_photos.id", ondelete="SET NULL")),
            s.Column("zone_id", s.String(36), s.ForeignKey("production_vision_zones.id", ondelete="SET NULL")),
            s.Column("code", s.String(80), nullable=False),
            s.Column("message", s.Text, nullable=False),
            s.Column("status", s.String(12), nullable=False, server_default="open"),
            s.Column("details_json", s.JSON, nullable=False, server_default=s.text("'{}'")),
            s.Column("created_at", s.DateTime(timezone=True), nullable=False, server_default=s.func.now()),
            s.Column("resolved_at", s.DateTime(timezone=True)),
            s.CheckConstraint("status IN ('open','resolved')", name="ck_production_vision_incident_status"),
        )
    _add_index("ix_production_vision_incidents_tenant_status", "production_vision_incidents", ["tenant_id", "status", "created_at"])

    if not _table_exists("production_vision_evidence_holds"):
        op.create_table(
            "production_vision_evidence_holds",
            s.Column("id", s.String(36), primary_key=True),
            s.Column("tenant_id", s.String, s.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
            s.Column("hold_key", s.String(160), nullable=False),
            s.Column("session_id", s.String(36), s.ForeignKey("production_vision_sessions.id", ondelete="RESTRICT")),
            s.Column("photo_id", s.String(36), s.ForeignKey("production_vision_photos.id", ondelete="RESTRICT")),
            s.Column("reason", s.Text, nullable=False),
            s.Column("created_by", s.String, s.ForeignKey("admin_users.id", ondelete="SET NULL")),
            s.Column("created_at", s.DateTime(timezone=True), nullable=False, server_default=s.func.now()),
            s.Column("released_at", s.DateTime(timezone=True)),
        )
    _add_index("uq_production_vision_holds_tenant_key", "production_vision_evidence_holds", ["tenant_id", "hold_key"], unique=True)
    _add_index("ix_production_vision_holds_tenant_active", "production_vision_evidence_holds", ["tenant_id", "released_at"])


def upgrade() -> None:
    s = sa
    # These columns are nullable so existing 20261102 rows remain valid.
    _add_column("production_vision_sessions", s.Column("production_attempt_id", s.String))
    _add_column("production_vision_sessions", s.Column("station_id", s.String(20)))
    _add_column("production_vision_sessions", s.Column("camera_id", s.String(36)))
    _add_column("production_vision_sessions", s.Column("zone_id", s.String(36)))
    _add_column("production_vision_photos", s.Column("sha256", s.String(64)))
    _add_column("production_vision_photos", s.Column("processing_status", s.String(20), nullable=False, server_default="pending"))

    _create_tables()
    _add_fk("fk_production_vision_sessions_attempt", "production_vision_sessions", ["tenant_id", "production_attempt_id"], "production_attempts", ["tenant_id", "id"], ondelete="SET NULL")
    _add_fk("fk_production_vision_sessions_camera", "production_vision_sessions", ["camera_id"], "production_vision_cameras", ["id"], ondelete="SET NULL")
    _add_fk("fk_production_vision_sessions_zone", "production_vision_sessions", ["zone_id"], "production_vision_zones", ["id"], ondelete="SET NULL")


def downgrade() -> None:
    # Forward-only operational policy: the corrective migration is not reversed.
    pass

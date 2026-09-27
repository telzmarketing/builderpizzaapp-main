"""Add tenant dispatch labels, deterministic volumes, print audit and item snapshots.

Revision ID: 20260926_dispatch_labels
Revises: 20260924_kds_kitchen_dispatch
"""
from alembic import op
import sqlalchemy as sa


revision = "20260926_dispatch_labels"
down_revision = "20260924_kds_kitchen_dispatch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("order_items", sa.Column("position", sa.Integer(), nullable=True))
    op.add_column("order_items", sa.Column("add_ons", sa.JSON(), nullable=True))
    op.execute("""
        WITH ranked AS (
            SELECT id, row_number() OVER (PARTITION BY order_id ORDER BY id) - 1 AS item_position
            FROM order_items
        )
        UPDATE order_items oi SET position = ranked.item_position FROM ranked WHERE ranked.id = oi.id
    """)
    op.execute("UPDATE order_items SET add_ons = '[]'::json WHERE add_ons IS NULL")
    op.alter_column("order_items", "position", existing_type=sa.Integer(), nullable=False, server_default="0")
    op.alter_column("order_items", "add_ons", existing_type=sa.JSON(), nullable=False, server_default=sa.text("'[]'::json"))
    op.create_index("ix_order_items_order_position", "order_items", ["order_id", "position", "id"])

    op.create_table(
        "label_printers",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(250)),
        sa.Column("system_queue_hint", sa.String(200)),
        sa.Column("printer_type", sa.String(30), nullable=False, server_default="thermal"),
        sa.Column("connection_type", sa.String(30), nullable=False, server_default="browser"),
        sa.Column("manufacturer_model", sa.String(160)),
        sa.Column("network_host", sa.String(255)),
        sa.Column("network_port", sa.Integer()),
        sa.Column("protocol", sa.String(30)),
        sa.Column("max_width_mm", sa.Integer()),
        sa.Column("sector", sa.String(50), nullable=False, server_default="dispatch"),
        sa.Column("dpi", sa.Integer(), nullable=False, server_default="203"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "name", name="uq_label_printers_tenant_name"),
        sa.CheckConstraint("connection_type IN ('browser','network','installed','shared','local_service')", name="ck_label_printers_connection"),
        sa.CheckConstraint("network_port IS NULL OR (network_port >= 1 AND network_port <= 65535)", name="ck_label_printers_port"),
        sa.CheckConstraint("max_width_mm IS NULL OR (max_width_mm >= 20 AND max_width_mm <= 300)", name="ck_label_printers_max_width"),
    )
    op.create_index("ix_label_printers_tenant_active", "label_printers", ["tenant_id", "active"])

    op.create_table(
        "label_templates",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("label_type", sa.String(30), nullable=False, server_default="gap"),
        sa.Column("width_mm", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("height_mm", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("margin_top_mm", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("margin_right_mm", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("margin_bottom_mm", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("margin_left_mm", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("safe_area_mm", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("gap_mm", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("columns", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("labels_per_sheet", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("dpi", sa.Integer(), nullable=False, server_default="203"),
        sa.Column("scale_percent", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("default_copies", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("font_scale_percent", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("offset_x_mm", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("offset_y_mm", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rotation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("density", sa.Integer()),
        sa.Column("speed", sa.Integer()),
        sa.Column("orientation", sa.String(20), nullable=False, server_default="portrait"),
        sa.Column("show_logo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("show_printed_at", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "name", name="uq_label_templates_tenant_name"),
        sa.CheckConstraint("width_mm >= 20 AND width_mm <= 200", name="ck_label_templates_width"),
        sa.CheckConstraint("height_mm >= 20 AND height_mm <= 300", name="ck_label_templates_height"),
        sa.CheckConstraint("margin_top_mm BETWEEN 0 AND 20 AND margin_right_mm BETWEEN 0 AND 20 AND margin_bottom_mm BETWEEN 0 AND 20 AND margin_left_mm BETWEEN 0 AND 20", name="ck_label_templates_margins"),
        sa.CheckConstraint("dpi BETWEEN 72 AND 1200", name="ck_label_templates_dpi"),
        sa.CheckConstraint("scale_percent BETWEEN 50 AND 200 AND font_scale_percent BETWEEN 50 AND 200", name="ck_label_templates_scales"),
        sa.CheckConstraint("default_copies BETWEEN 1 AND 20", name="ck_label_templates_copies"),
        sa.CheckConstraint("columns BETWEEN 1 AND 10 AND labels_per_sheet BETWEEN 1 AND 100", name="ck_label_templates_layout"),
        sa.CheckConstraint("offset_x_mm BETWEEN -20 AND 20 AND offset_y_mm BETWEEN -20 AND 20", name="ck_label_templates_offsets"),
        sa.CheckConstraint("orientation IN ('portrait','landscape')", name="ck_label_templates_orientation"),
        sa.CheckConstraint("rotation IN (0,90,180,270)", name="ck_label_templates_rotation"),
        sa.CheckConstraint("label_type IN ('continuous','gap','black_mark','roll','sheet','seal','custom')", name="ck_label_templates_type"),
    )
    op.create_table(
        "label_printer_templates",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("printer_id", sa.String(), sa.ForeignKey("label_printers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_id", sa.String(), sa.ForeignKey("label_templates.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("tenant_id", "printer_id", "template_id", name="uq_label_printer_template"),
    )
    op.create_table(
        "label_settings",
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("include_drinks", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("require_reprint_reason", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("confirmation_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("batch_printing", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_printer_id", sa.String(), sa.ForeignKey("label_printers.id", ondelete="SET NULL")),
        sa.Column("default_template_id", sa.String(), sa.ForeignKey("label_templates.id", ondelete="SET NULL")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "label_volume_rules",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope_type", sa.String(20), nullable=False),
        sa.Column("scope_value", sa.String(200), nullable=False),
        sa.Column("volumes_per_unit", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "scope_type", "scope_value", name="uq_label_volume_rules_scope"),
        sa.CheckConstraint("scope_type IN ('product','category')", name="ck_label_volume_rules_scope"),
        sa.CheckConstraint("volumes_per_unit >= 0 AND volumes_per_unit <= 20", name="ck_label_volume_rules_count"),
    )
    op.create_table(
        "label_versions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("invalidated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "order_id", "version_number", name="uq_label_versions_order_number"),
    )
    op.create_table(
        "label_volumes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label_version_id", sa.String(), sa.ForeignKey("label_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_item_id", sa.String(), sa.ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("total_volumes", sa.Integer(), nullable=False),
        sa.Column("unit_index", sa.Integer(), nullable=False),
        sa.Column("volume_index", sa.Integer(), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint("tenant_id", "label_version_id", "sequence", name="uq_label_volumes_version_sequence"),
    )
    op.create_table(
        "label_print_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.id", ondelete="CASCADE")),
        sa.Column("label_version_id", sa.String(), sa.ForeignKey("label_versions.id", ondelete="SET NULL")),
        sa.Column("printer_id", sa.String(), sa.ForeignKey("label_printers.id", ondelete="SET NULL")),
        sa.Column("template_id", sa.String(), sa.ForeignKey("label_templates.id", ondelete="SET NULL")),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("job_type", sa.String(20), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("copies", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("reason", sa.String(500)),
        sa.Column("result_status", sa.String(30), nullable=False, server_default="requested"),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_label_print_jobs_idempotency"),
        sa.CheckConstraint("job_type IN ('print','reprint','test')", name="ck_label_print_jobs_type"),
        sa.CheckConstraint("result_status IN ('requested','dialog_opened')", name="ck_label_print_jobs_result"),
        sa.CheckConstraint("copies >= 1 AND copies <= 20", name="ck_label_print_jobs_copies"),
    )
    op.create_index("ix_label_print_jobs_tenant_order_created", "label_print_jobs", ["tenant_id", "order_id", "created_at"])

    op.execute("""
        INSERT INTO label_printers (id, tenant_id, name, description, printer_type, connection_type,
            max_width_mm, sector, dpi, active, is_default, created_at, updated_at)
        SELECT 'label-browser-' || md5(t.id), t.id, 'Impressao pelo navegador',
            'Fila fisica escolhida no dialogo do sistema operacional', 'thermal', 'browser',
            100, 'dispatch', 203, TRUE, TRUE, NOW(), NOW() FROM tenants t
    """)
    op.execute("""
        INSERT INTO label_templates (id, tenant_id, name, label_type, width_mm, height_mm,
            margin_top_mm, margin_right_mm, margin_bottom_mm, margin_left_mm, safe_area_mm,
            gap_mm, columns, labels_per_sheet, dpi, scale_percent, default_copies,
            font_scale_percent, offset_x_mm, offset_y_mm, rotation, orientation, show_logo,
            show_printed_at, active, is_default, created_at, updated_at)
        SELECT 'label-template-' || md5(t.id), t.id, 'Padrao 100x50 mm', 'gap', 100, 50,
            2, 2, 2, 2, 1, 2, 1, 1, 203, 100, 1, 100, 0, 0, 0, 'portrait',
            TRUE, TRUE, TRUE, TRUE, NOW(), NOW() FROM tenants t
    """)
    op.execute("""
        INSERT INTO label_printer_templates (id, tenant_id, printer_id, template_id)
        SELECT 'label-link-' || md5(t.id), t.id, 'label-browser-' || md5(t.id),
            'label-template-' || md5(t.id) FROM tenants t
    """)
    op.execute("""
        INSERT INTO label_settings (tenant_id, include_drinks, require_reprint_reason,
            confirmation_required, batch_printing, default_printer_id, default_template_id, updated_at)
        SELECT t.id, FALSE, TRUE, TRUE, FALSE, 'label-browser-' || md5(t.id),
            'label-template-' || md5(t.id), NOW() FROM tenants t
    """)


def downgrade() -> None:
    op.drop_index("ix_label_print_jobs_tenant_order_created", table_name="label_print_jobs")
    op.drop_table("label_print_jobs")
    op.drop_table("label_volumes")
    op.drop_table("label_versions")
    op.drop_table("label_volume_rules")
    op.drop_table("label_settings")
    op.drop_table("label_printer_templates")
    op.drop_table("label_templates")
    op.drop_index("ix_label_printers_tenant_active", table_name="label_printers")
    op.drop_table("label_printers")
    op.drop_index("ix_order_items_order_position", table_name="order_items")
    op.drop_column("order_items", "add_ons")
    op.drop_column("order_items", "position")

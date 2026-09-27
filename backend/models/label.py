"""Tenant-scoped dispatch label configuration and immutable print audit."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint

from backend.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class LabelPrinter(Base):
    __tablename__ = "label_printers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_label_printers_tenant_name"),
        Index("ix_label_printers_tenant_active", "tenant_id", "active"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(String(250), nullable=True)
    system_queue_hint = Column(String(200), nullable=True)
    printer_type = Column(String(30), nullable=False, default="thermal")
    connection_type = Column(String(30), nullable=False, default="browser")
    manufacturer_model = Column(String(160), nullable=True)
    network_host = Column(String(255), nullable=True)
    network_port = Column(Integer, nullable=True)
    protocol = Column(String(30), nullable=True)
    max_width_mm = Column(Integer, nullable=True)
    sector = Column(String(50), nullable=False, default="dispatch")
    dpi = Column(Integer, nullable=False, default=203)
    active = Column(Boolean, nullable=False, default=True)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class LabelTemplate(Base):
    __tablename__ = "label_templates"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_label_templates_tenant_name"),
        CheckConstraint("width_mm >= 20 AND width_mm <= 200", name="ck_label_templates_width"),
        CheckConstraint("height_mm >= 20 AND height_mm <= 300", name="ck_label_templates_height"),
        CheckConstraint("margin_top_mm BETWEEN 0 AND 20 AND margin_right_mm BETWEEN 0 AND 20 AND margin_bottom_mm BETWEEN 0 AND 20 AND margin_left_mm BETWEEN 0 AND 20", name="ck_label_templates_margins"),
        CheckConstraint("dpi BETWEEN 72 AND 1200", name="ck_label_templates_dpi"),
        CheckConstraint("scale_percent BETWEEN 50 AND 200 AND font_scale_percent BETWEEN 50 AND 200", name="ck_label_templates_scales"),
        CheckConstraint("default_copies BETWEEN 1 AND 20", name="ck_label_templates_copies"),
        CheckConstraint("columns BETWEEN 1 AND 10 AND labels_per_sheet BETWEEN 1 AND 100", name="ck_label_templates_layout"),
        CheckConstraint("offset_x_mm BETWEEN -20 AND 20 AND offset_y_mm BETWEEN -20 AND 20", name="ck_label_templates_offsets"),
        CheckConstraint("orientation IN ('portrait','landscape')", name="ck_label_templates_orientation"),
        CheckConstraint("rotation IN (0,90,180,270)", name="ck_label_templates_rotation"),
        CheckConstraint("label_type IN ('continuous','gap','black_mark','roll','sheet','seal','custom')", name="ck_label_templates_type"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(120), nullable=False)
    label_type = Column(String(30), nullable=False, default="gap")
    width_mm = Column(Integer, nullable=False, default=100)
    height_mm = Column(Integer, nullable=False, default=50)
    margin_top_mm = Column(Integer, nullable=False, default=2)
    margin_right_mm = Column(Integer, nullable=False, default=2)
    margin_bottom_mm = Column(Integer, nullable=False, default=2)
    margin_left_mm = Column(Integer, nullable=False, default=2)
    safe_area_mm = Column(Integer, nullable=False, default=1)
    gap_mm = Column(Integer, nullable=False, default=2)
    columns = Column(Integer, nullable=False, default=1)
    labels_per_sheet = Column(Integer, nullable=False, default=1)
    dpi = Column(Integer, nullable=False, default=203)
    scale_percent = Column(Integer, nullable=False, default=100)
    default_copies = Column(Integer, nullable=False, default=1)
    font_scale_percent = Column(Integer, nullable=False, default=100)
    offset_x_mm = Column(Integer, nullable=False, default=0)
    offset_y_mm = Column(Integer, nullable=False, default=0)
    rotation = Column(Integer, nullable=False, default=0)
    density = Column(Integer, nullable=True)
    speed = Column(Integer, nullable=True)
    orientation = Column(String(20), nullable=False, default="portrait")
    show_logo = Column(Boolean, nullable=False, default=True)
    show_printed_at = Column(Boolean, nullable=False, default=True)
    active = Column(Boolean, nullable=False, default=True)
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class LabelPrinterTemplate(Base):
    __tablename__ = "label_printer_templates"
    __table_args__ = (UniqueConstraint("tenant_id", "printer_id", "template_id", name="uq_label_printer_template"),)
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    printer_id = Column(String, ForeignKey("label_printers.id", ondelete="CASCADE"), nullable=False)
    template_id = Column(String, ForeignKey("label_templates.id", ondelete="CASCADE"), nullable=False)


class LabelSetting(Base):
    __tablename__ = "label_settings"
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    include_drinks = Column(Boolean, nullable=False, default=False)
    require_reprint_reason = Column(Boolean, nullable=False, default=True)
    confirmation_required = Column(Boolean, nullable=False, default=True)
    batch_printing = Column(Boolean, nullable=False, default=False)
    default_printer_id = Column(String, ForeignKey("label_printers.id", ondelete="SET NULL"), nullable=True)
    default_template_id = Column(String, ForeignKey("label_templates.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class LabelVolumeRule(Base):
    __tablename__ = "label_volume_rules"
    __table_args__ = (
        CheckConstraint("scope_type IN ('product','category')", name="ck_label_volume_rules_scope"),
        CheckConstraint("volumes_per_unit >= 0 AND volumes_per_unit <= 20", name="ck_label_volume_rules_count"),
        UniqueConstraint("tenant_id", "scope_type", "scope_value", name="uq_label_volume_rules_scope"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    scope_type = Column(String(20), nullable=False)
    scope_value = Column(String(200), nullable=False)
    volumes_per_unit = Column(Integer, nullable=False, default=1)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class LabelVersion(Base):
    __tablename__ = "label_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "order_id", "version_number", name="uq_label_versions_order_number"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(String, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    fingerprint = Column(String(64), nullable=False)
    snapshot_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    invalidated_at = Column(DateTime(timezone=True), nullable=True)


class LabelVolume(Base):
    __tablename__ = "label_volumes"
    __table_args__ = (UniqueConstraint("tenant_id", "label_version_id", "sequence", name="uq_label_volumes_version_sequence"),)
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    label_version_id = Column(String, ForeignKey("label_versions.id", ondelete="CASCADE"), nullable=False)
    order_item_id = Column(String, ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False)
    sequence = Column(Integer, nullable=False)
    total_volumes = Column(Integer, nullable=False)
    unit_index = Column(Integer, nullable=False)
    volume_index = Column(Integer, nullable=False)
    content_json = Column(JSON, nullable=False)


class LabelPrintJob(Base):
    __tablename__ = "label_print_jobs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_label_print_jobs_idempotency"),
        CheckConstraint("job_type IN ('print','reprint','test')", name="ck_label_print_jobs_type"),
        CheckConstraint("result_status IN ('requested','dialog_opened')", name="ck_label_print_jobs_result"),
        CheckConstraint("copies >= 1 AND copies <= 20", name="ck_label_print_jobs_copies"),
        Index("ix_label_print_jobs_tenant_order_created", "tenant_id", "order_id", "created_at"),
    )
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    order_id = Column(String, ForeignKey("orders.id", ondelete="CASCADE"), nullable=True)
    label_version_id = Column(String, ForeignKey("label_versions.id", ondelete="SET NULL"), nullable=True)
    printer_id = Column(String, ForeignKey("label_printers.id", ondelete="SET NULL"), nullable=True)
    template_id = Column(String, ForeignKey("label_templates.id", ondelete="SET NULL"), nullable=True)
    actor_id = Column(String, nullable=False)
    job_type = Column(String(20), nullable=False)
    idempotency_key = Column(String(100), nullable=False)
    copies = Column(Integer, nullable=False, default=1)
    reason = Column(String(500), nullable=True)
    result_status = Column(String(30), nullable=False, default="requested")
    snapshot_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

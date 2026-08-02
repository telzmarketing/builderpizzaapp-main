"""Add the first complete Master Central commercial core.

Revision ID: 20260815_master_central_core
Revises: 20260814_merge_all_heads
"""
from alembic import op
import sqlalchemy as sa

revision = "20260815_master_central_core"
down_revision = "20260814_merge_all_heads"
branch_labels = None
depends_on = None


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def upgrade() -> None:
    op.create_table(
        "tenant_profiles",
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("trade_name", sa.String(200)), sa.Column("tax_id", sa.String(30)),
        sa.Column("state_registration", sa.String(40)),
        sa.Column("municipal_registration", sa.String(40)),
        sa.Column("website", sa.String(250)),
        sa.Column("legal_representative_name", sa.String(200)),
        sa.Column("legal_representative_email", sa.String(200)),
        sa.Column("legal_representative_phone", sa.String(30)),
        sa.Column("email", sa.String(200)), sa.Column("phone", sa.String(30)),
        sa.Column("address_line", sa.String(250)), sa.Column("address_number", sa.String(30)),
        sa.Column("address_extra", sa.String(120)), sa.Column("neighborhood", sa.String(120)),
        sa.Column("city", sa.String(120)), sa.Column("state", sa.String(2)),
        sa.Column("postal_code", sa.String(20)),
        sa.Column("configuration_status", sa.String(30), nullable=False, server_default="ready"),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        *_timestamps(),
    )
    op.create_index("ix_tenant_profiles_tax_id", "tenant_profiles", ["tax_id"])

    op.create_table(
        "saas_plans",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(160), nullable=False), sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("billing_cycle", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("grace_period_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("auto_renew_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("price", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("max_users", sa.Integer()), sa.Column("max_stores", sa.Integer()),
        sa.Column("max_orders", sa.Integer()), sa.Column("max_storage_mb", sa.Integer()),
        sa.Column("max_whatsapp_instances", sa.Integer()), sa.Column("support_level", sa.String(80)),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        *_timestamps(), sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("key", name="uq_saas_plans_key"),
        sa.CheckConstraint("status IN ('active','inactive','archived')", name="ck_saas_plans_status"),
        sa.CheckConstraint("billing_cycle IN ('monthly','quarterly','semiannual','annual','custom')", name="ck_saas_plans_cycle"),
    )
    op.create_index("ix_saas_plans_status", "saas_plans", ["status"])

    op.create_table(
        "saas_modules",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(160), nullable=False), sa.Column("description", sa.Text()),
        sa.Column("module_group", sa.String(30), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dependencies_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("default_config_json", sa.Text(), nullable=False, server_default="{}"),
        *_timestamps(), sa.UniqueConstraint("key", name="uq_saas_modules_key"),
        sa.CheckConstraint("module_group IN ('operation','delivery','management','marketing','crm','integrations')", name="ck_saas_modules_group"),
    )
    op.create_index("ix_saas_modules_module_group", "saas_modules", ["module_group"])

    op.create_table(
        "saas_plan_modules",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("plan_id", sa.String(), sa.ForeignKey("saas_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_id", sa.String(), sa.ForeignKey("saas_modules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("limit_value", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("plan_id", "module_id", name="uq_saas_plan_modules_plan_module"),
    )
    op.create_index("ix_saas_plan_modules_module_id", "saas_plan_modules", ["module_id"])

    op.create_table(
        "tenant_subscriptions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.String(), sa.ForeignKey("saas_plans.id", ondelete="RESTRICT")),
        sa.Column("status", sa.String(20), nullable=False, server_default="trial"),
        sa.Column("custom_terms_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True)), *_timestamps(),
        sa.CheckConstraint("status IN ('trial','active','suspended','cancelled')", name="ck_tenant_subscriptions_status"),
    )
    op.create_index("ix_tenant_subscriptions_tenant_id", "tenant_subscriptions", ["tenant_id"])
    op.create_index("ix_tenant_subscriptions_plan_id", "tenant_subscriptions", ["plan_id"])
    op.create_index("uq_tenant_subscriptions_current", "tenant_subscriptions", ["tenant_id"], unique=True, postgresql_where=sa.text("ended_at IS NULL"))

    op.create_table(
        "tenant_licenses",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="trial"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True)), sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("grace_period_ends_at", sa.DateTime(timezone=True)),
        sa.Column("billing_cycle", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("grace_period_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("suspended_at", sa.DateTime(timezone=True)), sa.Column("suspension_reason", sa.Text()),
        sa.Column("blocked_at", sa.DateTime(timezone=True)), sa.Column("block_reason", sa.Text()),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)), sa.Column("cancellation_reason", sa.Text()),
        *_timestamps(), sa.UniqueConstraint("tenant_id", name="uq_tenant_licenses_tenant"),
        sa.CheckConstraint("status IN ('trial','active','grace_period','expired','suspended','blocked','cancelled')", name="ck_tenant_licenses_status"),
    )
    op.create_index("ix_tenant_licenses_status", "tenant_licenses", ["status"])

    op.create_table(
        "tenant_license_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("license_id", sa.String(), sa.ForeignKey("tenant_licenses.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_user_id", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(50), nullable=False), sa.Column("previous_status", sa.String(20)),
        sa.Column("new_status", sa.String(20), nullable=False), sa.Column("reason", sa.Text()),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tenant_license_events_tenant_created", "tenant_license_events", ["tenant_id", "created_at"])

    op.create_table(
        "tenant_modules",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module_id", sa.String(), sa.ForeignKey("saas_modules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("origin", sa.String(20), nullable=False, server_default="plan"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ends_at", sa.DateTime(timezone=True)), sa.Column("limit_value", sa.Integer()),
        sa.Column("additional_price", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("block_reason", sa.Text()), sa.Column("config_json", sa.Text(), nullable=False, server_default="{}"),
        *_timestamps(), sa.UniqueConstraint("tenant_id", "module_id", name="uq_tenant_modules_tenant_module"),
        sa.CheckConstraint("origin IN ('plan','addon','courtesy','trial')", name="ck_tenant_modules_origin"),
    )
    op.create_index("ix_tenant_modules_module_id", "tenant_modules", ["module_id"])

    op.create_table(
        "tenant_billing_profiles",
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("billing_name", sa.String(200)), sa.Column("tax_id", sa.String(30)),
        sa.Column("email", sa.String(200)), sa.Column("phone", sa.String(30)),
        sa.Column("notes", sa.Text()), *_timestamps(),
    )
    op.create_table(
        "saas_invoices",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_id", sa.String(), sa.ForeignKey("saas_plans.id", ondelete="SET NULL")),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("base_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("additions_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("discount_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("payment_method", sa.String(40)), sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()), *_timestamps(),
        sa.CheckConstraint("status IN ('draft','pending','paid','overdue','cancelled','refunded','negotiated','courtesy')", name="ck_saas_invoices_status"),
        sa.CheckConstraint("base_amount >= 0 AND additions_amount >= 0 AND discount_amount >= 0 AND total_amount >= 0", name="ck_saas_invoices_amounts"),
        sa.CheckConstraint("period_end > period_start", name="ck_saas_invoices_period"),
    )
    op.create_index("ix_saas_invoices_tenant_status_due", "saas_invoices", ["tenant_id", "status", "due_at"])
    op.create_table(
        "saas_invoice_items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("invoice_id", sa.String(), sa.ForeignKey("saas_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.String(250), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_amount", sa.Numeric(18, 2), nullable=False), sa.Column("total_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.CheckConstraint("quantity > 0 AND unit_amount >= 0 AND total_amount >= 0", name="ck_saas_invoice_items_amounts"),
    )
    op.create_index("ix_saas_invoice_items_invoice_id", "saas_invoice_items", ["invoice_id"])
    op.create_table(
        "saas_payments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", sa.String(), sa.ForeignKey("saas_invoices.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False), sa.Column("payment_method", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="registered"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False), sa.Column("reference", sa.String(160)),
        sa.Column("notes", sa.Text()), sa.Column("registered_by", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('registered','confirmed','cancelled','refunded')", name="ck_saas_payments_status"),
        sa.CheckConstraint("amount > 0", name="ck_saas_payments_amount"),
    )
    op.create_index("ix_saas_payments_invoice_id", "saas_payments", ["invoice_id"])
    op.create_index("ix_saas_payments_tenant_paid", "saas_payments", ["tenant_id", "paid_at"])
    op.create_index(
        "uq_saas_payments_tenant_reference", "saas_payments",
        ["tenant_id", "reference"], unique=True,
        postgresql_where=sa.text("reference IS NOT NULL"),
    )

    op.create_table(
        "support_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_user_id", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL")),
        sa.Column("reason", sa.Text(), nullable=False), sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("ip_address", sa.String(50)), sa.Column("user_agent", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active','ended','expired','revoked')", name="ck_support_sessions_status"),
    )
    op.create_index("ix_support_sessions_actor_status", "support_sessions", ["actor_user_id", "status"])
    op.create_index("ix_support_sessions_tenant_status", "support_sessions", ["tenant_id", "status"])

    op.create_table(
        "tenant_usage_metrics",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_key", sa.String(80), nullable=False), sa.Column("period_key", sa.String(20), nullable=False),
        sa.Column("value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "metric_key", "period_key", name="uq_tenant_usage_metric_period"),
    )
    op.create_table(
        "tenant_internal_notes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_user_id", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL")),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_tenant_internal_notes_tenant_id", "tenant_internal_notes", ["tenant_id"])

    op.drop_constraint("ck_tenant_domains_status", "tenant_domains", type_="check")
    op.create_check_constraint(
        "ck_tenant_domains_status", "tenant_domains",
        "status IN ('pending','awaiting_dns','verifying','verified','active','dns_error','ssl_error','suspended','removed')",
    )
    for column in (
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("expected_txt_record", sa.String(500)), sa.Column("expected_cname", sa.String(500)),
        sa.Column("suspended_at", sa.DateTime(timezone=True)), sa.Column("removed_at", sa.DateTime(timezone=True)),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("ssl_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("ssl_issued_at", sa.DateTime(timezone=True)), sa.Column("ssl_expires_at", sa.DateTime(timezone=True)),
        sa.Column("error_message", sa.Text()),
    ):
        op.add_column("tenant_domains", column)
    op.create_index("uq_tenant_domains_primary_active", "tenant_domains", ["tenant_id"], unique=True, postgresql_where=sa.text("is_primary = true AND status = 'active'"))

    op.add_column("platform_audit_logs", sa.Column("actor_type", sa.String(30), nullable=False, server_default="platform_user"))
    op.add_column("platform_audit_logs", sa.Column("before_data", sa.Text()))
    op.add_column("platform_audit_logs", sa.Column("after_data", sa.Text()))
    op.add_column("platform_audit_logs", sa.Column("reason", sa.Text()))
    op.add_column(
        "admin_users",
        sa.Column("force_password_change", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("admin_users", "force_password_change")
    op.drop_column("platform_audit_logs", "reason")
    op.drop_column("platform_audit_logs", "after_data")
    op.drop_column("platform_audit_logs", "before_data")
    op.drop_column("platform_audit_logs", "actor_type")
    op.drop_index("uq_tenant_domains_primary_active", table_name="tenant_domains")
    op.execute(
        "UPDATE tenant_domains SET status='pending', is_primary=false "
        "WHERE status NOT IN ('pending','verified','active')"
    )
    for name in ("error_message", "ssl_expires_at", "ssl_issued_at", "ssl_status", "last_checked_at", "removed_at", "suspended_at", "expected_cname", "expected_txt_record", "is_primary"):
        op.drop_column("tenant_domains", name)
    op.drop_constraint("ck_tenant_domains_status", "tenant_domains", type_="check")
    op.create_check_constraint("ck_tenant_domains_status", "tenant_domains", "status IN ('pending','verified','active')")
    for table_name, index_names in (
        ("tenant_internal_notes", ("ix_tenant_internal_notes_tenant_id",)),
        (
            "support_sessions",
            ("ix_support_sessions_tenant_status", "ix_support_sessions_actor_status"),
        ),
        (
            "saas_payments",
            (
                "uq_saas_payments_tenant_reference",
                "ix_saas_payments_tenant_paid",
                "ix_saas_payments_invoice_id",
            ),
        ),
        ("saas_invoice_items", ("ix_saas_invoice_items_invoice_id",)),
        ("saas_invoices", ("ix_saas_invoices_tenant_status_due",)),
        (
            "tenant_modules",
            ("ix_tenant_modules_module_id",),
        ),
        ("tenant_license_events", ("ix_tenant_license_events_tenant_created",)),
        (
            "tenant_licenses",
            ("ix_tenant_licenses_status",),
        ),
        (
            "tenant_subscriptions",
            (
                "uq_tenant_subscriptions_current",
                "ix_tenant_subscriptions_plan_id",
                "ix_tenant_subscriptions_tenant_id",
            ),
        ),
        (
            "saas_plan_modules",
            ("ix_saas_plan_modules_module_id",),
        ),
        (
            "saas_modules",
            ("ix_saas_modules_module_group",),
        ),
        ("saas_plans", ("ix_saas_plans_status",)),
        ("tenant_profiles", ("ix_tenant_profiles_tax_id",)),
    ):
        for index_name in index_names:
            op.drop_index(index_name, table_name=table_name)
    for table in (
        "tenant_internal_notes", "tenant_usage_metrics", "support_sessions", "saas_payments",
        "saas_invoice_items", "saas_invoices", "tenant_billing_profiles", "tenant_modules",
        "tenant_license_events", "tenant_licenses", "tenant_subscriptions",
        "saas_plan_modules", "saas_modules", "saas_plans", "tenant_profiles",
    ):
        op.drop_table(table)

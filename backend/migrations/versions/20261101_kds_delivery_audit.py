"""Add tenant-scoped KDS delivery audit aggregate."""
from alembic import op
import sqlalchemy as sa

revision = "20261101_kds_delivery_audit"
down_revision = "20261101_silent_label_print_queue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("delivery_audits",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", sa.String(), sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False), sa.Column("delivery_id", sa.String(), sa.ForeignKey("deliveries.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"), sa.Column("started_by_admin_id", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL")), sa.Column("handoff_by_admin_id", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("handoff_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "order_id", name="uq_delivery_audits_tenant_order"), sa.CheckConstraint("status IN ('in_progress','completed','divergent')", name="ck_delivery_audits_status"))
    op.create_index("ix_delivery_audits_tenant_status", "delivery_audits", ["tenant_id", "status", "created_at"])
    op.create_table("delivery_audit_item_confirmations",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("audit_id", sa.String(), sa.ForeignKey("delivery_audits.id", ondelete="CASCADE"), nullable=False), sa.Column("order_item_id", sa.String(), sa.ForeignKey("order_items.id", ondelete="RESTRICT"), nullable=False), sa.Column("expected_quantity", sa.Integer(), nullable=False), sa.Column("confirmed_quantity", sa.Integer(), nullable=False, server_default="0"), sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("actor_id", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL")), sa.Column("confirmed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("tenant_id", "audit_id", "order_item_id", name="uq_delivery_audit_items_item"))
    op.create_index("ix_delivery_audit_items_tenant_audit", "delivery_audit_item_confirmations", ["tenant_id", "audit_id"])
    op.create_table("delivery_audit_volumes",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("audit_id", sa.String(), sa.ForeignKey("delivery_audits.id", ondelete="CASCADE"), nullable=False), sa.Column("order_item_id", sa.String(), sa.ForeignKey("order_items.id", ondelete="RESTRICT"), nullable=False), sa.Column("label_volume_id", sa.String(), sa.ForeignKey("label_volumes.id", ondelete="SET NULL")), sa.Column("sequence", sa.Integer(), nullable=False), sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("actor_id", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL")), sa.Column("confirmed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("tenant_id", "audit_id", "sequence", name="uq_delivery_audit_volumes_sequence"))
    op.create_index("ix_delivery_audit_volumes_tenant_audit", "delivery_audit_volumes", ["tenant_id", "audit_id"])
    op.create_table("delivery_audit_evidence",
        sa.Column("id", sa.String(), primary_key=True), sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False), sa.Column("audit_id", sa.String(), sa.ForeignKey("delivery_audits.id", ondelete="CASCADE"), nullable=False), sa.Column("asset_id", sa.String(), sa.ForeignKey("tenant_upload_assets.id", ondelete="RESTRICT"), nullable=False), sa.Column("evidence_type", sa.String(40), nullable=False, server_default="handoff"), sa.Column("captured_at", sa.DateTime(timezone=True)), sa.Column("actor_id", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL")), sa.Column("metadata_json", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("tenant_id", "audit_id", "asset_id", name="uq_delivery_audit_evidence_asset"))
    op.create_index("ix_delivery_audit_evidence_tenant_audit", "delivery_audit_evidence", ["tenant_id", "audit_id", "created_at"])
    op.execute("""INSERT INTO rbac_modules (id,key,name,description,order_index,is_active,created_at) VALUES ('rbac-module-kds-auditoria','kds_auditoria','KDS Auditoria','Auditoria final e transferencia ao entregador',29,TRUE,NOW()) ON CONFLICT (key) DO UPDATE SET is_active=TRUE""")
    op.execute("""INSERT INTO role_permissions (id,tenant_id,role_id,module_id,permission_id,allowed) SELECT 'kds-auditoria-rp-' || md5(r.id || m.id || p.id),r.tenant_id,r.id,m.id,p.id,TRUE FROM roles r CROSS JOIN rbac_modules m CROSS JOIN rbac_permissions p WHERE lower(r.name) IN ('master','administrador','gerente','expedicao') AND m.key='kds_auditoria' AND p.key IN ('view','edit') ON CONFLICT DO NOTHING""")


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE module_id = (SELECT id FROM rbac_modules WHERE key='kds_auditoria')")
    op.execute("DELETE FROM rbac_modules WHERE key='kds_auditoria'")
    op.drop_index("ix_delivery_audit_evidence_tenant_audit", table_name="delivery_audit_evidence"); op.drop_table("delivery_audit_evidence")
    op.drop_index("ix_delivery_audit_volumes_tenant_audit", table_name="delivery_audit_volumes"); op.drop_table("delivery_audit_volumes")
    op.drop_index("ix_delivery_audit_items_tenant_audit", table_name="delivery_audit_item_confirmations"); op.drop_table("delivery_audit_item_confirmations")
    op.drop_index("ix_delivery_audits_tenant_status", table_name="delivery_audits"); op.drop_table("delivery_audits")

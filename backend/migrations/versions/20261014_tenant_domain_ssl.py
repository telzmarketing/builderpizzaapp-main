"""Persistent fenced certificate queue for the unprivileged Master API."""
from alembic import op
import sqlalchemy as sa

revision = "20261014_tenant_domain_ssl"
down_revision = "20261014_order_cancellation_tracking"
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint("uq_tenant_domains_id_tenant", "tenant_domains", ["id", "tenant_id"])
    op.create_table(
        "tenant_domain_certificate_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("domain_id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("hostname", sa.String(253), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("requested_by", sa.String(), sa.ForeignKey("admin_users.id", ondelete="SET NULL")),
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_token_hash", sa.String(64)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(50)),
        sa.Column("certificate_fingerprint", sa.String(64)),
        sa.Column("certificate_issued_at", sa.DateTime(timezone=True)),
        sa.Column("certificate_expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["domain_id", "tenant_id"], ["tenant_domains.id", "tenant_domains.tenant_id"], ondelete="RESTRICT", name="fk_domain_ssl_job_owner"),
        sa.CheckConstraint("status IN ('queued','running','succeeded','failed','cancelled')", name="ck_domain_ssl_job_status"),
        sa.CheckConstraint("attempts >= 0", name="ck_domain_ssl_job_attempts"),
        sa.UniqueConstraint("domain_id", "idempotency_key_hash", name="uq_domain_ssl_job_request"),
    )
    op.create_index("uq_domain_ssl_job_open", "tenant_domain_certificate_jobs", ["domain_id"], unique=True, postgresql_where=sa.text("status IN ('queued','running')"))
    op.create_index("ix_domain_ssl_job_queue", "tenant_domain_certificate_jobs", ["status", "created_at"])
    op.create_index("ix_domain_ssl_job_tenant_created", "tenant_domain_certificate_jobs", ["tenant_id", "created_at"])


def downgrade():
    raise RuntimeError("Tenant domain SSL is forward-only; certificate requests and consent history must be preserved.")

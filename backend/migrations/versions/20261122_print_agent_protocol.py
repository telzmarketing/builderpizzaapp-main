"""Add tenant-scoped Windows print-agent pairing and credentials."""
from alembic import op
import sqlalchemy as sa

revision = "20261122_print_agent_protocol"
down_revision = "20261121_print_center"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "print_agent_pairings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("station_id", sa.String(36), sa.ForeignKey("print_stations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_admin_id", sa.String, sa.ForeignKey("admin_users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "code_hash", name="uq_print_agent_pairings_tenant_code_hash"),
    )
    op.create_index(
        "ix_print_agent_pairings_tenant_station_active", "print_agent_pairings",
        ["tenant_id", "station_id", "used_at", "expires_at"],
    )
    op.create_table(
        "print_agent_credentials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String, sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("station_id", sa.String(36), sa.ForeignKey("print_stations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("agent_version", sa.String(80)),
        sa.Column("hostname", sa.String(255)),
        sa.Column("last_ip", sa.String(64)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "station_id", name="uq_print_agent_credentials_tenant_station"),
        sa.UniqueConstraint("tenant_id", "token_hash", name="uq_print_agent_credentials_tenant_token_hash"),
    )
    op.create_index(
        "ix_print_agent_credentials_tenant_active", "print_agent_credentials",
        ["tenant_id", "revoked_at", "last_seen_at"],
    )


def downgrade():
    op.drop_index("ix_print_agent_credentials_tenant_active", table_name="print_agent_credentials")
    op.drop_table("print_agent_credentials")
    op.drop_index("ix_print_agent_pairings_tenant_station_active", table_name="print_agent_pairings")
    op.drop_table("print_agent_pairings")

"""Add tenant-scoped Gestor multimodal artifacts and audit events."""
from alembic import op
import sqlalchemy as sa


revision = "20261028_gestor_multimodal"
down_revision = "20261028_gestor_whatsapp_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gestor_multimodal_artifacts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("uploaded_by_admin_id", sa.String(), nullable=True),
        sa.Column("storage_asset_id", sa.String(length=32), nullable=True),
        sa.Column("media_type", sa.String(length=20), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=700), nullable=True),
        sa.Column("idempotency_key", sa.String(length=220), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="received"),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("processor", sa.String(length=80), nullable=True),
        sa.Column("source_message_id", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_admin_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["storage_asset_id"], ["tenant_upload_assets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key", name="uq_gestor_multimodal_tenant_idempotency"),
    )
    op.create_index(
        "ix_gestor_multimodal_tenant_status_created",
        "gestor_multimodal_artifacts", ["tenant_id", "status", "created_at"],
    )
    op.create_index(
        "ix_gestor_multimodal_tenant_hash",
        "gestor_multimodal_artifacts", ["tenant_id", "content_sha256"],
    )

    op.create_table(
        "gestor_multimodal_audits",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("artifact_id", sa.String(), nullable=False),
        sa.Column("actor_admin_id", sa.String(), nullable=True),
        sa.Column("event", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["artifact_id"], ["gestor_multimodal_artifacts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_admin_id"], ["admin_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_gestor_multimodal_audits_tenant_created",
        "gestor_multimodal_audits", ["tenant_id", "created_at"],
    )
    op.create_index(
        "ix_gestor_multimodal_audits_artifact_created",
        "gestor_multimodal_audits", ["artifact_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_gestor_multimodal_audits_artifact_created", table_name="gestor_multimodal_audits")
    op.drop_index("ix_gestor_multimodal_audits_tenant_created", table_name="gestor_multimodal_audits")
    op.drop_table("gestor_multimodal_audits")
    op.drop_index("ix_gestor_multimodal_tenant_hash", table_name="gestor_multimodal_artifacts")
    op.drop_index("ix_gestor_multimodal_tenant_status_created", table_name="gestor_multimodal_artifacts")
    op.drop_table("gestor_multimodal_artifacts")

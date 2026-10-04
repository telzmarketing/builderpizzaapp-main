"""Bind Meta webhook credentials to one tenant-owned WhatsApp number.

Revision ID: 20261003_whatsapp_meta_webhook_tenant_keys
Revises: 20261003_marketing_tenant_keys
"""
from __future__ import annotations

import hashlib
import json

from alembic import op
import sqlalchemy as sa


revision = "20261003_whatsapp_meta_webhook_tenant_keys"
down_revision = "20261003_marketing_tenant_keys"
branch_labels = None
depends_on = None


def _credentials(value: str | None) -> dict:
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def upgrade() -> None:
    op.add_column("integration_connections", sa.Column("whatsapp_phone_number_id", sa.String(100), nullable=True))
    op.add_column("integration_connections", sa.Column("whatsapp_webhook_verify_token_hash", sa.String(128), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(sa.text("""
        SELECT id, credentials_json
        FROM integration_connections
        WHERE integration_type = 'whatsapp_cloud'
    """)).mappings().all()
    for row in rows:
        credentials = _credentials(row["credentials_json"])
        phone_number_id = str(credentials.get("phone_number_id") or "").strip() or None
        verify_token = str(credentials.get("verify_token") or credentials.get("webhook_verify_token") or "")
        verify_token_hash = hashlib.sha256(verify_token.encode("utf-8")).hexdigest() if verify_token else None
        bind.execute(sa.text("""
            UPDATE integration_connections
            SET whatsapp_phone_number_id = :phone_number_id,
                whatsapp_webhook_verify_token_hash = :verify_token_hash
            WHERE id = :id
        """), {
            "id": row["id"],
            "phone_number_id": phone_number_id,
            "verify_token_hash": verify_token_hash,
        })

    duplicate_phone = bind.execute(sa.text("""
        SELECT whatsapp_phone_number_id
        FROM integration_connections
        WHERE integration_type = 'whatsapp_cloud'
          AND whatsapp_phone_number_id IS NOT NULL
        GROUP BY whatsapp_phone_number_id
        HAVING COUNT(*) > 1
    """)).scalar()
    if duplicate_phone:
        raise RuntimeError("phone_number_id Meta duplicado entre empresas; corrija as integracoes antes de migrar")

    duplicate_token = bind.execute(sa.text("""
        SELECT whatsapp_webhook_verify_token_hash
        FROM integration_connections
        WHERE integration_type = 'whatsapp_cloud'
          AND whatsapp_webhook_verify_token_hash IS NOT NULL
        GROUP BY whatsapp_webhook_verify_token_hash
        HAVING COUNT(*) > 1
    """)).scalar()
    if duplicate_token:
        raise RuntimeError("verify_token Meta duplicado entre empresas; configure tokens unicos antes de migrar")

    op.create_index(
        "uq_whatsapp_cloud_phone_number_id",
        "integration_connections",
        ["whatsapp_phone_number_id"],
        unique=True,
        postgresql_where=sa.text("integration_type = 'whatsapp_cloud' AND whatsapp_phone_number_id IS NOT NULL"),
    )
    op.create_index(
        "uq_whatsapp_cloud_verify_token_hash",
        "integration_connections",
        ["whatsapp_webhook_verify_token_hash"],
        unique=True,
        postgresql_where=sa.text("integration_type = 'whatsapp_cloud' AND whatsapp_webhook_verify_token_hash IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_whatsapp_cloud_verify_token_hash", table_name="integration_connections")
    op.drop_index("uq_whatsapp_cloud_phone_number_id", table_name="integration_connections")
    op.drop_column("integration_connections", "whatsapp_webhook_verify_token_hash")
    op.drop_column("integration_connections", "whatsapp_phone_number_id")

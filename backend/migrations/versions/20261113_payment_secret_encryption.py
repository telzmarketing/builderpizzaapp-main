"""Encrypt payment gateway secrets at rest with an environment master key."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from backend.config import get_settings
from backend.services.secret_encryption import (
    PAYMENT_SECRET_PREFIX,
    PaymentSecretEncryptionKeyMissing,
    payment_secret_ciphertext,
)


revision = "20261113_payment_secret_encryption"
down_revision = "20261113_marketplace_settlements"
branch_labels = None
depends_on = None


SECRET_COLUMNS = (
    "mp_access_token",
    "mp_webhook_secret",
    "asaas_api_key",
    "asaas_webhook_token",
    "pagarme_secret_key",
    "pagarme_webhook_secret",
    "stripe_secret_key",
    "stripe_webhook_secret",
    "pagseguro_token",
)

LEGACY_LENGTHS = {
    "mp_access_token": 300,
    "mp_webhook_secret": 300,
    "asaas_api_key": 500,
    "asaas_webhook_token": 300,
    "pagarme_secret_key": 500,
    "pagarme_webhook_secret": 500,
    "stripe_secret_key": 300,
    "stripe_webhook_secret": 300,
    "pagseguro_token": 300,
}


def _master_key() -> str:
    value = (get_settings().PAYMENT_SECRET_ENCRYPTION_KEY or "").strip()
    if not value:
        raise PaymentSecretEncryptionKeyMissing(
            "PAYMENT_SECRET_ENCRYPTION_KEY ausente; migration de segredos recusada."
        )
    return value


def _encrypt_legacy_values(bind, master_key: str) -> int:
    columns = ", ".join(("id", *SECRET_COLUMNS))
    rows = bind.execute(sa.text(f"SELECT {columns} FROM payment_gateway_config FOR UPDATE")).mappings()
    changed = 0
    for row in rows:
        updates = {}
        for column in SECRET_COLUMNS:
            value = row[column]
            if value and not value.startswith(PAYMENT_SECRET_PREFIX):
                updates[column] = payment_secret_ciphertext(value, master_key=master_key)
        if updates:
            assignments = ", ".join(f"{column} = :{column}" for column in updates)
            params = {"id": row["id"], **updates}
            bind.execute(
                sa.text(f"UPDATE payment_gateway_config SET {assignments} WHERE id = :id"),
                params,
            )
            changed += len(updates)
    return changed


def upgrade() -> None:
    bind = op.get_bind()
    # Production always requires the master key, including an empty table. In
    # development, an empty table can be migrated before the key is provisioned.
    settings = get_settings()
    master_key = (settings.PAYMENT_SECRET_ENCRYPTION_KEY or "").strip()
    if not master_key and not settings.DEBUG:
        _master_key()
    if master_key:
        _encrypt_legacy_values(bind, master_key)

    for column, length in LEGACY_LENGTHS.items():
        op.alter_column(
            "payment_gateway_config",
            column,
            existing_type=sa.String(length=length),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, " + ", ".join(SECRET_COLUMNS) + " "
            "FROM payment_gateway_config FOR UPDATE"
        )
    ).mappings()
    master_key = _master_key()
    from backend.services.secret_encryption import decrypt_payment_secret

    for row in rows:
        updates = {}
        for column, max_length in LEGACY_LENGTHS.items():
            value = row[column]
            if value and value.startswith(PAYMENT_SECRET_PREFIX):
                # Use the same key only for an explicit rollback; this keeps
                # old application versions compatible without silent loss.
                plaintext = decrypt_payment_secret(value)
            else:
                plaintext = value
            if plaintext and len(plaintext) > max_length:
                raise RuntimeError(f"Cannot safely downgrade {column}: value exceeds legacy size")
            if plaintext != value:
                updates[column] = plaintext
        if updates:
            assignments = ", ".join(f"{column} = :{column}" for column in updates)
            bind.execute(
                sa.text(f"UPDATE payment_gateway_config SET {assignments} WHERE id = :id"),
                {"id": row["id"], **updates},
            )

    for column, length in reversed(tuple(LEGACY_LENGTHS.items())):
        op.alter_column(
            "payment_gateway_config",
            column,
            existing_type=sa.Text(),
            type_=sa.String(length=length),
            existing_nullable=True,
        )

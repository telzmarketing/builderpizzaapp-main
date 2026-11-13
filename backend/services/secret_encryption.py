"""Encryption helpers for payment secrets stored in the database.

The database format is deliberately versioned so legacy plaintext rows remain
recognisable during the migration window.  Plaintext is accepted only as an
explicit compatibility path; every new ORM write is encrypted.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from backend.config import get_settings


PAYMENT_SECRET_PREFIX = "enc:v1:"


class PaymentSecretEncryptionError(RuntimeError):
    """Base error for payment-secret encryption/decryption failures."""


class PaymentSecretEncryptionKeyMissing(PaymentSecretEncryptionError):
    """Raised when encryption is required but the master key is unavailable."""


class PaymentSecretDecryptionError(PaymentSecretEncryptionError):
    """Raised when an encrypted payment secret cannot be decrypted."""


def _is_production() -> bool:
    return not bool(get_settings().DEBUG)


def _master_key() -> str:
    value = (get_settings().PAYMENT_SECRET_ENCRYPTION_KEY or "").strip()
    if not value and _is_production():
        raise PaymentSecretEncryptionKeyMissing(
            "PAYMENT_SECRET_ENCRYPTION_KEY ausente; segredos de pagamento indisponiveis."
        )
    return value


def _fernet() -> Fernet:
    master_key = _master_key()
    if not master_key:
        raise PaymentSecretEncryptionKeyMissing(
            "PAYMENT_SECRET_ENCRYPTION_KEY ausente para proteger segredo de pagamento."
        )
    # Accept a generated Fernet key as-is, while also supporting a normal
    # environment secret without placing a key-format requirement on deploys.
    try:
        return Fernet(master_key.encode("ascii"))
    except (ValueError, TypeError):
        derived = base64.urlsafe_b64encode(hashlib.sha256(master_key.encode("utf-8")).digest())
        return Fernet(derived)


def encrypt_payment_secret(value: str | None) -> str | None:
    """Encrypt a non-empty secret, returning the versioned DB representation."""
    if value is None or value == "":
        return None
    if value.startswith(PAYMENT_SECRET_PREFIX):
        return value
    token = _fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{PAYMENT_SECRET_PREFIX}{token}"


def decrypt_payment_secret(value: str | None) -> str | None:
    """Read encrypted values and explicitly preserve legacy plaintext reads."""
    if value is None or value == "":
        return None
    if not value.startswith(PAYMENT_SECRET_PREFIX):
        # Compatibility is intentional and bounded to rows written before the
        # encryption migration. Production still requires the master key.
        _master_key()
        return value
    try:
        token = value[len(PAYMENT_SECRET_PREFIX) :].encode("ascii")
        return _fernet().decrypt(token).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError, TypeError) as exc:
        raise PaymentSecretDecryptionError(
            "Segredo de pagamento criptografado invalido ou ilegivel."
        ) from exc


def payment_secret_ciphertext(value: str, *, master_key: str) -> str:
    """Encrypt a migration value without reading runtime settings."""
    if value.startswith(PAYMENT_SECRET_PREFIX):
        return value
    if not master_key:
        raise PaymentSecretEncryptionKeyMissing(
            "PAYMENT_SECRET_ENCRYPTION_KEY ausente para migrar segredos de pagamento."
        )
    try:
        fernet = Fernet(master_key.encode("ascii"))
    except (ValueError, TypeError):
        derived = base64.urlsafe_b64encode(hashlib.sha256(master_key.encode("utf-8")).digest())
        fernet = Fernet(derived)
    return f"{PAYMENT_SECRET_PREFIX}{fernet.encrypt(value.encode('utf-8')).decode('ascii')}"


class PaymentSecretType(__import__("sqlalchemy").types.TypeDecorator):
    """SQLAlchemy type that encrypts payment secrets on bind and decrypts them on read."""

    impl = __import__("sqlalchemy").Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_payment_secret(value)

    def process_result_value(self, value, dialect):
        return decrypt_payment_secret(value)

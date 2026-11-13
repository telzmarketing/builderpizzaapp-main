import pytest
from cryptography.fernet import Fernet

from backend.config import get_settings
from backend.services.secret_encryption import (
    PAYMENT_SECRET_PREFIX,
    PaymentSecretEncryptionKeyMissing,
    PaymentSecretType,
    decrypt_payment_secret,
)


@pytest.fixture(autouse=True)
def payment_secret_settings(monkeypatch):
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("PAYMENT_SECRET_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_payment_secrets_are_encrypted_at_rest_and_read_as_plaintext():
    plaintext = "access-token-that-must-not-be-stored"
    encrypted = PaymentSecretType().process_bind_param(plaintext, None)
    assert encrypted.startswith(PAYMENT_SECRET_PREFIX)
    assert plaintext not in encrypted
    assert PaymentSecretType().process_result_value(encrypted, None) == plaintext


def test_legacy_plaintext_is_an_explicit_compatibility_read():
    assert decrypt_payment_secret("legacy-access-token") == "legacy-access-token"


def test_production_fails_closed_without_master_key(monkeypatch):
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.delenv("PAYMENT_SECRET_ENCRYPTION_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(PaymentSecretEncryptionKeyMissing):
        PaymentSecretType().process_bind_param("secret", None)

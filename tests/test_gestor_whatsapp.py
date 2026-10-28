import hashlib
import hmac
import json
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models.gestor import GestorWhatsAppChannel, GestorWhatsAppMessage
from backend.models.tenant import Tenant
from backend.schemas.gestor import GestorWhatsAppChannelUpdate
from backend.services.gestor_service import GestorService, GestorWhatsAppNotConfigured


@pytest.fixture()
def whatsapp_db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[Tenant.__table__, GestorWhatsAppChannel.__table__, GestorWhatsAppMessage.__table__])
    db = sessionmaker(bind=engine)()
    tenant_id = str(uuid4())
    other_tenant_id = str(uuid4())
    # SQLite does not support the PostgreSQL partial unique index used by
    # Tenant.is_legacy; one real tenant is sufficient because channel FKs are
    # not enforced by this isolated test database.
    db.add(Tenant(id=tenant_id, slug=f"gestor-wa-{tenant_id[:8]}", name="Gestor WA", status="active"))
    db.commit()
    monkeypatch.setenv("GESTOR_META_APP_SECRET_TEST", "meta-app-secret")
    try:
        yield db, tenant_id, other_tenant_id
    finally:
        db.close()
        engine.dispose()


def _channel(db, tenant_id, phone_id="phone-gestor-1", enabled=True, verify_token="verify-token-123456"):
    item = GestorWhatsAppChannel(
        tenant_id=tenant_id, enabled=enabled, phone_number_id=phone_id,
        business_account_id="business-1", display_phone_number="5511999990000",
        verify_token_hash=hashlib.sha256(verify_token.encode()).hexdigest(),
        app_secret_ref="env:GESTOR_META_APP_SECRET_TEST",
        status="ready_receive_only" if enabled else "disabled",
    )
    db.add(item)
    db.commit()
    return item


def _payload(phone_id="phone-gestor-1", provider_id="wamid-1"):
    return {"object": "whatsapp_business_account", "entry": [{"changes": [{
        "value": {
            "metadata": {"phone_number_id": phone_id},
            "messages": [{"id": provider_id, "from": "5511988887777", "type": "text", "text": {"body": "estoque"}}],
        }
    }]}]}


def _signature(payload):
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return raw, "sha256=" + hmac.new(b"meta-app-secret", raw, hashlib.sha256).hexdigest()


def test_activation_requires_resolvable_secret(whatsapp_db, monkeypatch):
    db, tenant_id, _ = whatsapp_db
    monkeypatch.delenv("GESTOR_META_APP_SECRET_TEST", raising=False)
    service = GestorService(db, tenant_id, str(uuid4()))
    with pytest.raises(GestorWhatsAppNotConfigured, match="Ativacao recusada"):
        service.update_whatsapp_channel(GestorWhatsAppChannelUpdate(
            enabled=True, phone_number_id="phone-secure-1", business_account_id="business-1",
            verify_token="verify-token-123456", app_secret_ref="env:GESTOR_META_APP_SECRET_TEST",
        ))
    item = service.get_whatsapp_channel()
    assert item is not None and item.enabled is False and item.app_secret_ref.startswith("env:")


def test_invalid_signature_and_missing_phone_id_are_rejected(whatsapp_db):
    db, tenant_id, _ = whatsapp_db
    _channel(db, tenant_id)
    payload = _payload()
    raw, signature = _signature(payload)
    with pytest.raises(GestorWhatsAppNotConfigured, match="Assinatura Meta invalida"):
        GestorService.receive_gestor_meta_webhook(db, payload, raw, "sha256=invalid")
    with pytest.raises(GestorWhatsAppNotConfigured, match="phone_number_id"):
        GestorService.receive_gestor_meta_webhook(db, _payload(phone_id=""), raw, signature)


def test_verify_token_and_message_idempotency_are_channel_scoped(whatsapp_db):
    db, tenant_id, other_tenant_id = whatsapp_db
    channel = _channel(db, tenant_id)
    _channel(db, other_tenant_id, phone_id="phone-other-1", verify_token="other-verify-token-123456")
    assert GestorService.verify_gestor_meta_challenge(db, "verify-token-123456") == "ok"
    assert GestorService.verify_gestor_meta_challenge(db, "wrong-token") is None

    payload = _payload()
    raw, signature = _signature(payload)
    first = GestorService.receive_gestor_meta_webhook(db, payload, raw, signature)
    second = GestorService.receive_gestor_meta_webhook(db, payload, raw, signature)
    assert first["received"] == 1 and first["duplicates"] == 0
    assert second["received"] == 0 and second["duplicates"] == 1
    assert db.query(GestorWhatsAppMessage).count() == 1
    assert db.query(GestorWhatsAppMessage).first().status == "RECEIVED"


def test_commercial_phone_id_is_not_accepted_by_gestor(whatsapp_db):
    db, tenant_id, _ = whatsapp_db
    _channel(db, tenant_id, phone_id="gestor-phone")
    payload = _payload(phone_id="commercial-phone")
    raw, signature = _signature(payload)
    with pytest.raises(GestorWhatsAppNotConfigured, match="canal Gestor"):
        GestorService.receive_gestor_meta_webhook(db, payload, raw, signature)

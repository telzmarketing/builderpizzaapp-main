from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models.admin import AdminUser
from backend.models.gestor import (
    GestorOperation,
    GestorWhatsAppChannel,
    GestorWhatsAppMessage,
    GestorWhatsAppOutbox,
)
from backend.models.membership import TenantMembership
from backend.models.tenant import Tenant
from backend.services.gestor_service import (
    GestorOperationInvalid,
    GestorService,
    GestorWhatsAppNotConfigured,
    GestorWhatsAppPolicyDenied,
)


@pytest.fixture()
def send_db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, AdminUser.__table__, TenantMembership.__table__,
        GestorOperation.__table__, GestorWhatsAppChannel.__table__,
        GestorWhatsAppMessage.__table__, GestorWhatsAppOutbox.__table__,
    ])
    db = sessionmaker(bind=engine)()
    tenant_id, other_tenant_id, admin_id = str(uuid4()), str(uuid4()), str(uuid4())
    db.add_all([
        Tenant(id=tenant_id, slug=f"send-{tenant_id[:8]}", name="Send", status="active"),
        AdminUser(id=admin_id, email=f"send-{admin_id[:8]}@test.invalid", name="Sender", password_hash="unused", active=True),
        TenantMembership(id=str(uuid4()), tenant_id=tenant_id, user_id=admin_id, role="owner", status="active", is_default=True),
    ])
    db.commit()
    monkeypatch.setenv("GESTOR_META_APP_SECRET_SEND", "app-secret-not-persisted")
    monkeypatch.setenv("GESTOR_META_ACCESS_TOKEN_SEND", "access-token-not-persisted")
    try:
        yield db, tenant_id, other_tenant_id, admin_id
    finally:
        db.close()
        engine.dispose()


def _channel(db, tenant_id):
    item = GestorWhatsAppChannel(
        tenant_id=tenant_id, enabled=True, phone_number_id="gestor-phone-send",
        business_account_id="business-send", verify_token_hash="hash",
        app_secret_ref="env:GESTOR_META_APP_SECRET_SEND",
        access_token_ref="env:GESTOR_META_ACCESS_TOKEN_SEND", status="ready_send",
    )
    db.add(item)
    db.commit()
    return item


def _operation(db, tenant_id, admin_id, *, recipient="5511999990000", kind="text", body="Operacao concluida"):
    item = GestorOperation(
        tenant_id=tenant_id, requested_by_admin_id=admin_id, channel="gestor_whatsapp",
        phone=recipient, tool_name="gestor.whatsapp.send_message", risk_level="medium",
        status="READY_TO_EXECUTE", arguments_json={
            "to_phone": recipient, "message_type": kind, "body": body if kind == "text" else None,
            "template_name": "gestor_status" if kind == "template" else None,
            "template_language": "pt_BR", "template_variables": ["Gran Torino"] if kind == "template" else [],
        }, preview_json={"summary": "Enviar mensagem administrativa"},
        idempotency_key=str(uuid4()),
    )
    db.add(item)
    db.commit()
    return item


def _inbound(db, tenant_id, channel_id, phone="5511999990000", age=timedelta(hours=1)):
    item = GestorWhatsAppMessage(
        tenant_id=tenant_id, channel_id=channel_id, provider_message_id=str(uuid4()),
        from_phone=phone, message_type="text", text_body="status", payload_json={},
        status="RECEIVED", created_at=datetime.now(timezone.utc) - age,
    )
    db.add(item)
    db.commit()
    return item


class _MetaResponse:
    status_code = 200
    text = "ok"

    @staticmethod
    def json():
        return {"messages": [{"id": "wamid.gestor.1"}]}


def test_enqueue_requires_confirmed_operation_and_external_token(send_db, monkeypatch):
    db, tenant_id, _other_tenant_id, admin_id = send_db
    channel = _channel(db, tenant_id)
    operation = _operation(db, tenant_id, admin_id)
    _inbound(db, tenant_id, channel.id)
    operation.status = "PENDING_CONFIRMATION"
    db.commit()
    with pytest.raises(GestorOperationInvalid, match="confirmada"):
        GestorService(db, tenant_id, admin_id).enqueue_whatsapp_message(operation.id)

    operation.status = "READY_TO_EXECUTE"
    db.commit()
    monkeypatch.delenv("GESTOR_META_ACCESS_TOKEN_SEND", raising=False)
    with pytest.raises(GestorWhatsAppNotConfigured, match="Token de acesso"):
        GestorService(db, tenant_id, admin_id).enqueue_whatsapp_message(operation.id)


def test_enqueue_is_idempotent_and_processing_is_separate(send_db, monkeypatch):
    db, tenant_id, _other_tenant_id, admin_id = send_db
    channel = _channel(db, tenant_id)
    _inbound(db, tenant_id, channel.id)
    operation = _operation(db, tenant_id, admin_id)
    service = GestorService(db, tenant_id, admin_id)

    first, replay, policy = service.enqueue_whatsapp_message(operation.id)
    second, replay_again, _ = service.enqueue_whatsapp_message(operation.id)
    assert first.id == second.id
    assert replay is False and replay_again is True
    assert policy["window_open"] is True
    assert operation.status == "QUEUED"
    assert db.query(GestorWhatsAppOutbox).count() == 1
    assert "access-token-not-persisted" not in str(first.__dict__)

    calls = []

    def fake_post(url, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return _MetaResponse()

    monkeypatch.setattr("backend.services.gestor_service.requests.post", fake_post)
    assert service.process_whatsapp_outbox(10) == {
        "processed": 1, "sent": 1, "failed": 0, "deferred": 0, "dead": 0,
    }
    db.refresh(first)
    db.refresh(operation)
    assert first.status == "sent"
    assert first.provider_message_id == "wamid.gestor.1"
    assert operation.status == "EXECUTED"
    assert calls[0][1]["Authorization"] == "Bearer access-token-not-persisted"
    assert calls[0][2]["type"] == "text"


def test_meta_window_requires_template_and_retry_is_bounded(send_db, monkeypatch):
    db, tenant_id, _other_tenant_id, admin_id = send_db
    channel = _channel(db, tenant_id)
    _inbound(db, tenant_id, channel.id, age=timedelta(hours=25))
    operation = _operation(db, tenant_id, admin_id)
    service = GestorService(db, tenant_id, admin_id)
    with pytest.raises(GestorWhatsAppPolicyDenied, match="24 horas"):
        service.enqueue_whatsapp_message(operation.id)

    template_op = _operation(db, tenant_id, admin_id, kind="template", body=None)
    item, _, policy = service.enqueue_whatsapp_message(template_op.id)
    assert item.message_type == "template"
    assert policy["requires_approved_template"] is True

    class FailedResponse:
        status_code = 400
        text = "invalid template"

        @staticmethod
        def json():
            return {"error": {"message": "invalid template"}}

    monkeypatch.setattr("backend.services.gestor_service.requests.post", lambda **kwargs: FailedResponse())
    assert service.process_whatsapp_outbox() == {
        "processed": 1, "sent": 0, "failed": 1, "deferred": 0, "dead": 0,
    }
    db.refresh(item)
    assert item.status == "failed" and item.attempts == 1
    retried = service.retry_whatsapp_outbox(item.id)
    assert retried.status == "pending" and retried.attempts == 0


def test_tenant_scope_does_not_expose_other_outbox(send_db):
    db, tenant_id, other_tenant_id, admin_id = send_db
    channel = _channel(db, tenant_id)
    _inbound(db, tenant_id, channel.id)
    operation = _operation(db, tenant_id, admin_id)
    service = GestorService(db, tenant_id, admin_id)
    item, _, _ = service.enqueue_whatsapp_message(operation.id)
    assert item in service.list_whatsapp_outbox()
    assert GestorService(db, other_tenant_id, admin_id).list_whatsapp_outbox() == []

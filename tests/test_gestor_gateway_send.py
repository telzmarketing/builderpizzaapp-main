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
from backend.models.whatsapp_gateway import WhatsAppGatewayInstance
from backend.services.gestor_service import GestorService
from backend.services.whatsapp_gateway_provider import WhatsAppProviderResult


@pytest.fixture()
def gateway_send_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, AdminUser.__table__, TenantMembership.__table__,
        WhatsAppGatewayInstance.__table__, GestorOperation.__table__,
        GestorWhatsAppChannel.__table__, GestorWhatsAppMessage.__table__,
        GestorWhatsAppOutbox.__table__,
    ])
    db = sessionmaker(bind=engine)()
    tenant_id, admin_id = str(uuid4()), str(uuid4())
    db.add_all([
        Tenant(id=tenant_id, slug=f"gateway-{tenant_id[:8]}", name="Gateway Send", status="active"),
        AdminUser(id=admin_id, email=f"gateway-{admin_id[:8]}@test.invalid", name="Gateway sender", password_hash="unused", active=True),
        TenantMembership(
            id=str(uuid4()), tenant_id=tenant_id, user_id=admin_id,
            role="owner", status="active", is_default=True,
        ),
    ])
    db.commit()
    try:
        yield db, tenant_id, admin_id
    finally:
        db.close()
        engine.dispose()


def test_gateway_instance_sends_without_meta_request(gateway_send_db, monkeypatch):
    db, tenant_id, admin_id = gateway_send_db
    instance = WhatsAppGatewayInstance(
        id="gateway-instance-gestor",
        tenant_id=tenant_id,
        company_id="default",
        name="Gestor Gateway",
        provider="baileys",
        status="connected",
    )
    channel = GestorWhatsAppChannel(
        tenant_id=tenant_id,
        enabled=True,
        phone_number_id="meta-phone-unused",
        business_account_id="meta-business-unused",
        verify_token_hash="hash",
        app_secret_ref="env:GESTOR_META_APP_SECRET_UNUSED",
        access_token_ref="env:GESTOR_META_ACCESS_TOKEN_UNUSED",
        status="ready_send",
        whatsapp_gateway_instance_id=instance.id,
    )
    db.add_all([instance, channel])
    db.flush()
    db.add(GestorWhatsAppMessage(
        tenant_id=tenant_id,
        channel_id=channel.id,
        provider_message_id="inbound-gateway-1",
        from_phone="5511999990000",
        message_type="text",
        text_body="Como esta o pedido?",
        payload_json={},
        status="RECEIVED",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    ))
    operation = GestorOperation(
        tenant_id=tenant_id,
        requested_by_admin_id=admin_id,
        channel="gestor_whatsapp",
        phone="5511999990000",
        tool_name="gestor.whatsapp.send_message",
        risk_level="medium",
        status="READY_TO_EXECUTE",
        arguments_json={
            "to_phone": "5511999990000",
            "message_type": "text",
            "body": "O pedido esta em preparacao.",
        },
        preview_json={"summary": "Enviar pelo Gateway"},
        idempotency_key=str(uuid4()),
    )
    db.add(operation)
    db.commit()

    gateway_calls = []

    class FakeGatewayService:
        def __init__(self, _db, tenant_context=None):
            self.tenant_context = tenant_context

        def send_text_message(self, *, phone, text, instance_id=None):
            gateway_calls.append({"phone": phone, "text": text, "instance_id": instance_id})
            return WhatsAppProviderResult(
                ok=True,
                status="sent",
                message="Mensagem enviada pelo Gateway.",
                provider_message_id="gateway-message-1",
                data={"provider": "baileys"},
            )

    def fail_meta_request(*_args, **_kwargs):
        raise AssertionError("Meta Graph nao deve ser chamado quando o Gateway esta selecionado.")

    monkeypatch.setattr("backend.services.gestor_service.WhatsAppGatewayService", FakeGatewayService)
    monkeypatch.setattr("backend.services.gestor_service.requests.post", fail_meta_request)

    service = GestorService(db, tenant_id, admin_id)
    item, replay, policy = service.enqueue_whatsapp_message(operation.id)
    result = service.process_whatsapp_outbox()

    db.refresh(item)
    db.refresh(operation)
    assert replay is False
    assert policy["window_open"] is True
    assert result == {"processed": 1, "sent": 1, "failed": 0, "deferred": 0, "dead": 0}
    assert gateway_calls == [{
        "phone": "5511999990000",
        "text": "O pedido esta em preparacao.",
        "instance_id": instance.id,
    }]
    assert item.status == "sent"
    assert item.provider_message_id == "gateway-message-1"
    assert item.error is None
    assert operation.status == "EXECUTED"

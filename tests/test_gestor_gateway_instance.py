from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models.gestor import GestorWhatsAppChannel
from backend.models.tenant import Tenant
from backend.models.whatsapp_gateway import WhatsAppGatewayInstance
from backend.schemas.gestor import GestorWhatsAppChannelUpdate
from backend.services.gestor_service import GestorService, GestorWhatsAppNotConfigured


@pytest.fixture()
def gateway_db(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, WhatsAppGatewayInstance.__table__, GestorWhatsAppChannel.__table__,
    ])
    db = sessionmaker(bind=engine)()
    tenant_id = str(uuid4())
    other_tenant_id = str(uuid4())
    db.add(Tenant(id=tenant_id, slug=f"gestor-gateway-{tenant_id[:8]}", name="Gestor Gateway", status="active"))
    db.commit()
    monkeypatch.setenv("GESTOR_META_APP_SECRET_TEST", "meta-app-secret")
    try:
        yield db, tenant_id, other_tenant_id
    finally:
        db.close()
        engine.dispose()


def _instance(tenant_id: str, name: str) -> WhatsAppGatewayInstance:
    return WhatsAppGatewayInstance(
        id=str(uuid4()), tenant_id=tenant_id, company_id="default", name=name,
        phone_number="5511999990000", provider="baileys", status="connected",
    )


def _channel_update(instance_id: str | None) -> GestorWhatsAppChannelUpdate:
    return GestorWhatsAppChannelUpdate(
        phone_number_id="meta-phone-1", business_account_id="meta-business-1",
        verify_token="verify-token-123456", app_secret_ref="env:GESTOR_META_APP_SECRET_TEST",
        access_token_ref="env:GESTOR_META_ACCESS_TOKEN_TEST",
        whatsapp_gateway_instance_id=instance_id,
    )


def test_gateway_instances_are_listed_only_for_the_gestor_tenant(gateway_db):
    db, tenant_id, other_tenant_id = gateway_db
    own = _instance(tenant_id, "Gestor principal")
    other = _instance(other_tenant_id, "Outro tenant")
    db.add_all([own, other])
    db.commit()

    result = GestorService(db, tenant_id, str(uuid4())).list_whatsapp_gateway_instances()

    assert [item.id for item in result] == [own.id]
    assert all(item.tenant_id == tenant_id for item in result)


def test_channel_accepts_owned_gateway_instance_and_keeps_meta_identity_separate(gateway_db):
    db, tenant_id, _other_tenant_id = gateway_db
    own = _instance(tenant_id, "Gestor principal")
    db.add(own)
    db.commit()

    channel = GestorService(db, tenant_id, str(uuid4())).update_whatsapp_channel(_channel_update(own.id))

    assert channel.whatsapp_gateway_instance_id == own.id
    assert channel.phone_number_id == "meta-phone-1"
    assert channel.whatsapp_gateway_instance_id != channel.phone_number_id


def test_channel_rejects_gateway_instance_from_another_tenant(gateway_db):
    db, tenant_id, other_tenant_id = gateway_db
    other = _instance(other_tenant_id, "Outro tenant")
    db.add(other)
    db.commit()

    with pytest.raises(GestorWhatsAppNotConfigured, match="nao pertence a este tenant"):
        GestorService(db, tenant_id, str(uuid4())).update_whatsapp_channel(_channel_update(other.id))

    assert db.query(GestorWhatsAppChannel).filter(GestorWhatsAppChannel.tenant_id == tenant_id).count() == 0

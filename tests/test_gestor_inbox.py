from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models.admin import AdminUser
from backend.models.gestor import (
    GestorAuthorizedContact,
    GestorOperation,
    GestorWhatsAppChannel,
    GestorWhatsAppMessage,
)
from backend.models.membership import TenantMembership
from backend.models.tenant import Tenant
from backend.schemas.gestor import GestorAIPlanOut, GestorAIProposedTool, GestorAIUsage
from backend.services.gestor_service import GestorService


@pytest.fixture()
def inbox_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, AdminUser.__table__, TenantMembership.__table__,
        GestorAuthorizedContact.__table__, GestorOperation.__table__,
        GestorWhatsAppChannel.__table__, GestorWhatsAppMessage.__table__,
    ])
    db = sessionmaker(bind=engine)()
    tenant_id, other_tenant_id, admin_id = str(uuid4()), str(uuid4()), str(uuid4())
    # SQLite cannot reproduce the PostgreSQL partial unique index on
    # Tenant.is_legacy; the second tenant id is intentionally only used to
    # exercise tenant predicates in this isolated database.
    db.add_all([
        Tenant(id=tenant_id, slug=f"inbox-{tenant_id[:8]}", name="Inbox", status="active"),
        AdminUser(id=admin_id, email=f"inbox-{admin_id[:8]}@test.invalid", name="Inbox Admin", password_hash="unused", active=True),
        TenantMembership(id=str(uuid4()), tenant_id=tenant_id, user_id=admin_id, role="owner", status="active", is_default=True),
    ])
    db.commit()
    try:
        yield db, tenant_id, other_tenant_id, admin_id
    finally:
        db.close()
        engine.dispose()


def _message(db, tenant_id, phone="5511999990000", provider_id=None, text_body="mostre as vendas"):
    channel = GestorWhatsAppChannel(
        tenant_id=tenant_id, enabled=True, phone_number_id=f"phone-{uuid4()}",
        business_account_id="business", verify_token_hash="hash", app_secret_ref="env:GESTOR_META_APP_SECRET_TEST",
        status="ready_receive_only",
    )
    db.add(channel)
    db.flush()
    message = GestorWhatsAppMessage(
        tenant_id=tenant_id, channel_id=channel.id, provider_message_id=provider_id or str(uuid4()),
        from_phone=phone, message_type="text", text_body=text_body,
        payload_json={"id": provider_id or "provider"}, status="RECEIVED",
    )
    db.add(message)
    db.commit()
    return message


def _plan(tool_name=None, arguments=None):
    tools = [] if tool_name is None else [GestorAIProposedTool(
        tool_name=tool_name, arguments=arguments or {}, risk_level="low",
        requires_confirmation=False, summary="Consulta planejada.",
    )]
    return GestorAIPlanOut(
        provider="internal", model="internal-rules-v1", response_text="Planejamento sem execucao.",
        proposed_tools=tools, usage=GestorAIUsage(),
    )


def _authorize(db, tenant_id, admin_id, phone="5511999990000"):
    contact = GestorAuthorizedContact(
        tenant_id=tenant_id, admin_user_id=admin_id, phone_normalized=phone,
        display_name="Gestor", role="owner", active=True, requires_reauth=True,
    )
    db.add(contact)
    db.commit()
    return contact


def test_authorized_message_creates_planned_operation_without_execution(inbox_db, monkeypatch):
    db, tenant_id, _other_tenant_id, admin_id = inbox_db
    message = _message(db, tenant_id)
    _authorize(db, tenant_id, admin_id)
    service = GestorService(db, tenant_id, admin_id)
    monkeypatch.setattr(service, "plan_ai", lambda body: _plan("gestor.bi.dashboard", {"period": "30d"}))
    monkeypatch.setattr(service, "execute_tool", lambda *_args: pytest.fail("inbox nao pode executar ferramenta"))

    result = service.process_gestor_inbox(10)

    db.refresh(message)
    assert result == {"processed": 1, "planned": 1, "responded": 0, "rejected": 0, "failed": 0, "skipped": 0}
    assert message.status == "PLANNED"
    assert message.payload_json["id"] == "provider"
    operation = db.query(GestorOperation).one()
    assert operation.status == "PLANNED"
    assert operation.channel == "gestor_whatsapp"
    assert operation.tool_name == "gestor.bi.dashboard"
    assert message.payload_json["_gestor_processing"]["operation_id"] == operation.id


def test_unauthorized_message_is_rejected(inbox_db, monkeypatch):
    db, tenant_id, _other_tenant_id, admin_id = inbox_db
    message = _message(db, tenant_id, phone="5511888887777")
    service = GestorService(db, tenant_id, admin_id)
    monkeypatch.setattr(service, "plan_ai", lambda *_args: pytest.fail("nao deve planejar remetente nao autorizado"))

    result = service.process_gestor_inbox()

    db.refresh(message)
    assert result["rejected"] == 1
    assert message.status == "REJECTED"
    assert "nao autorizado" in message.payload_json["_gestor_processing"]["error"]


def test_reprocessing_does_not_create_second_operation(inbox_db, monkeypatch):
    db, tenant_id, _other_tenant_id, admin_id = inbox_db
    _message(db, tenant_id, provider_id="same-provider")
    _authorize(db, tenant_id, admin_id)
    service = GestorService(db, tenant_id, admin_id)
    monkeypatch.setattr(service, "plan_ai", lambda body: _plan("gestor.bi.dashboard", {"period": "30d"}))

    first = service.process_gestor_inbox()
    second = service.process_gestor_inbox()

    assert first["planned"] == 1
    assert second["processed"] == 0
    assert db.query(GestorOperation).count() == 1


def test_planner_failure_marks_failed_without_secret_details(inbox_db, monkeypatch):
    db, tenant_id, _other_tenant_id, admin_id = inbox_db
    message = _message(db, tenant_id)
    _authorize(db, tenant_id, admin_id)
    service = GestorService(db, tenant_id, admin_id)
    monkeypatch.setattr(service, "plan_ai", lambda *_args: (_ for _ in ()).throw(RuntimeError("sk-super-secret")))

    result = service.process_gestor_inbox()

    db.refresh(message)
    assert result["failed"] == 1
    assert message.status == "FAILED"
    error = message.payload_json["_gestor_processing"]["error"]
    assert error == "Falha no planejamento administrativo do Gestor."
    assert "super-secret" not in str(message.payload_json)


def test_tenant_isolation_does_not_process_other_tenant(inbox_db, monkeypatch):
    db, tenant_id, other_tenant_id, admin_id = inbox_db
    other_message = _message(db, other_tenant_id)
    _authorize(db, other_tenant_id, admin_id)
    service = GestorService(db, tenant_id, admin_id)
    monkeypatch.setattr(service, "plan_ai", lambda *_args: pytest.fail("tenant incorreto processado"))

    result = service.process_gestor_inbox()

    db.refresh(other_message)
    assert result["processed"] == 0
    assert other_message.status == "RECEIVED"
    assert db.query(GestorOperation).count() == 0

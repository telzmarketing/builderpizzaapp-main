from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models.admin import AdminUser
from backend.models.gestor import GestorAISettings, GestorOperation
from backend.models.tenant import Tenant
from backend.schemas.gestor import GestorAIPlanIn, GestorAISettingsUpdate
from backend.services.ai.base import AIResponse
from backend.services.gestor_service import GestorAIUnavailable, GestorOperationInvalid, GestorService


@pytest.fixture()
def gestor_ai_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[Tenant.__table__, AdminUser.__table__, GestorOperation.__table__, GestorAISettings.__table__])
    db = sessionmaker(bind=engine)()
    tenant_id, admin_id = str(uuid4()), str(uuid4())
    db.add(Tenant(id=tenant_id, slug=f"ai-{tenant_id[:8]}", name="AI Teste", status="active"))
    db.add(AdminUser(id=admin_id, email=f"ai-{tenant_id[:8]}@test.invalid", name="AI Teste", password_hash="not-used", active=True))
    db.commit()
    try:
        yield db, tenant_id, admin_id
    finally:
        db.close()
        engine.dispose()


def test_provider_status_does_not_expose_secret(gestor_ai_db, monkeypatch):
    db, tenant_id, admin_id = gestor_ai_db
    monkeypatch.setattr("backend.config.get_ai_api_key", lambda name: "sk-super-secret-value" if name == "OPENAI_API_KEY" else "")
    status = GestorService(db, tenant_id, admin_id).ai_status()
    assert status["openai_configured"] is True
    assert "super-secret" not in (status["openai_key_preview"] or "")
    assert "sk-super-secret-value" not in str(status)


def test_internal_plan_is_read_only_and_does_not_execute(gestor_ai_db, monkeypatch):
    db, tenant_id, admin_id = gestor_ai_db
    service = GestorService(db, tenant_id, admin_id)
    monkeypatch.setattr(service, "execute_tool", lambda *_args: pytest.fail("plan nao pode executar ferramenta"))
    result = service.plan_ai(GestorAIPlanIn(message="mostre as vendas dos ultimos dias"))
    assert result.no_execution is True
    assert result.proposed_tools[0].tool_name == "gestor.bi.dashboard"
    assert db.query(GestorOperation).count() == 0


def test_internal_plan_writing_tool_requires_confirmation(gestor_ai_db):
    db, tenant_id, admin_id = gestor_ai_db
    service = GestorService(db, tenant_id, admin_id)
    result = service.plan_ai(GestorAIPlanIn(message="aprovar documento receipt-123"))
    proposal = result.proposed_tools[0]
    assert proposal.tool_name == "gestor.inventory.approve_receipt"
    assert proposal.requires_confirmation is True
    assert proposal.risk_level == "medium"
    assert result.no_execution is True


def test_external_plan_rejects_unknown_tool(gestor_ai_db, monkeypatch):
    db, tenant_id, admin_id = gestor_ai_db
    service = GestorService(db, tenant_id, admin_id)
    service.update_ai_settings(GestorAISettingsUpdate(provider="openai", model="gpt-4o-mini"))
    monkeypatch.setattr("backend.config.get_ai_api_key", lambda _name: "configured-secret")
    monkeypatch.setattr(
        "backend.services.ai.openai_provider.OpenAIProvider.generate",
        lambda *_args, **_kwargs: AIResponse(
            content='{"response_text":"ok","proposed_tools":[{"tool_name":"gestor.sql.query","arguments":{},"summary":"sql","evidence_required":[]}]}'
        ),
    )
    with pytest.raises(GestorOperationInvalid, match="catalogo"):
        service.plan_ai(GestorAIPlanIn(message="consulte qualquer coisa"))

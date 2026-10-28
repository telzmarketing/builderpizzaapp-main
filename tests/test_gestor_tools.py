from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models.admin import AdminUser
from backend.models.gestor import GestorOperation
from backend.models.membership import TenantMembership
from backend.models.tenant import Tenant
from backend.schemas.gestor import GestorToolExecuteIn
from backend.services.gestor_service import GestorOperationInvalid, GestorService


@pytest.fixture()
def gestor_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, AdminUser.__table__, TenantMembership.__table__, GestorOperation.__table__,
    ])
    db = sessionmaker(bind=engine)()
    tenant_id = str(uuid4())
    admin_id = str(uuid4())
    db.add(Tenant(id=tenant_id, slug=f"tools-{tenant_id[:8]}", name="Tools Teste", status="active"))
    db.add(AdminUser(id=admin_id, email=f"tools-{tenant_id[:8]}@test.invalid", name="Tools Teste", password_hash="not-used", active=True))
    db.add(TenantMembership(id=str(uuid4()), tenant_id=tenant_id, user_id=admin_id, role="owner", status="active", is_default=True))
    db.commit()
    try:
        yield db, tenant_id, admin_id
    finally:
        db.close()
        engine.dispose()


def test_tool_catalog_is_typed_and_read_only():
    catalog = GestorService.tool_catalog()
    names = {item.name for item in catalog}
    assert {
        "gestor.bi.dashboard",
        "gestor.inventory.overview",
        "gestor.finance.overview",
        "gestor.operations.summary",
    }.issubset(names)
    assert all(item.mutates_data is False for item in GestorService.tool_catalog() if not item.mutates_data)
    read_names = {
        "gestor.bi.dashboard",
        "gestor.inventory.overview",
        "gestor.finance.overview",
        "gestor.operations.summary",
    }
    assert all(item.risk_level == "low" and item.mutates_data is False for item in catalog if item.name in read_names)
    assert next(item for item in catalog if item.name == "gestor.bi.dashboard").input_schema["properties"]["period"]


def test_unknown_tool_is_rejected(gestor_db):
    db, tenant_id, admin_id = gestor_db
    service = GestorService(db, tenant_id, admin_id)
    with pytest.raises(GestorOperationInvalid, match="desconhecida"):
        service.execute_tool( GestorToolExecuteIn(
            tool_name="gestor.sql.query", phone="5511999990000", arguments={}
        ))
    assert db.query(GestorOperation).count() == 0


def test_tool_execution_is_tenant_scoped_and_idempotent(gestor_db, monkeypatch):
    db, tenant_id, admin_id = gestor_db

    def fake_dashboard(self, args):
        return {"tenant_id": self.tenant_id}

    monkeypatch.setattr(GestorService, "_execute_bi_dashboard", fake_dashboard)
    first = GestorService(db, tenant_id, admin_id).execute_tool(GestorToolExecuteIn(
        tool_name="gestor.bi.dashboard", phone="5511999990000",
        idempotency_key="read-1", arguments={"period": "7d"},
    ))
    assert first[0].status == "EXECUTED"
    assert first[1] == {"tenant_id": tenant_id}

    other_tenant = str(uuid4())
    replay = GestorService(db, other_tenant, admin_id).execute_tool(GestorToolExecuteIn(
        tool_name="gestor.bi.dashboard", phone="5511999990000",
        idempotency_key="read-1", arguments={"period": "7d"},
    ))
    assert replay[0].id != first[0].id
    assert replay[1] == {"tenant_id": other_tenant}

    with pytest.raises(GestorOperationInvalid, match="Replay divergente"):
        GestorService(db, tenant_id, admin_id).execute_tool(GestorToolExecuteIn(
            tool_name="gestor.bi.dashboard", phone="5511999990000",
            idempotency_key="read-1", arguments={"period": "90d"},
        ))


def test_tool_failure_is_audited(gestor_db, monkeypatch):
    db, tenant_id, admin_id = gestor_db

    def failing_dashboard(self, args):
        raise RuntimeError("BI indisponivel")

    monkeypatch.setattr(GestorService, "_execute_bi_dashboard", failing_dashboard)
    operation, result = GestorService(db, tenant_id, admin_id).execute_tool(GestorToolExecuteIn(
        tool_name="gestor.bi.dashboard", phone="5511999990000", idempotency_key="failed-1",
    ))
    assert result is None
    assert operation.status == "FAILED"
    assert "BI indisponivel" in operation.error

from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models.gestor import GestorOperation
from backend.models.admin import AdminUser
from backend.models.tenant import Tenant
from backend.schemas.gestor import GestorOperationPreviewIn, GestorToolExecuteIn
from backend.services.gestor_service import GestorOperationInvalid, GestorOperationNotFound, GestorService


@pytest.fixture()
def gestor_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[Tenant.__table__, AdminUser.__table__, GestorOperation.__table__])
    db = sessionmaker(bind=engine)()
    tenant_id, admin_id = str(uuid4()), str(uuid4())
    try:
        yield db, tenant_id, admin_id
    finally:
        db.close()
        engine.dispose()


def _confirmed(db, tenant_id, admin_id, document_id="receipt-1"):
    service = GestorService(db, tenant_id, admin_id)
    operation, token = service.create_operation(GestorOperationPreviewIn(
        channel="gestor", phone="5511999990000", tool_name="gestor.inventory.approve_receipt",
        risk_level="medium", arguments={"document_id": document_id},
        preview={"summary": f"Aprovar recebimento {document_id}"}, idempotency_key=str(uuid4()),
    ))
    service.confirm_operation(operation.id, token)
    return operation


def _body(operation_id, document_id="receipt-1"):
    return GestorToolExecuteIn(
        operation_id=operation_id, tool_name="gestor.inventory.approve_receipt",
        phone="5511999990000", arguments={"document_id": document_id},
    )


def test_write_without_confirmation_is_rejected(gestor_db):
    db, tenant_id, admin_id = gestor_db
    with pytest.raises(GestorOperationInvalid, match="confirmacao previa"):
        GestorService(db, tenant_id, admin_id).execute_tool(GestorToolExecuteIn(
            tool_name="gestor.inventory.approve_receipt", phone="5511999990000",
            arguments={"document_id": "receipt-1"},
        ))


def test_confirmed_write_calls_receipt_service_once_and_executes(gestor_db, monkeypatch):
    db, tenant_id, admin_id = gestor_db
    operation = _confirmed(db, tenant_id, admin_id)
    calls = []

    def approve(self, document_id):
        calls.append((self.tenant_id, self.admin_id, document_id))
        return {"id": document_id, "status": "approved"}

    def handler(self, args):
        return approve(type("ReceiptService", (), {"tenant_id": self.tenant_id, "admin_id": self.admin_id})(), args.document_id)

    monkeypatch.setattr(GestorService, "_execute_inventory_approve_receipt", handler)
    executed, result = GestorService(db, tenant_id, admin_id).execute_tool(_body(operation.id))
    assert calls == [(tenant_id, admin_id, "receipt-1")]
    assert executed.status == "EXECUTED"
    assert executed.executed_at is not None
    assert result == {"id": "receipt-1", "status": "approved"}
    assert executed.preview_json["_execution_result"] == result


def test_replay_does_not_duplicate_write(gestor_db, monkeypatch):
    db, tenant_id, admin_id = gestor_db
    operation = _confirmed(db, tenant_id, admin_id)
    calls = []
    monkeypatch.setattr(GestorService, "_execute_inventory_approve_receipt", lambda self, args: calls.append(args.document_id) or {"id": args.document_id})
    service = GestorService(db, tenant_id, admin_id)
    service.execute_tool(_body(operation.id))
    replay, result = service.execute_tool(_body(operation.id))
    assert calls == ["receipt-1"]
    assert replay.status == "EXECUTED"
    assert result == {"id": "receipt-1"}


def test_tenant_mismatch_is_rejected(gestor_db):
    db, tenant_id, admin_id = gestor_db
    operation = _confirmed(db, tenant_id, admin_id)
    with pytest.raises(GestorOperationNotFound):
        GestorService(db, str(uuid4()), admin_id).execute_tool(_body(operation.id))


def test_write_error_is_audited_as_failed(gestor_db, monkeypatch):
    db, tenant_id, admin_id = gestor_db
    operation = _confirmed(db, tenant_id, admin_id)
    def fail(self, args):
        raise RuntimeError("receipt service indisponivel")

    monkeypatch.setattr(GestorService, "_execute_inventory_approve_receipt", fail)
    with pytest.raises(RuntimeError, match="indisponivel"):
        GestorService(db, tenant_id, admin_id).execute_tool(_body(operation.id))
    assert operation.status == "FAILED"
    assert operation.executed_at is None
    assert "receipt service indisponivel" in operation.error

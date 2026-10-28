from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models.admin import AdminUser
from backend.models.gestor import GestorAuthorizedContact, GestorOperation
from backend.models.membership import TenantMembership
from backend.models.tenant import Tenant
from backend.schemas.gestor import GestorContactCreate, GestorOperationPreviewIn
from backend.services.gestor_service import GestorOperationInvalid, GestorService


@pytest.fixture()
def gestor_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, AdminUser.__table__, TenantMembership.__table__,
        GestorAuthorizedContact.__table__, GestorOperation.__table__,
    ])
    db = sessionmaker(bind=engine)()
    tenant_id = str(uuid4())
    admin_id = str(uuid4())
    db.add(Tenant(id=tenant_id, slug=f"gestor-{tenant_id[:8]}", name="Gestor Teste", status="active"))
    db.add(AdminUser(
        id=admin_id, email=f"gestor-{tenant_id[:8]}@test.invalid", name="Gestor Teste",
        password_hash="not-used", active=True,
    ))
    db.add(TenantMembership(
        id=str(uuid4()), tenant_id=tenant_id, user_id=admin_id,
        role="owner", status="active", is_default=True,
    ))
    db.commit()
    try:
        yield db, tenant_id, admin_id
    finally:
        db.close()
        engine.dispose()


def test_contacts_are_normalized_and_tenant_scoped(gestor_db):
    db, tenant_id, admin_id = gestor_db
    service = GestorService(db, tenant_id, admin_id)
    item = service.create_contact(GestorContactCreate(
        admin_user_id=admin_id, phone="+55 (11) 99999-0000",
        display_name="Operador", role="owner",
    ))
    assert item.phone_normalized == "5511999990000"
    assert len(service.list_contacts()) == 1


def test_preview_returns_one_time_token_and_confirmation_is_not_execution(gestor_db):
    db, tenant_id, admin_id = gestor_db
    service = GestorService(db, tenant_id, admin_id)
    operation, token = service.create_operation(GestorOperationPreviewIn(
        channel="gestor", phone="5511999990000", tool_name="inventory.read",
        risk_level="low", arguments={"item": "flour"}, preview={"read_only": True},
        idempotency_key="request-1",
    ))
    assert token
    assert operation.confirmation_token_hash != token
    confirmed = service.confirm_operation(operation.id, token)
    assert confirmed.status == "READY_TO_EXECUTE"
    assert confirmed.executed_at is None
    assert confirmed.confirmation_token_hash is None
    with pytest.raises(GestorOperationInvalid, match="nao esta aguardando"):
        service.confirm_operation(operation.id, token)


def test_invalid_and_expired_confirmation_are_rejected(gestor_db):
    db, tenant_id, admin_id = gestor_db
    service = GestorService(db, tenant_id, admin_id)
    operation, _token = service.create_operation(GestorOperationPreviewIn(
        channel="gestor", phone="5511999990000", tool_name="gestor.inventory.approve_receipt",
        risk_level="medium", arguments={"document_id": "receipt-1"},
        preview={"summary": "Aprovar recebimento receipt-1"}, idempotency_key="request-2",
    ))
    with pytest.raises(GestorOperationInvalid, match="invalido"):
        service.confirm_operation(operation.id, "wrong-token-value")
    operation.confirmation_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.flush()
    with pytest.raises(GestorOperationInvalid, match="expirado"):
        service.confirm_operation(operation.id, "wrong-token-value")
    assert operation.status == "EXPIRED"

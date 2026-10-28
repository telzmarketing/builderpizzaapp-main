import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models.admin import AdminUser
from backend.models.gestor import (
    GestorAutomation, GestorAutomationAudit, GestorAutomationRun, GestorOperation,
)
from backend.models.membership import TenantMembership
from backend.models.tenant import Tenant
from backend.schemas.gestor import (
    GestorAutomationCreate, GestorAutomationSimulateIn, GestorAutomationUpdate,
)
from backend.services.gestor_service import GestorOperationInvalid, GestorService


@pytest.fixture()
def automation_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, AdminUser.__table__, TenantMembership.__table__, GestorOperation.__table__,
        GestorAutomation.__table__, GestorAutomationRun.__table__, GestorAutomationAudit.__table__,
    ])
    db = sessionmaker(bind=engine)()
    tenant_id, other_tenant_id, admin_id = str(uuid4()), str(uuid4()), str(uuid4())
    db.add_all([
        Tenant(id=tenant_id, slug=f"auto-{tenant_id[:8]}", name="Automations", status="active"),
        AdminUser(id=admin_id, email=f"auto-{admin_id[:8]}@test.invalid", name="Gestor", password_hash="unused", active=True),
        TenantMembership(id=str(uuid4()), tenant_id=tenant_id, user_id=admin_id, role="owner", status="active", is_default=True),
    ])
    db.commit()
    db.execute(text("""
        CREATE TABLE automation_events (
            id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, event_key VARCHAR NOT NULL,
            payload_json TEXT NOT NULL, customer_id VARCHAR, aggregate_id VARCHAR,
            available_at DATETIME NOT NULL, occurred_at DATETIME NOT NULL, status VARCHAR NOT NULL
        )
    """))
    db.commit()
    try:
        yield db, tenant_id, other_tenant_id, admin_id
    finally:
        db.close()
        engine.dispose()


def _body(**overrides):
    values = {
        "name": "Pagamento confirmado",
        "description": "Avisar o administrador para confirmar o envio.",
        "trigger_key": "payment.confirmed",
        "conditions": [],
        "actions": [{"key": "notification.send_whatsapp", "config": {"message": "Pagamento de {amount} recebido."}}],
        "enabled": True,
        "dry_run": True,
        "service_window_start": "00:00",
        "service_window_end": "00:00",
    }
    values.update(overrides)
    return GestorAutomationCreate(**values)


def _event(db, tenant_id, payload=None, event_key="payment.confirmed"):
    event_id = str(uuid4())
    now = datetime.now(timezone.utc)
    db.execute(text("""
        INSERT INTO automation_events
        (id, tenant_id, event_key, payload_json, customer_id, aggregate_id, available_at, occurred_at, status)
        VALUES (:id, :tenant_id, :event_key, :payload, :customer_id, :aggregate_id, :available_at, :occurred_at, 'processed')
    """), {
        "id": event_id, "tenant_id": tenant_id, "event_key": event_key,
        "payload": json.dumps(payload or {"phone": "5511999990000", "amount": 42}),
        "customer_id": None, "aggregate_id": "payment-1", "available_at": now, "occurred_at": now,
    })
    db.commit()
    return event_id


def test_crud_is_tenant_scoped_and_uses_existing_trigger_whitelist(automation_db):
    db, tenant_id, other_tenant_id, admin_id = automation_db
    service = GestorService(db, tenant_id, admin_id)
    item = service.create_automation(_body())
    db.commit()

    assert item.trigger_key == "payment.confirmed"
    assert service.list_automations() == [item]
    assert GestorService(db, other_tenant_id, admin_id).list_automations() == []

    updated = service.update_automation(item.id, GestorAutomationUpdate(dry_run=False, enabled=False))
    assert updated.dry_run is False and updated.enabled is False
    assert db.query(GestorAutomationAudit).filter_by(automation_id=item.id).count() == 2
    deleted = service.delete_automation(item.id)
    assert deleted.enabled is False
    assert db.query(GestorAutomationAudit).filter_by(automation_id=item.id, event="deleted").count() == 1

    with pytest.raises(GestorOperationInvalid, match="whitelist"):
        service.create_automation(_body(trigger_key="unknown.event"))
    with pytest.raises(GestorOperationInvalid, match="so permite"):
        service.create_automation(_body(actions=[{"key": "notification.send_email", "config": {"message": "x"}}]))


def test_simulation_is_dry_run_and_respects_opt_out(automation_db):
    db, tenant_id, _other_tenant_id, admin_id = automation_db
    service = GestorService(db, tenant_id, admin_id)
    item = service.create_automation(_body(dry_run=True))

    preview = service.simulate_automation(item.id, GestorAutomationSimulateIn(
        event_key="payment.confirmed", payload={"phone": "5511999990000", "amount": 42},
    ))
    assert preview["matched"] is True
    assert preview["would_queue"] is False
    assert preview["dry_run"] is True

    opted_out = service.simulate_automation(item.id, GestorAutomationSimulateIn(
        event_key="payment.confirmed", payload={"phone": "5511999990000", "opt_out": True},
    ))
    assert opted_out["matched"] is False
    assert "opt-out" in opted_out["blocked_reason"]


def test_processing_uses_event_job_stream_is_idempotent_and_only_previews(automation_db, monkeypatch):
    db, tenant_id, _other_tenant_id, admin_id = automation_db
    service = GestorService(db, tenant_id, admin_id)
    item = service.create_automation(_body(dry_run=True))
    db.commit()
    event_id = _event(db, tenant_id)
    monkeypatch.setattr(
        "backend.services.automation_event_service.AutomationEventService.process_pending",
        lambda self, limit, worker_id: {"claimed": 1},
    )

    first = service.process_gestor_automation_events(limit=10)
    assert first["claimed"] == 1
    assert first["previews"] == 1
    assert first["confirmation_tokens"] == {}
    assert first["runs"][0].event_id == event_id
    assert db.query(GestorOperation).count() == 0

    second = service.process_gestor_automation_events(limit=10)
    assert second["idempotent_replays"] == 1
    assert db.query(GestorAutomationRun).count() == 1


def test_enabled_automation_creates_confirmation_operation_never_sends_implicitly(automation_db, monkeypatch):
    db, tenant_id, _other_tenant_id, admin_id = automation_db
    service = GestorService(db, tenant_id, admin_id)
    item = service.create_automation(_body(dry_run=False))
    db.commit()
    _event(db, tenant_id, payload={"phone": "5511999990000", "amount": 99})
    monkeypatch.setattr(
        "backend.services.automation_event_service.AutomationEventService.process_pending",
        lambda self, limit, worker_id: {"claimed": 0},
    )

    result = service.process_gestor_automation_events(limit=10)
    operation = db.query(GestorOperation).one()
    assert result["awaiting_confirmation"] == 1
    assert operation.status == "PENDING_CONFIRMATION"
    assert operation.tool_name == "gestor.whatsapp.send_message"
    assert operation.channel == "gestor_automation"
    assert result["confirmation_tokens"][operation.id]
    assert db.query(GestorAutomationAudit).filter_by(automation_id=item.id, event="event_processed").count() == 1

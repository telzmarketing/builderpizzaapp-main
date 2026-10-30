from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.models.gestor import (
    GestorOperation,
    GestorWhatsAppChannel,
    GestorWhatsAppMessage,
    GestorWhatsAppOutbox,
)
from backend.models.tenant import Tenant
from backend.schemas.gestor import GestorDashboardOut
from backend.services.gestor_service import GestorService


def _db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, GestorWhatsAppChannel.__table__, GestorWhatsAppMessage.__table__,
        GestorOperation.__table__, GestorWhatsAppOutbox.__table__,
    ])
    db = sessionmaker(bind=engine)()
    tenant_id = str(uuid4())
    other_tenant_id = str(uuid4())
    # SQLite cannot reproduce PostgreSQL's partial uniqueness for Tenant.is_legacy;
    # the second tenant id is still used to prove tenant predicates without a
    # second Tenant row (foreign keys are disabled in this isolated fixture).
    db.add(Tenant(id=tenant_id, slug=f"gestor-dashboard-{tenant_id[:8]}", name="Gestor", status="active"))
    db.commit()
    return engine, db, tenant_id, other_tenant_id


def _channel(tenant_id: str, enabled: bool = True):
    return GestorWhatsAppChannel(
        tenant_id=tenant_id, enabled=enabled, phone_number_id=f"phone-{uuid4()}",
        business_account_id="business-1", verify_token_hash="hash", app_secret_ref="env:TEST",
        status="ready" if enabled else "disabled",
    )


def test_dashboard_is_tenant_scoped_and_uses_only_gestor_tables():
    engine, db, tenant_id, other_tenant_id = _db()
    try:
        now = datetime.now(timezone.utc)
        channel = _channel(tenant_id)
        other_channel = _channel(other_tenant_id)
        db.add_all([channel, other_channel])
        db.flush()
        db.add_all([
            GestorWhatsAppMessage(
                tenant_id=tenant_id, channel_id=channel.id, provider_message_id="g-1",
                from_phone="5511999990000", message_type="text", text_body="status",
                status="RECEIVED", created_at=now,
            ),
            GestorWhatsAppMessage(
                tenant_id=tenant_id, channel_id=channel.id, provider_message_id="g-2",
                from_phone="5511999990000", message_type="text", text_body="failed",
                status="FAILED", created_at=now,
            ),
            GestorWhatsAppMessage(
                tenant_id=other_tenant_id, channel_id=other_channel.id, provider_message_id="other-1",
                from_phone="5511888880000", message_type="text", text_body="other",
                status="RECEIVED", created_at=now,
            ),
        ])
        operation = GestorOperation(
            tenant_id=tenant_id, channel="gestor", phone="5511999990000",
            tool_name="gestor.operations.summary", risk_level="low", status="READY_TO_EXECUTE",
            arguments_json={}, preview_json={}, idempotency_key="op-1",
        )
        other_operation = GestorOperation(
            tenant_id=other_tenant_id, channel="gestor", phone="5511888880000",
            tool_name="gestor.operations.summary", risk_level="low", status="EXECUTED",
            arguments_json={}, preview_json={}, idempotency_key="other-op",
        )
        db.add_all([operation, other_operation])
        db.flush()
        db.add_all([
            GestorWhatsAppOutbox(
                tenant_id=tenant_id, channel_id=channel.id, operation_id=operation.id,
                recipient_phone="5511999990000", body="pending", idempotency_key="out-1", status="pending",
            ),
            GestorWhatsAppOutbox(
                tenant_id=other_tenant_id, channel_id=other_channel.id, operation_id=other_operation.id,
                recipient_phone="5511888880000", body="other", idempotency_key="other-out", status="sent",
                sent_at=now,
            ),
        ])
        db.commit()

        result = GestorService(db, tenant_id, str(uuid4())).dashboard()
        assert isinstance(result, GestorDashboardOut)
        assert result.channels_total == 1
        assert result.channels_enabled == 1
        assert result.messages_total == 2
        assert result.messages_received_today == 2
        assert result.messages_failed == 1
        assert result.operations_total == 1
        assert result.operations_ready_to_execute == 1
        assert result.outbox_pending == 1
        assert result.outbox_sent_today == 0
    finally:
        db.close()
        engine.dispose()


def test_dashboard_does_not_count_old_gestor_rows_as_today():
    engine, db, tenant_id, _other_tenant_id = _db()
    try:
        channel = _channel(tenant_id)
        db.add(channel)
        db.flush()
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        db.add(GestorWhatsAppMessage(
            tenant_id=tenant_id, channel_id=channel.id, provider_message_id="old-1",
            from_phone="5511999990000", message_type="text", text_body="old",
            status="RECEIVED", created_at=yesterday,
        ))
        db.commit()
        result = GestorService(db, tenant_id, str(uuid4())).dashboard()
        assert result.messages_total == 1
        assert result.messages_received_today == 0
    finally:
        db.close()
        engine.dispose()


def test_tool_catalog_exposes_effective_permission_without_secrets():
    catalog = {item.name: item for item in GestorService.tool_catalog()}
    assert catalog["gestor.operations.summary"].permission == "view"
    assert catalog["gestor.operations.update_order_status"].permission == "edit"
    assert all("token" not in item.model_dump_json().lower() for item in catalog.values())

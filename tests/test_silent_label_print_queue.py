from datetime import datetime, timezone

import pytest
import importlib
import pkgutil
import backend.models as model_package
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.database import Base
from backend.core.exceptions import DomainError
from backend.core.tenant_context import TenantContext, TenantSource
from backend.models.label import LabelPrintJob
# Register the inventory tables referenced by the global SQLAlchemy mapper so
# this focused SQLite fixture can configure LabelService in isolation.
from backend.models.inventory import InventoryItem  # noqa: F401
from backend.models.customer import Customer  # noqa: F401
from backend.models.loyalty import CustomerLoyalty  # noqa: F401
from backend.models.payment import PaymentProviderCustomer  # noqa: F401
from backend.schemas.label import LabelTransportClaimIn, LabelTransportStatusIn
from backend.services.label_service import LabelService

# LabelService is part of the shared mapper registry; load all model modules so
# its unrelated relationship strings are resolvable in this isolated fixture.
for _module in pkgutil.iter_modules(model_package.__path__):
    importlib.import_module(f"backend.models.{_module.name}")


@pytest.fixture
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[LabelPrintJob.__table__])
    with Session(engine) as db:
        yield db


def make_job(db):
    job = LabelPrintJob(
        id="job-1", tenant_id="tenant-a", actor_id="actor-1", job_type="test",
        idempotency_key="queue-test-1", snapshot_json={"test": True},
        result_status="requested",
    )
    db.add(job)
    db.commit()
    return job


def service(db):
    return LabelService(db, TenantContext(tenant_id="tenant-a", source=TenantSource.JOB))


def test_transport_contract_uses_exact_states_and_validates_error_payload():
    assert LabelTransportClaimIn(agent_job_id="agent-1").agent_job_id == "agent-1"
    assert LabelTransportStatusIn(status="sent", agent_job_id="agent-1").status == "sent"
    with pytest.raises(ValueError):
        LabelTransportStatusIn(status="error", agent_job_id="agent-1")
    with pytest.raises(ValueError):
        LabelTransportStatusIn(status="confirmed", agent_job_id="agent-1", error="x")


def test_transport_state_machine_is_idempotent_and_tenant_scoped(session):
    make_job(session)
    svc = service(session)

    claimed = svc.claim_print_job("job-1", agent_job_id="agent-1")
    assert claimed["transport_status"] == "enqueued"
    assert claimed["attempt_count"] == 1
    with pytest.raises(DomainError, match="nao esta disponivel"):
        svc.claim_print_job("job-1", agent_job_id="agent-2")

    sent = svc.mark_print_job_sent("job-1", agent_job_id="agent-1", external_job_id="spool-1")
    assert sent["transport_status"] == "sent"
    with pytest.raises(DomainError, match="aguarda confirmacao"):
        svc.mark_print_job_confirmed("job-1", agent_job_id="agent-2")

    confirmed = svc.mark_print_job_confirmed("job-1", agent_job_id="spool-1")
    assert confirmed["transport_status"] == "confirmed"
    with pytest.raises(DomainError, match="aguarda confirmacao"):
        svc.mark_print_job_confirmed("job-1", agent_job_id="spool-1")


def test_transport_error_is_terminal_and_does_not_change_legacy_result(session):
    make_job(session)
    svc = service(session)
    svc.claim_print_job("job-1", agent_job_id="agent-1")
    failed = svc.mark_print_job_failed("job-1", agent_job_id="agent-1", error="offline", retry=False)
    assert failed["transport_status"] == "error"
    assert failed["result_status"] == "requested"
    assert failed["last_error"] == "offline"

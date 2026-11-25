"""Focused tests for the durable finance projection retry queue."""

from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.database import Base
from backend.models.finance_projection import FinanceProjectionEvent, utcnow
from backend.models.tenant import Tenant
from backend.services.finance_projection_queue import FinanceProjectionQueue


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Tenant.__table__, FinanceProjectionEvent.__table__])
    return engine


def test_enqueue_is_idempotent_per_tenant_and_redacts_payload():
    engine = _db()
    with Session(engine) as db:
        first = FinanceProjectionQueue(db, "tenant-a").enqueue(
            event_type="PaymentConfirmed",
            dedupe_key="payment:1",
            aggregate_type="payment",
            aggregate_id="payment-1",
            payload={"payment_id": "payment-1", "api_key": "secret", "nested": {"token": "x"}},
        )
        second = FinanceProjectionQueue(db, "tenant-a").enqueue(
            event_type="PaymentConfirmed",
            dedupe_key="payment:1",
            payload={"payment_id": "different", "api_key": "another-secret"},
        )
        other_tenant = FinanceProjectionQueue(db, "tenant-b").enqueue(
            event_type="PaymentConfirmed", dedupe_key="payment:1", payload={"payment_id": "payment-1"}
        )
        assert first.id == second.id
        assert other_tenant.id != first.id
        assert "secret" not in first.payload_json
        assert '"api_key":"[redacted]"' in first.payload_json
        assert db.query(FinanceProjectionEvent).count() == 2
    engine.dispose()


def test_claim_retry_then_processes_once():
    engine = _db()
    with Session(engine) as db:
        queue = FinanceProjectionQueue(db, "tenant-a")
        event = queue.enqueue(event_type="PurchaseConfirmed", dedupe_key="purchase:1", max_attempts=3)
        db.commit()

        claimed = queue.claim(worker_id="worker-1", limit=10)
        assert [row.id for row in claimed] == [event.id]
        assert claimed[0].status == "processing"
        assert claimed[0].attempts == 1
        assert queue.claim(worker_id="worker-2") == []

        assert queue.fail(event.id, worker_id="worker-1", error="transient", retry_delay_seconds=0) == "failed"
        db.expire_all()
        failed = db.get(FinanceProjectionEvent, event.id)
        assert failed.status == "failed"
        assert failed.attempts == 1
        assert failed.last_error == "transient"

        processed = []
        result = queue.process_pending(lambda item: processed.append(item.id), worker_id="worker-2")
        assert result == {"claimed": 1, "processed": 1, "failed": 0, "dead": 0}
        assert processed == [event.id]
        db.expire_all()
        done = db.get(FinanceProjectionEvent, event.id)
        assert done.status == "processed"
        assert done.attempts == 2
        assert queue.claim(worker_id="worker-3") == []
    engine.dispose()


def test_expired_final_lease_becomes_dead_without_exceeding_attempts():
    engine = _db()
    with Session(engine) as db:
        queue = FinanceProjectionQueue(db, "tenant-a")
        event = queue.enqueue(event_type="PaymentReversed", dedupe_key="payment:2", max_attempts=1)
        db.commit()
        assert len(queue.claim(worker_id="worker-1")) == 1
        row = db.get(FinanceProjectionEvent, event.id)
        row.locked_at = utcnow() - timedelta(minutes=10)
        db.commit()
        assert queue.claim(worker_id="worker-2") == []
        db.expire_all()
        terminal = db.get(FinanceProjectionEvent, event.id)
        assert terminal.status == "dead"
        assert terminal.attempts == 1
    engine.dispose()

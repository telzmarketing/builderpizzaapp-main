from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from backend.core.exceptions import TestOrderPurgeBlocked
from backend.routes.orders import admin_orders_router
from backend.services.order_test_purge_service import OrderTestPurgeService


def _archived_order(order_id="order-test", tenant_id="tenant-a"):
    return SimpleNamespace(
        id=order_id,
        tenant_id=tenant_id,
        archived_at=datetime.now(timezone.utc),
    )


def _session_for_locked_order(order):
    db = MagicMock()
    locked = MagicMock()
    locked.filter.return_value.with_for_update.return_value.first.return_value = order
    db.query.return_value = locked
    return db


def test_purge_deletes_only_allowed_rows_and_audits_atomically():
    order = _archived_order()
    db = _session_for_locked_order(order)
    service = OrderTestPurgeService(
        db, tenant_id="tenant-a", actor_id="admin-a", actor_name="Admin",
    )
    service._find_blockers = MagicMock(return_value=[])
    payment = SimpleNamespace(id="payment-test")
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = order
    # The service performs later payment/count queries through the same chain.
    locked = MagicMock()
    payment_query = MagicMock()
    items_query = MagicMock()
    db.query.side_effect = [locked, payment_query, items_query]
    locked.filter.return_value.with_for_update.return_value.first.return_value = order
    payment_query.filter.return_value.first.return_value = payment
    items_query.filter.return_value.count.return_value = 2

    with patch(
        "backend.services.order_test_purge_service.AdminAuditLog",
        side_effect=lambda **kwargs: SimpleNamespace(**kwargs),
    ):
        result = service._purge_locked(
            order_id="order-test",
            reason="simulação autorizada para limpeza",
            payload={"confirmation": "PURGE_TEST_ORDER"},
        )

    assert result == {
        "status": "purged",
        "order_id": "order-test",
        "deleted_payment": True,
        "deleted_order_items": 2,
    }
    assert db.delete.call_count == 2
    assert db.commit.call_count == 1
    audit = db.add.call_args_list[-1].args[0]
    assert audit.action == "purge_test_order"
    assert audit.tenant_id == "tenant-a"


def test_purge_requires_archived_order_and_reports_blocker():
    order = SimpleNamespace(id="order-test", tenant_id="tenant-a", archived_at=None)
    db = _session_for_locked_order(order)
    service = OrderTestPurgeService(
        db, tenant_id="tenant-a", actor_id="admin-a", actor_name="Admin",
    )

    with pytest.raises(TestOrderPurgeBlocked) as exc:
        service._purge_locked(
            order_id="order-test",
            reason="simulação autorizada para limpeza",
            payload={"confirmation": "PURGE_TEST_ORDER"},
        )

    assert exc.value.blockers == ("order_not_archived",)
    db.delete.assert_not_called()
    db.commit.assert_not_called()


def test_purge_is_tenant_scoped_and_does_not_find_other_tenant_order():
    db = _session_for_locked_order(None)
    service = OrderTestPurgeService(
        db, tenant_id="tenant-a", actor_id="admin-a", actor_name="Admin",
    )

    with pytest.raises(Exception) as exc:
        service._purge_locked(
            order_id="order-other-tenant",
            reason="simulação autorizada para limpeza",
            payload={"confirmation": "PURGE_TEST_ORDER"},
        )

    assert exc.value.__class__.__name__ == "OrderNotFound"
    db.delete.assert_not_called()


def test_purge_rolls_back_when_atomic_delete_commit_fails():
    order = _archived_order()
    db = _session_for_locked_order(order)
    payment_query = MagicMock()
    items_query = MagicMock()
    locked = db.query.return_value
    db.query.side_effect = [locked, payment_query, items_query]
    locked.filter.return_value.with_for_update.return_value.first.return_value = order
    payment_query.filter.return_value.with_for_update.return_value.first.return_value = None
    items_query.filter.return_value.count.return_value = 0
    db.commit.side_effect = SQLAlchemyError("write failed")
    service = OrderTestPurgeService(
        db, tenant_id="tenant-a", actor_id="admin-a", actor_name="Admin",
    )
    service._find_blockers = MagicMock(return_value=[])

    with patch(
        "backend.services.order_test_purge_service.AdminAuditLog",
        side_effect=lambda **kwargs: SimpleNamespace(**kwargs),
    ), pytest.raises(SQLAlchemyError):
        service._purge_locked(
            order_id="order-test",
            reason="simulação autorizada para limpeza",
            payload={"confirmation": "PURGE_TEST_ORDER"},
        )

    db.rollback.assert_called_once()
    assert db.delete.call_count == 1


def test_failed_purge_abandons_idempotency_claim_and_rolls_back():
    db = MagicMock()
    claim = SimpleNamespace(record=object(), replay_resource_id=None)
    idempotency = MagicMock()
    idempotency.claim.return_value = claim
    service = OrderTestPurgeService(
        db, tenant_id="tenant-a", actor_id="admin-a", actor_name="Admin",
    )
    blocked = TestOrderPurgeBlocked("order-test", ["finance_transactions"])

    with patch("backend.services.order_test_purge_service.IdempotencyService", return_value=idempotency), \
         patch.object(service, "_purge_locked", side_effect=blocked):
        with pytest.raises(TestOrderPurgeBlocked):
            service.purge(
                order_id="order-test",
                confirmation="PURGE_TEST_ORDER",
                reason="simulação autorizada para limpeza",
                idempotency_key="purge-1",
            )

    idempotency.abandon.assert_called_once_with(claim.record)
    idempotency.complete.assert_not_called()


def test_idempotency_replay_does_not_delete_again():
    db = MagicMock()
    idempotency = MagicMock()
    idempotency.claim.return_value = SimpleNamespace(record=object(), replay_resource_id="order-test")
    service = OrderTestPurgeService(
        db, tenant_id="tenant-a", actor_id="admin-a", actor_name="Admin",
    )

    with patch("backend.services.order_test_purge_service.IdempotencyService", return_value=idempotency):
        result = service.purge(
            order_id="order-test",
            confirmation="PURGE_TEST_ORDER",
            reason="simulação autorizada para limpeza",
            idempotency_key="purge-1",
        )

    assert result["status"] == "already_purged"
    db.delete.assert_not_called()


def test_success_marks_idempotency_record_before_atomic_commit():
    db = _session_for_locked_order(_archived_order())
    service = OrderTestPurgeService(
        db, tenant_id="tenant-a", actor_id="admin-a", actor_name="Admin",
    )
    record = SimpleNamespace(status="processing", resource_id=None)
    idempotency = MagicMock()
    idempotency.claim.return_value = SimpleNamespace(record=record, replay_resource_id=None)
    service._purge_locked = MagicMock(return_value={"status": "purged", "order_id": "order-test"})

    with patch("backend.services.order_test_purge_service.IdempotencyService", return_value=idempotency):
        service.purge(
            order_id="order-test",
            confirmation="PURGE_TEST_ORDER",
            reason="simulação autorizada para limpeza",
            idempotency_key="purge-atomic",
        )

    # The record is passed into the transaction; completion is not a second commit.
    service._purge_locked.assert_called_once()
    assert service._purge_locked.call_args.kwargs["idempotency_record"] is record
    idempotency.complete.assert_not_called()


def test_confirmation_schema_is_fixed_and_endpoint_is_separate_from_archive():
    paths = {route.path for route in admin_orders_router.routes}
    assert "/admin/orders/{order_id}/purge-test" in paths
    assert all(route.path != "/orders/{order_id}" for route in admin_orders_router.routes)
    purge_route = next(route for route in admin_orders_router.routes if route.path.endswith("/purge-test"))
    assert any(
        any(cell.cell_contents == "pedidos" for cell in (dependency.call.__closure__ or ()))
        and any(cell.cell_contents == "delete" for cell in (dependency.call.__closure__ or ()))
        for dependency in purge_route.dependant.dependencies
    )

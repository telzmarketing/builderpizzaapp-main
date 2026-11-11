from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import SQLAlchemyError

from backend.services.order_test_purge_service import ConfirmedSimulationPurgeService, OrderTestPurgeService


def _service(db):
    return OrderTestPurgeService(
        db, tenant_id="tenant-a", actor_id="admin-a", actor_name="Admin"
    )


def _confirmed_service(db):
    return ConfirmedSimulationPurgeService(
        db, tenant_id="tenant-a", actor_id="admin-a", actor_name="Admin"
    )


def _kds_queries(*, attempt=None, attempt_ids=(), consumption=None, assignment=None):
    unit_query = MagicMock()
    attempt_query = MagicMock()
    attempt_ids_query = MagicMock()
    consumption_query = MagicMock()
    assignment_query = MagicMock()
    unit_query.filter.return_value.with_for_update.return_value.all.return_value = [
        SimpleNamespace(id="unit-1", state="unassigned")
    ]
    attempt_query.filter.return_value.first.return_value = attempt
    attempt_ids_query.filter.return_value.all.return_value = [
        SimpleNamespace(id=value) for value in attempt_ids
    ]
    consumption_query.filter.return_value.first.return_value = consumption
    assignment_query.filter.return_value.first.return_value = assignment
    return [unit_query, attempt_query, attempt_ids_query, consumption_query, assignment_query]


def test_safe_unassigned_production_unit_has_no_kds_blocker():
    db = MagicMock()
    queries = _kds_queries()
    db.query.side_effect = [queries[0], queries[1], queries[3], queries[4]]
    service = _service(db)
    service._production_attempt_ids = MagicMock(return_value=[])
    with patch.object(service, "_find_production_unit_child_blockers", return_value=[]):
        assert service._find_production_unit_blockers("order-test") == []


def test_production_attempt_blocks_even_when_unit_is_cancelled_or_unassigned():
    db = MagicMock()
    queries = _kds_queries(attempt=SimpleNamespace(id="attempt-1"))
    db.query.side_effect = [queries[0], queries[1], queries[2], queries[3], queries[4]]
    service = _service(db)
    service._production_attempt_ids = MagicMock(return_value=[])
    with patch.object(service, "_find_production_unit_child_blockers", return_value=[]):
        blockers = service._find_production_unit_blockers("order-test")
    assert "production_attempts" in blockers


def test_production_consumption_blocks_purge_even_if_attempt_lookup_is_empty():
    db = MagicMock()
    queries = _kds_queries(
        attempt_ids=("attempt-legacy",),
        consumption=SimpleNamespace(id="consumption-1"),
    )
    db.query.side_effect = [queries[0], queries[1], queries[3], queries[4]]
    service = _service(db)
    service._production_attempt_ids = MagicMock(return_value=["attempt-legacy"])
    with patch.object(service, "_find_production_unit_child_blockers", return_value=[]):
        blockers = service._find_production_unit_blockers("order-test")
    assert "production_attempt_consumptions" in blockers


def test_active_production_unit_state_is_a_structured_blocker():
    db = MagicMock()
    queries = _kds_queries()
    queries[0].filter.return_value.with_for_update.return_value.all.return_value = [
        SimpleNamespace(id="unit-1", state="assembling")
    ]
    db.query.side_effect = [queries[0], queries[1], queries[3], queries[4]]
    service = _service(db)
    service._production_attempt_ids = MagicMock(return_value=[])
    with patch.object(service, "_find_production_unit_child_blockers", return_value=[]):
        blockers = service._find_production_unit_blockers("order-test")
    assert "production_units_unsafe_state" in blockers


def _confirmed_attempt_queries(*, attempt, consumption=None):
    unit_query = MagicMock()
    attempt_query = MagicMock()
    consumption_query = MagicMock()
    assignment_query = MagicMock()
    unit_query.filter.return_value.with_for_update.return_value.all.return_value = [
        SimpleNamespace(id="unit-1", state="cancelled")
    ]
    attempt_query.filter.return_value.all.return_value = [attempt]
    consumption_query.filter.return_value.first.return_value = consumption
    assignment_query.filter.return_value.first.return_value = None
    return [unit_query, attempt_query, consumption_query, assignment_query]


def test_confirmed_simulation_allows_cancelled_attempt_without_execution_evidence():
    db = MagicMock()
    attempt = SimpleNamespace(
        id="attempt-1",
        state="cancelled",
        started_at=None,
        stock_requested_at=None,
        assembly_finished_at=None,
        oven_started_at=None,
        oven_finished_at=None,
        checked_at=None,
        completed_at=None,
    )
    queries = _confirmed_attempt_queries(attempt=attempt)
    db.query.side_effect = queries
    service = _confirmed_service(db)
    with patch.object(service, "_find_production_unit_child_blockers", return_value=[]):
        assert service._find_production_unit_blockers("order-test") == []


def test_confirmed_simulation_allows_cancelled_attempt_with_stock_request_only():
    db = MagicMock()
    attempt = SimpleNamespace(
        id="attempt-1",
        state="cancelled",
        started_at=None,
        stock_requested_at="stock-requested",
        assembly_finished_at=None,
        oven_started_at=None,
        oven_finished_at=None,
        checked_at=None,
        completed_at=None,
    )
    queries = _confirmed_attempt_queries(attempt=attempt)
    db.query.side_effect = queries
    service = _confirmed_service(db)
    with patch.object(service, "_find_production_unit_child_blockers", return_value=[]):
        assert service._find_production_unit_blockers("order-test") == []


def test_confirmed_simulation_still_blocks_cancelled_attempt_with_real_execution():
    db = MagicMock()
    attempt = SimpleNamespace(
        id="attempt-1",
        state="cancelled",
        started_at="started",
        stock_requested_at="stock-requested",
        assembly_finished_at=None,
        oven_started_at=None,
        oven_finished_at=None,
        checked_at=None,
        completed_at=None,
    )
    queries = _confirmed_attempt_queries(attempt=attempt)
    db.query.side_effect = queries
    service = _confirmed_service(db)
    with patch.object(service, "_find_production_unit_child_blockers", return_value=[]):
        assert "production_attempts" in service._find_production_unit_blockers("order-test")


def test_confirmed_simulation_blocks_active_attempt():
    db = MagicMock()
    attempt = SimpleNamespace(
        id="attempt-1",
        state="assembling",
        started_at=None,
        stock_requested_at=None,
        assembly_finished_at=None,
        oven_started_at=None,
        oven_finished_at=None,
        checked_at=None,
        completed_at=None,
    )
    queries = _confirmed_attempt_queries(attempt=attempt)
    db.query.side_effect = queries
    service = _confirmed_service(db)
    with patch.object(service, "_find_production_unit_child_blockers", return_value=[]):
        assert "production_attempts" in service._find_production_unit_blockers("order-test")


def test_confirmed_simulation_blocks_cancelled_attempt_with_consumption():
    db = MagicMock()
    attempt = SimpleNamespace(
        id="attempt-1",
        state="cancelled",
        started_at=None,
        stock_requested_at=None,
        assembly_finished_at=None,
        oven_started_at=None,
        oven_finished_at=None,
        checked_at=None,
        completed_at=None,
    )
    queries = _confirmed_attempt_queries(
        attempt=attempt,
        consumption=SimpleNamespace(id="consumption-1"),
    )
    db.query.side_effect = queries
    service = _confirmed_service(db)
    with patch.object(service, "_find_production_unit_child_blockers", return_value=[]):
        assert "production_attempt_consumptions" in service._find_production_unit_blockers("order-test")


def test_kds_unit_is_deleted_before_order_commit_and_rollback_is_atomic():
    db = MagicMock()
    locked_order = SimpleNamespace(
        id="order-test", tenant_id="tenant-a", archived_at=SimpleNamespace(isoformat=lambda: "now")
    )
    order_query, payment_query, items_query, units_query = [MagicMock() for _ in range(4)]
    unit = SimpleNamespace(id="unit-1", state="cancelled")
    db.query.side_effect = [order_query, payment_query, items_query, units_query]
    order_query.filter.return_value.with_for_update.return_value.first.return_value = locked_order
    payment_query.filter.return_value.with_for_update.return_value.first.return_value = None
    items_query.filter.return_value.count.return_value = 0
    units_query.filter.return_value.with_for_update.return_value.all.return_value = [unit]
    db.commit.side_effect = SQLAlchemyError("write failed")
    service = _service(db)
    service._find_blockers = MagicMock(return_value=[])

    try:
        with patch(
            "backend.services.order_test_purge_service.AdminAuditLog",
            side_effect=lambda **kwargs: SimpleNamespace(**kwargs),
        ):
            service._purge_locked(
                order_id="order-test",
                reason="simulacao autorizada",
                payload={"confirmation": "PURGE_CONFIRMED_SIMULATION"},
            )
    except SQLAlchemyError:
        pass

    assert db.delete.call_args_list[0].args[0] is unit
    assert db.rollback.call_count == 1

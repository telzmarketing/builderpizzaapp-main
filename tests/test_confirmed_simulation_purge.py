from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from backend.core.exceptions import TestOrderPurgeBlocked
from backend.routes.orders import admin_orders_router
from backend.services.order_test_purge_service import (
    ConfirmedSimulationPurgeService,
    OrderTestPurgeService,
)


def _service():
    return ConfirmedSimulationPurgeService(
        MagicMock(), tenant_id="tenant-a", actor_id="admin-a", actor_name="Admin"
    )


def test_confirmed_simulation_success_uses_separate_operation_and_literal():
    service = _service()
    service._purge_locked = MagicMock(return_value={
        "status": "purged", "order_id": "order-test", "deleted_payment": True,
    })
    claim = SimpleNamespace(record=object(), replay_resource_id=None)
    idem = MagicMock()
    idem.claim.return_value = claim

    with patch(
        "backend.services.order_test_purge_service.IdempotencyService",
        return_value=idem,
    ):
        result = service.purge(
            order_id="order-test",
            confirmation="PURGE_CONFIRMED_SIMULATION",
            reason="limpeza autorizada de simulacao",
            idempotency_key="simulation-1",
        )

    assert result["status"] == "purged"
    payload = idem.claim.call_args.args[2]
    assert payload["confirmation"] == "PURGE_CONFIRMED_SIMULATION"
    assert idem.claim.call_args.args[1] == "orders.purge_confirmed_simulation"


def test_confirmed_simulation_rejects_wrong_confirmation():
    service = _service()
    with pytest.raises(TestOrderPurgeBlocked) as exc:
        service.purge(
            order_id="order-test",
            confirmation="PURGE_TEST_ORDER",
            reason="limpeza autorizada de simulacao",
            idempotency_key="simulation-2",
        )
    assert exc.value.blockers == ("confirmation_token_invalid",)
    service.db.delete.assert_not_called()


def test_confirmed_simulation_replays_idempotently_without_deleting():
    service = _service()
    idem = MagicMock()
    idem.claim.return_value = SimpleNamespace(record=object(), replay_resource_id="order-test")
    with patch(
        "backend.services.order_test_purge_service.IdempotencyService",
        return_value=idem,
    ):
        result = service.purge(
            order_id="order-test",
            confirmation="PURGE_CONFIRMED_SIMULATION",
            reason="limpeza autorizada de simulacao",
            idempotency_key="simulation-3",
        )
    assert result["status"] == "already_purged"
    service.db.delete.assert_not_called()


def test_confirmed_simulation_abandons_claim_after_rollback_failure():
    service = _service()
    claim = SimpleNamespace(record=object(), replay_resource_id=None)
    idem = MagicMock()
    idem.claim.return_value = claim
    idem_error = SQLAlchemyError("rollback")
    with patch(
        "backend.services.order_test_purge_service.IdempotencyService",
        return_value=idem,
    ), patch.object(service, "_purge_locked", side_effect=idem_error), pytest.raises(SQLAlchemyError):
        service.purge(
            order_id="order-test",
            confirmation="PURGE_CONFIRMED_SIMULATION",
            reason="limpeza autorizada de simulacao",
            idempotency_key="simulation-4",
        )
    idem.abandon.assert_called_once_with(claim.record)


def test_regular_purge_policy_is_unchanged_and_simulation_policy_is_explicit():
    assert OrderTestPurgeService.ALLOW_MANUAL_TEST_EXTERNAL_METADATA is False
    assert ConfirmedSimulationPurgeService.ALLOW_MANUAL_TEST_EXTERNAL_METADATA is True
    paths = {route.path for route in admin_orders_router.routes}
    assert "/admin/orders/{order_id}/purge-test" in paths
    assert "/admin/orders/{order_id}/purge-confirmed-simulation" in paths
    assert ConfirmedSimulationPurgeService.AUDIT_ACTION == "purge_confirmed_simulation"

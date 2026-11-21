"""Real unit/attempt transitions through the existing dispatch service."""
from datetime import datetime, timezone

import pytest

from backend.core.exceptions import DomainError
from backend.core.kds_stations import KDS_OPERATIONAL_ORDER, operational_stage
from backend.core.tenant_context import TenantContext, TenantSource
from backend.models.kds_production import ProductionAttempt, ProductionUnit
from backend.models.order import Order
from backend.models.payment import Payment
from backend.services.kds_service import KdsService
from test_kds_stock_gate import gate  # shared SQLite stock/production fixture


@pytest.mark.parametrize("station", ["pizza", "pizza-1", "pizza-2", "esfiha"])
def test_stages_keep_assembly_station_and_share_oven_dispatch(station):
    preparation = "esfiha" if station == "esfiha" else "pizza"
    assert KDS_OPERATIONAL_ORDER == ("pizza", "esfiha", "forno", "expedicao")
    assert [operational_stage(station, state) for state in (
        "queued", "checking_stock", "assembling", "assembled", "baking", "checking", "ready",
    )] == [preparation] * 4 + ["forno", "forno", "expedicao"]
    assert operational_stage(station, "cancelled") is None
    assert operational_stage("expedicao", "ready") == "expedicao"


def dispatch(gate):
    Payment.__table__.create(gate.db.get_bind(), checkfirst=True)
    service = KdsService(gate.db, gate.context)
    # Serialization is covered separately; preserve real database transition,
    # latest-attempt resolution, readiness and audit logic in these tests.
    service._serialize_orders = lambda orders, **kw: [{"id": row.id} for row in orders]
    return service


def oven_task(gate, station="esfiha"):
    # A second pending unit keeps the parent preparing until both are ready.
    second = gate.db.get(ProductionUnit, "unit2")
    second.order_id = "order1"
    attempt = gate.db.get(ProductionAttempt, "task1")
    attempt.state = attempt.unit.state = "baking"
    attempt.unit.station_id = station
    attempt.oven_started_at = datetime.now(timezone.utc)
    gate.db.commit()
    return attempt


@pytest.mark.parametrize("station", ["pizza", "pizza-1", "pizza-2", "esfiha"])
def test_oven_handoff_then_packing_preserves_station(gate, station):
    attempt = oven_task(gate, station)
    service = dispatch(gate)
    with pytest.raises(DomainError) as exc:
        service.complete_dispatch_unit("order1", "unit1", expected_version=1, actor_id="packer")
    assert exc.value.code == "ProductionUnitNotReady"
    service.check_oven_in_dispatch("order1", "unit1", expected_version=1, actor_id="packer")
    assert attempt.state == attempt.unit.state == "ready"
    assert attempt.unit.station_id == station
    assert attempt.oven_finished_at and attempt.checked_at and attempt.completed_at
    assert attempt.unit.dispatch_completed_at is None
    assert gate.db.get(Order, "order1").status.value == "preparing"
    service.complete_dispatch_unit("order1", "unit1", expected_version=2, actor_id="packer")
    assert attempt.unit.dispatch_completed_at and attempt.unit.dispatch_completed_by == "packer"
    # Replayed packing is idempotent and does not advance version again.
    service.complete_dispatch_unit("order1", "unit1", expected_version=2, actor_id="packer")
    assert attempt.unit.version == 3


@pytest.mark.parametrize("state", ["queued", "assembling", "assembled", "cancelled"])
def test_dispatch_cannot_skip_oven(gate, state):
    attempt = gate.db.get(ProductionAttempt, "task1")
    attempt.state = attempt.unit.state = state
    gate.db.commit()
    with pytest.raises(DomainError) as exc:
        dispatch(gate).check_oven_in_dispatch("order1", "unit1", expected_version=1, actor_id="packer")
    assert exc.value.code == "OvenCheckNotEligible"
    assert attempt.state == state and attempt.unit.dispatch_completed_at is None


@pytest.mark.parametrize("status", ["cancelled", "delivered", "on_the_way"])
def test_oven_rejects_ineligible_parent(gate, status):
    attempt = oven_task(gate)
    gate.db.get(Order, "order1").status = status
    gate.db.commit()
    with pytest.raises(DomainError) as exc:
        dispatch(gate).check_oven_in_dispatch("order1", "unit1", expected_version=1, actor_id="packer")
    assert exc.value.code == "DispatchOrderNotReady"
    assert attempt.state == "baking"


def test_dispatch_rejects_stale_version_and_foreign_tenant(gate):
    attempt = oven_task(gate)
    with pytest.raises(DomainError) as exc:
        dispatch(gate).check_oven_in_dispatch("order1", "unit1", expected_version=0, actor_id="packer")
    assert exc.value.code == "VersionConflict"
    foreign = KdsService(gate.db, TenantContext("foreign", TenantSource.JOB))
    with pytest.raises(DomainError):
        foreign.check_oven_in_dispatch("order1", "unit1", expected_version=1, actor_id="packer")
    assert attempt.state == "baking"

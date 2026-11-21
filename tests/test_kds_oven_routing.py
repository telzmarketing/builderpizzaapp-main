from types import SimpleNamespace
from pathlib import Path

from backend.services.kds_service import KdsService
from backend.services.kds_production_service import KdsProductionService


ROOT = Path(__file__).resolve().parents[1]


def test_pizzaiolo_queue_releases_oven_states_to_dispatch():
    service = KdsProductionService.__new__(KdsProductionService)
    service._current_queue_attempts = lambda: [
        SimpleNamespace(
            id=f"task-{index}",
            started_at=None,
            attempt_number=1,
            state=state,
            operator_id="operator-1",
            created_at=index,
            unit=SimpleNamespace(
                station_id="pizza",
                order_item_id=f"item-{index}",
            ),
        )
        for index, state in enumerate(("queued", "assembling", "baking", "checking"))
    ]
    service._drink_item_ids = lambda _item_ids: set()
    service._payload = lambda row: {"state": row.state}

    tasks = service.queue("operator-1", "pizza")

    assert [task["state"] for task in tasks] == ["assembling", "queued"]


def test_dispatch_keeps_oven_states_and_expedição_pipeline_has_both_scroll_axes():
    service_source = (ROOT / "backend/services/kds_service.py").read_text(encoding="utf-8")
    css_source = (ROOT / "client/pages/admin/Expedicao.css").read_text(encoding="utf-8")

    assert 'unit["state"] in {"baking", "checking", "ready"}' in service_source
    assert "overflow: auto" in css_source
    assert "grid-template-columns: repeat(3, minmax(min(20rem, 88vw), 1fr))" in css_source
    assert "orientation: portrait" in css_source


def test_dispatch_oven_check_reconciles_a_stale_attempt_from_the_unit_state():
    assert KdsService._oven_check_is_eligible("baking", "assembled")
    assert KdsService._oven_check_is_eligible("checking", "baking")

    for attempt_state in ("ready", "blocked", "cancelled", None):
        assert not KdsService._oven_check_is_eligible("baking", attempt_state)
    for unit_state in ("queued", "assembled", "ready", "cancelled"):
        assert not KdsService._oven_check_is_eligible(unit_state, "assembled")

    service_source = (ROOT / "backend/services/kds_service.py").read_text(encoding="utf-8")
    dispatch = service_source[
        service_source.index("    def check_oven_in_dispatch(") :
        service_source.index("    def complete_dispatch_unit(")
    ]
    assert "old_unit_state = unit.state" in dispatch
    assert "attempt.state = unit.state = \"ready\"" in dispatch
    assert "self._audit_unit(order.id, unit.id, actor_id, old_unit_state, \"ready\", \"expedicao\")" in dispatch

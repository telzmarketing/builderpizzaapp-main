from types import SimpleNamespace
from pathlib import Path

from backend.services.kds_production_service import KdsProductionService


ROOT = Path(__file__).resolve().parents[1]


def test_pizzaiolo_queue_releases_oven_states_to_dispatch():
    service = KdsProductionService.__new__(KdsProductionService)
    service._current_queue_attempts = lambda: [
        SimpleNamespace(
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

    assert [task["state"] for task in tasks] == ["queued", "assembling"]


def test_dispatch_keeps_oven_states_and_expedição_pipeline_has_both_scroll_axes():
    service_source = (ROOT / "backend/services/kds_service.py").read_text(encoding="utf-8")
    css_source = (ROOT / "client/pages/admin/Expedicao.css").read_text(encoding="utf-8")

    assert 'unit["state"] in {"baking", "checking", "ready"}' in service_source
    assert "overflow: auto" in css_source
    assert "grid-template-columns: repeat(3, minmax(min(20rem, 88vw), 1fr))" in css_source
    assert "orientation: portrait" in css_source

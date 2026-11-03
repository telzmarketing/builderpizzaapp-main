from pathlib import Path

from backend.core.kds_stations import KDS_STATION_LABELS, station_scope
from backend.services.kds_production_service import KdsProductionService


ROOT = Path(__file__).resolve().parents[1]


def test_fixed_pizza_stations_have_stable_labels_and_legacy_visibility():
    assert KDS_STATION_LABELS["pizza-1"] == "Pizza 1"
    assert KDS_STATION_LABELS["pizza-2"] == "Pizza 2"
    assert station_scope("pizza-1") == ("pizza-1", "pizza")
    assert station_scope("pizza-2") == ("pizza-2", "pizza")


def test_kds_accepts_fixed_stations_without_breaking_legacy_station():
    assert KdsProductionService.normalize_station("pizza-1") == "pizza-1"
    assert KdsProductionService.normalize_station("pizza-2") == "pizza-2"
    assert KdsProductionService.normalize_station("pizza") == "pizza"
    assert KdsProductionService.normalize_station("cozinha") == "pizza"


def test_schema_and_migration_keep_station_contract_tenant_safe():
    model = (ROOT / "backend/models/kds_production.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend/migrations/versions/20261104_fixed_pizza_stations.py").read_text(encoding="utf-8")
    schema = (ROOT / "backend/schemas/kds_production.py").read_text(encoding="utf-8")
    vision = (ROOT / "backend/services/production_vision_service.py").read_text(encoding="utf-8")
    assert "pizza-1" in model and "pizza-2" in model
    assert "ck_production_unit_station" in migration
    assert "tenant_id" in vision
    assert 'Literal["pizza", "pizza-1", "pizza-2", "esfiha"]' in schema
    assert "ProductionVisionStationInvalid" in vision

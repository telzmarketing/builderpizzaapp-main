from pathlib import Path

from backend.core.kds_stations import KDS_STATION_LABELS
from backend.schemas.production_vision import StationIn, ZoneIn


ROOT = Path(__file__).resolve().parents[1]


def test_station_and_zone_crud_contract_is_tenant_scoped_and_allows_managed_stations():
    model = (ROOT / "backend/models/production_vision.py").read_text(encoding="utf-8")
    service = (ROOT / "backend/services/production_vision_service.py").read_text(encoding="utf-8")
    route = (ROOT / "backend/routes/production_vision.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend/migrations/versions/20261105_production_vision_station_crud.py").read_text(encoding="utf-8")

    assert StationIn(name="Bancada extra", identifier="bancada-extra").status == "active"
    assert ZoneIn(name="Zona A", identifier="zona-a", station_id="pizza-1").station_id == "pizza-1"
    assert KDS_STATION_LABELS["pizza-1"] == "Pizza 1"
    assert "class ProductionVisionStation" in model
    assert "tenant_id" in model and "uq_production_vision_stations_tenant_identifier" in model
    assert "def save_station" in service and "def delete_station" in service
    assert '"protected": False' in service
    assert "PIZZA_STATION_IDS" not in service
    assert "ProductionVisionFixedStationProtected" not in service
    assert "def delete_zone" in service and "ProductionVisionZoneInUse" in service
    assert 'router.post("/stations"' in route
    assert 'router.delete("/stations/{station_id}"' in route
    assert 'router.delete("/zones/{zone_id}"' in route
    assert 'revision = "20261105_production_vision_station_crud"' in migration
    assert 'down_revision = "20261104_fixed_pizza_stations"' in migration
    assert "op.alter_column" in migration


def test_custom_station_identifier_validation_and_fixed_station_ids():
    assert StationIn(name="Montagem", identifier="montagem-1", status="inactive").identifier == "montagem-1"
    assert set(("pizza-1", "pizza-2")).issubset(KDS_STATION_LABELS)

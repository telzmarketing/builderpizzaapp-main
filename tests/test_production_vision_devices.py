from pathlib import Path

from backend.schemas.production_vision import DeviceIn


ROOT = Path(__file__).resolve().parents[1]


def test_kds_devices_are_tenant_scoped_and_station_binding_is_unique():
    model = (ROOT / "backend/models/production_vision.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend/migrations/versions/20261117_production_vision_devices.py").read_text(encoding="utf-8")
    service = (ROOT / "backend/services/production_vision_service.py").read_text(encoding="utf-8")
    route = (ROOT / "backend/routes/production_vision.py").read_text(encoding="utf-8")

    device = DeviceIn(identifier="kds-pizza-1", name="Pizza 1", station_id="montagem-1")
    assert device.status == "active"
    assert 'class ProductionVisionDevice' in model
    assert 'ForeignKey("tenants.id"' in model
    assert 'uq_production_vision_devices_tenant_station' in model
    assert 'uq_production_vision_devices_tenant_station' in migration
    assert 'ProductionVisionLegacyStationNotAssignable' in service
    assert 'def save_device' in service and 'def delete_device' in service
    assert 'router.post("/devices"' in route
    assert 'router.put("/devices/{device_id}"' in route


def test_production_vision_rejects_legacy_stations_for_new_configuration_links():
    service = (ROOT / "backend/services/production_vision_service.py").read_text(encoding="utf-8")
    page = (ROOT / "client/pages/admin/ProductionVision.tsx").read_text(encoding="utf-8")

    assert 'station.get("station_type") == "legacy"' in service
    assert 'station.station_type !== "legacy"' in page
    assert '"/painel/kds/configuracoes"' in page

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_station_is_persisted_and_migration_backfills_without_commercial_split():
    model = (ROOT / "backend/models/kds_production.py").read_text(encoding="utf-8")
    migration = (ROOT / "backend/migrations/versions/20261101_kds_production_stations.py").read_text(encoding="utf-8")
    assert "station_id = Column(String(20)" in model
    assert "p.product_type = 'esfiha'" in migration
    assert "selected_drink_variant" in migration
    assert "production_units" in migration
    assert "orders" not in migration.split("def upgrade", 1)[1].split("def downgrade", 1)[0]


def test_esfiha_routing_reuses_units_attempts_and_is_idempotent():
    service = (ROOT / "backend/services/kds_production_service.py").read_text(encoding="utf-8")
    assert "def initialize_order" in service
    assert "if unit:" in service
    assert "return \"esfiha\" if product and product.product_type == \"esfiha\"" in service
    assert "ProductionAttempt" in service
    assert "def queue(self, actor_id, station_id=\"pizza\")" in service
    assert "def all_queued(self, station_id=\"pizza\")" in service


def test_mixed_and_drink_routing_stays_operationally_separate():
    service = (ROOT / "backend/services/kds_production_service.py").read_text(encoding="utf-8")
    assert 'return "expedicao"' in service
    assert 'row.unit.station_id == station_id' in service
    assert 'KdsStationConflict' in service


def test_esfiha_endpoint_and_commands_have_canonical_station_contract():
    routes = (ROOT / "backend/routes/kds.py").read_text(encoding="utf-8")
    schema = (ROOT / "backend/schemas/kds_production.py").read_text(encoding="utf-8")
    assert '/kitchen/esfiha/queue' in routes
    assert '/kitchen/esfiha/my-queue' in routes
    assert 'station_id: Literal["pizza", "esfiha"]' in schema
    assert 'Tarefa pertence a outra estacao operacional' in (ROOT / "backend/services/kds_production_service.py").read_text(encoding="utf-8")


def test_pending_tasks_are_visible_without_operator_and_assignment_is_station_scoped():
    service = (ROOT / "backend/services/kds_production_service.py").read_text(encoding="utf-8")
    assert 'row.operator_id is None' in service
    assert 'target_station = self.normalize_station' in service
    assert 'requested_state == "available"' in service

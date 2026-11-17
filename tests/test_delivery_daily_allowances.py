from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app  # noqa: F401 - register all ORM foreign-key targets
from backend.database import Base
from backend.models.delivery import (
    Delivery,
    DeliveryDailyAllowance,
    DeliveryEarning,
    DeliveryPerson,
    DeliveryPersonStatus,
    LogisticsSettings,
)
from backend.models.order import Order
from backend.models.tenant import Tenant
from backend.schemas.delivery import LogisticsSettingsUpdate
from backend.services.delivery_service import DeliveryService


def _session(monkeypatch):
    monkeypatch.setattr("backend.services.delivery_service.wave7_orm_enabled", lambda: False)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[
        Tenant.__table__, Order.__table__, DeliveryPerson.__table__, Delivery.__table__,
        LogisticsSettings.__table__, DeliveryEarning.__table__,
        DeliveryDailyAllowance.__table__,
    ])
    return engine, sessionmaker(bind=engine)()


def test_daily_allowance_is_idempotent_per_tenant_driver_and_day(monkeypatch):
    engine, db = _session(monkeypatch)
    db.add_all([
        Tenant(id="tenant-a", slug="tenant-a", name="A"),
        LogisticsSettings(id="default", tenant_id="tenant-a", daily_allowance_amount=50),
        DeliveryPerson(id="driver-a", tenant_id="tenant-a", name="A", phone="1", status=DeliveryPersonStatus.offline),
    ])
    db.commit()
    service = DeliveryService(db, tenant_id="tenant-a")

    assert service.ensure_daily_allowances(period_date=date(2026, 11, 15)) == 1
    assert service.ensure_daily_allowances(period_date=date(2026, 11, 15)) == 0
    rows = db.query(DeliveryDailyAllowance).all()
    assert len(rows) == 1
    assert rows[0].amount == 50
    engine.dispose()


def test_driver_override_wins_over_logistics_default(monkeypatch):
    engine, db = _session(monkeypatch)
    db.add_all([
        Tenant(id="tenant-a", slug="tenant-a", name="A"),
        LogisticsSettings(id="default", tenant_id="tenant-a", daily_allowance_amount=50),
        DeliveryPerson(id="driver-a", tenant_id="tenant-a", name="A", phone="1", status=DeliveryPersonStatus.offline, daily_allowance_amount=75.5),
    ])
    db.commit()
    DeliveryService(db, tenant_id="tenant-a").ensure_daily_allowances(period_date=date(2026, 11, 15))
    assert db.query(DeliveryDailyAllowance).one().amount == 75.5
    engine.dispose()


def test_daily_allowance_settings_schema_and_existing_route_contract():
    payload = LogisticsSettingsUpdate(daily_allowance_amount=50)
    assert payload.daily_allowance_amount == 50
    assert LogisticsSettings.__table__.c.daily_allowance_amount.default.arg == 50.0
    route = Path("backend/routes/delivery.py").read_text(encoding="utf-8")
    assert '@router.get("/settings")' in route
    assert '@router.put("/settings")' in route
    assert "update_logistics_settings(**body.model_dump(exclude_none=True))" in route

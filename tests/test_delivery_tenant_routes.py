from pathlib import Path

import pytest

from backend.core.exceptions import DomainError
from backend.routes.delivery import _driver_login_service


ROUTE = Path("backend/routes/delivery.py")
SERVICE = Path("backend/services/delivery_service.py")


def test_delivery_routes_do_not_instantiate_global_service() -> None:
    source = ROUTE.read_text(encoding="utf-8")

    assert "DeliveryService(db)" not in source
    assert "_admin_service(request, db, admin)" in source
    assert "_driver_service(db, person_id)" in source
    assert "_delivery_service(db, delivery_id)" in source


def test_driver_login_is_tenant_scoped_before_password_check() -> None:
    route = ROUTE.read_text(encoding="utf-8")
    service = SERVICE.read_text(encoding="utf-8")

    assert "resolve_public_tenant_context(request, db)" in route
    assert "_driver_login_service(db, body.email, tenant_context).driver_login" in route
    assert ".limit(2).all()" in route
    assert "DriverTenantSelectionRequired" in route
    assert "DeliveryPerson.tenant_id == self._tenant_id" in service
    assert "func.lower(DeliveryPerson.email)" in service


class _LoginQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_conditions):
        return self

    def limit(self, _limit):
        return self

    def all(self):
        return self.rows

    def first(self):  # pragma: no cover - proves the login lookup never chooses a first row.
        raise AssertionError("login lookup must not call first()")


class _LoginDb:
    def __init__(self, rows):
        self.rows = rows

    def query(self, _model):
        return _LoginQuery(self.rows)


class _Driver:
    def __init__(self, driver_id: str, tenant_id: str):
        self.id = driver_id
        self.tenant_id = tenant_id


def test_driver_login_denies_ambiguous_email_before_password_check() -> None:
    with pytest.raises(DomainError) as exc:
        _driver_login_service(
            _LoginDb([_Driver("driver-a", "tenant-a"), _Driver("driver-b", "tenant-b")]),
            "driver@example.test",
            None,
        )
    assert exc.value.code == "DriverTenantSelectionRequired"


def test_wave7_logistics_fails_closed_and_scopes_runtime_reads() -> None:
    service = SERVICE.read_text(encoding="utf-8")
    route = ROUTE.read_text(encoding="utf-8")

    assert "wave7_orm_enabled" in service
    assert "Contexto confiavel obrigatorio para logistica da Wave 7." in service
    assert "self._scope(self._db.query(Delivery), Delivery)" in service
    assert "self._scope(self._db.query(DeliveryEarning), DeliveryEarning)" in service
    assert "self._scope(self._db.query(LogisticsSettings), LogisticsSettings)" in service
    assert "trusted_process_context(" in route

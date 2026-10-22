"""PostgreSQL constraints that must hold even when a writer bypasses services."""
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def foundation_constraints():
    url = os.environ.get("INVENTORY_FOUNDATION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires an explicitly configured disposable PostgreSQL database")
    from backend.main import app  # noqa: F401 -- register real model metadata, no startup
    from backend.models.admin import AdminUser
    from backend.models.tenant import Tenant
    from backend.models.inventory import InventoryItem, InventoryLocation, InventoryUnit
    from backend.models.inventory_foundation import InventoryOperation, InventoryLot

    engine = sa.create_engine(url, connect_args={"connect_timeout": 5})
    assert engine.dialect.name == "postgresql"
    with engine.connect() as connection:
        transaction = connection.begin()
        ids = {key: key + "-" + uuid.uuid4().hex for key in (
            "ta", "tb", "actor", "ia", "ia2", "ib", "la", "lb", "ua", "ub", "opa", "opb", "lota", "lotb",
        )}
        try:
            for key in ("ta", "tb"):
                connection.execute(Tenant.__table__.insert().values(id=ids[key], slug=ids[key], name="Constraint audit"))
            connection.execute(AdminUser.__table__.insert().values(
                id=ids["actor"], name="Constraint audit", email=ids["actor"] + "@example.invalid", password_hash="not-a-login",
            ))
            for tenant, unit, location, item, operation, lot in (
                ("ta", "ua", "la", "ia", "opa", "lota"),
                ("tb", "ub", "lb", "ib", "opb", "lotb"),
            ):
                connection.execute(InventoryUnit.__table__.insert().values(
                    id=ids[unit], tenant_id=ids[tenant], name="kg", symbol="kg",
                    dimension="mass", code="kg", conversion_factor=Decimal("1"),
                ))
                connection.execute(InventoryLocation.__table__.insert().values(id=ids[location], tenant_id=ids[tenant], name="Storage"))
                connection.execute(InventoryItem.__table__.insert().values(
                    id=ids[item], tenant_id=ids[tenant], name="Ingredient", unit_id=ids[unit], default_location_id=ids[location],
                ))
                connection.execute(InventoryOperation.__table__.insert().values(
                    id=ids[operation], tenant_id=ids[tenant], kind="manual_in", business_key="same-business",
                    idempotency_scope="same-scope", idempotency_key="same-key", request_hash="a" * 64,
                    actor_id="system:legacy-order",
                ))
                connection.execute(InventoryLot.__table__.insert().values(
                    id=ids[lot], tenant_id=ids[tenant], item_id=ids[item], location_id=ids[location],
                    lot_code="same-external-lot", received_at=datetime.now(timezone.utc), actor_id=ids["actor"],
                ))
            connection.execute(InventoryItem.__table__.insert().values(id=ids["ia2"], tenant_id=ids["ta"], name="Another ingredient"))
            yield connection, ids
        finally:
            transaction.rollback()
    engine.dispose()


def reject(connection, table, values):
    with connection.begin_nested() as nested:
        with pytest.raises(IntegrityError):
            connection.execute(table.insert().values(**values))
        nested.rollback()


def movement(ids, **changes):
    values = dict(
        id=uuid.uuid4().hex, tenant_id=ids["ta"], item_id=ids["ia"],
        location_id=ids["la"], source_type="foundation_test", quantity_delta=Decimal("1"),
        operation_id=ids["opa"], operation_sequence=1, lot_id=ids["lota"],
    )
    values.update(changes)
    return values


def test_movements_reject_foreign_tenant_operation_lot_and_wrong_lot_item(foundation_constraints):
    from backend.models.inventory import InventoryStockMovement
    connection, ids = foundation_constraints
    for changes in (
        {"operation_id": ids["opb"]}, {"lot_id": ids["lotb"]}, {"item_id": ids["ia2"]},
    ):
        reject(connection, InventoryStockMovement.__table__, movement(ids, **changes))


@pytest.mark.parametrize("changes", [
    {"operation_id": None}, {"operation_sequence": None}, {"operation_sequence": 0},
    {"operation_id": None, "operation_sequence": None},
])
def test_lot_movement_requires_complete_positive_operation_identity(foundation_constraints, changes):
    from backend.models.inventory import InventoryStockMovement
    connection, ids = foundation_constraints
    reject(connection, InventoryStockMovement.__table__, movement(ids, **changes))


def test_split_logical_line_has_unique_physical_sequences(foundation_constraints):
    from backend.models.inventory import InventoryStockMovement
    connection, ids = foundation_constraints
    table = InventoryStockMovement.__table__
    connection.execute(table.insert().values(**movement(ids, logical_line_id="one-logical-line")))
    connection.execute(table.insert().values(**movement(ids, operation_sequence=2, logical_line_id="one-logical-line")))
    reject(connection, table, movement(ids, logical_line_id="another-logical-line"))


def test_permanent_business_identity_and_request_identity_are_independent(foundation_constraints):
    from backend.models.inventory_foundation import InventoryOperation
    connection, ids = foundation_constraints
    base = dict(
        id=uuid.uuid4().hex, tenant_id=ids["ta"], kind="manual_in", business_key="same-business",
        idempotency_scope="same-scope", idempotency_key="new-key", request_hash="a" * 64,
        actor_id="system:legacy-order",
    )
    reject(connection, InventoryOperation.__table__, base)
    reject(connection, InventoryOperation.__table__, {**base, "business_key": "different-business", "idempotency_key": "same-key"})
    # The fixture successfully inserts the same business/request in another tenant.
    count = connection.scalar(sa.select(sa.func.count()).select_from(InventoryOperation.__table__).where(
        InventoryOperation.id.in_([ids["opa"], ids["opb"]]),
    ))
    assert count == 2


def test_packaging_rejects_cross_tenant_units_and_unmeasured_fixed_factor(foundation_constraints):
    from backend.models.inventory_foundation import InventoryItemPackaging
    connection, ids = foundation_constraints
    base = dict(
        id=uuid.uuid4().hex, tenant_id=ids["ta"], item_id=ids["ia"], name="Package",
        commercial_unit_id=ids["ua"], base_unit_id=ids["ua"], factor=Decimal("1"),
        variable_weight=False, actor_id=ids["actor"],
    )
    reject(connection, InventoryItemPackaging.__table__, {**base, "base_unit_id": ids["ub"]})
    reject(connection, InventoryItemPackaging.__table__, {**base, "item_id": ids["ib"]})
    reject(connection, InventoryItemPackaging.__table__, {**base, "factor": None})
    reject(connection, InventoryItemPackaging.__table__, {**base, "variable_weight": True})
    connection.execute(InventoryItemPackaging.__table__.insert().values(**{**base, "variable_weight": True, "factor": None}))


def test_reservation_rejects_foreign_location_or_wrong_lot_item(foundation_constraints):
    from backend.models.inventory_foundation import InventoryReservation
    connection, ids = foundation_constraints
    base = dict(
        id=uuid.uuid4().hex, tenant_id=ids["ta"], business_key=uuid.uuid4().hex,
        item_id=ids["ia"], lot_id=ids["lota"], location_id=ids["la"], operation_id=ids["opa"],
        source_type="manual", source_id="constraint-audit", quantity=Decimal("1"), actor_id=ids["actor"],
    )
    reject(connection, InventoryReservation.__table__, {**base, "location_id": ids["lb"]})
    reject(connection, InventoryReservation.__table__, {**base, "item_id": ids["ia2"]})
    reject(connection, InventoryReservation.__table__, {**base, "quantity": Decimal("NaN")})
    connection.execute(InventoryReservation.__table__.insert().values(**base))


def test_numeric_quantity_rejects_nan_without_inventing_legacy_lot(foundation_constraints):
    from backend.models.inventory import InventoryStockMovement
    connection, ids = foundation_constraints
    reject(connection, InventoryStockMovement.__table__, movement(ids, quantity_delta=Decimal("NaN")))
    connection.execute(InventoryStockMovement.__table__.insert().values(**movement(
        ids, operation_id=None, operation_sequence=None, lot_id=None, quantity_delta=Decimal("0.123456"),
    )))
    value = connection.scalar(sa.select(InventoryStockMovement.quantity_delta).where(
        InventoryStockMovement.tenant_id == ids["ta"], InventoryStockMovement.operation_id.is_(None),
    ))
    assert value == Decimal("0.123456")


def test_nonlot_movements_reject_foreign_tenant_item_or_location(foundation_constraints):
    from backend.models.inventory import InventoryStockMovement
    connection, ids = foundation_constraints
    for changes in ({"item_id": ids["ib"]}, {"location_id": ids["lb"]}):
        reject(connection, InventoryStockMovement.__table__, movement(ids, lot_id=None, **changes))

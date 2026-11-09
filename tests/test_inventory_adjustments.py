"""SQLite acceptance for tenant-scoped inventory count corrections and losses."""
from datetime import date
from decimal import Decimal
from importlib import import_module
from pkgutil import iter_modules
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.database import Base
import backend.models

# SQLAlchemy configures the shared mapper registry on the first model instance.
for module in iter_modules(backend.models.__path__):
    import_module(f"backend.models.{module.name}")
from backend.models.inventory import InventoryItem, InventoryLocation, InventoryStockMovement, InventoryUnit
from backend.models.inventory_foundation import InventoryLot, InventoryOperation, InventoryReservation
from backend.models.inventory_portion import InventoryPortionConfig
from backend.schemas.inventory import InventoryAdjustmentIn
from backend.services.inventory_adjustment_service import InventoryAdjustmentService
from backend.services.inventory_foundation_service import FoundationConflict, FoundationInvalid, FoundationNotFound


def body(kind="correction", quantity="10", expected="0", **kwargs):
    return InventoryAdjustmentIn(
        kind=kind, business_key=str(uuid4()), quantity=quantity,
        expected_physical=expected, reason="Contagem fisica", **kwargs,
    )


@pytest.fixture
def stock():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        InventoryUnit.__table__, InventoryLocation.__table__, InventoryItem.__table__,
        InventoryOperation.__table__, InventoryLot.__table__, InventoryReservation.__table__,
        InventoryStockMovement.__table__, InventoryPortionConfig.__table__,
    ])
    with Session(engine) as db:
        db.add_all([
            InventoryUnit(id="kg", tenant_id="tenant-a", name="Quilograma", symbol="KG", code="kg", dimension="mass", conversion_factor=Decimal("1")),
            InventoryUnit(id="gr", tenant_id="tenant-a", name="Grama", symbol="GR", code="gr", dimension="mass", conversion_factor=Decimal("0.001")),
            InventoryUnit(id="prq", tenant_id="tenant-a", name="Porcoes", symbol="PRQ", code="portion_count", dimension="count", conversion_factor=Decimal("1")),
            InventoryLocation(id="room", tenant_id="tenant-a", name="Camara"),
            InventoryLocation(id="other-room", tenant_id="tenant-a", name="Deposito"),
            InventoryLocation(id="foreign-room", tenant_id="tenant-b", name="Outra loja"),
            InventoryItem(id="ingredient", tenant_id="tenant-a", name="Queijo", item_type="ingredient", unit_id="kg", default_location_id="room"),
            InventoryItem(id="finished", tenant_id="tenant-a", name="Porcao", item_type="finished_good", unit_id="prq"),
            InventoryItem(id="legacy-portion", tenant_id="tenant-a", name="Porcao legada", item_type="finished_good", unit_id="gr"),
            InventoryItem(id="foreign", tenant_id="tenant-b", name="Outra loja", item_type="ingredient", unit_id="kg", default_location_id="foreign-room"),
        ])
        db.commit()
        yield db
    engine.dispose()


def service(db, tenant="tenant-a"):
    return InventoryAdjustmentService(db, tenant, "actor")


def test_correction_positive_negative_loss_and_zero_bucket(stock):
    svc = service(stock)
    initial = svc.buckets("finished")
    assert initial == [dict(location_id=None, location_name=None, lot_id=None, lot_code=None,
                            physical="0", reserved="0", available="0", unit_symbol="PRQ")]
    first = svc.adjust("finished", body(quantity="10"), "one")
    assert first["delta"] == "10" and first["unit_cost"] == "0"
    assert first["cost_status"] == "unvalued"
    assert svc.adjust("finished", body(quantity="8", expected="10"), "two")["delta"] == "-2.000000"
    assert svc.adjust("finished", body(kind="loss", quantity="3", expected="8"), "three")["physical"] == "5.000000"
    assert svc.buckets("finished")[0]["available"] == "5.000000"
    movements = stock.query(InventoryStockMovement).filter_by(item_id="finished").all()
    assert [row.quantity_delta for row in movements] == [Decimal("10"), Decimal("-2"), Decimal("-3")]
    assert all(row.operation_id and row.unit_cost == 0 for row in movements)
    assert all('"actor_id": "actor"' in row.notes and '"delta":' in row.notes for row in movements)


def test_ingredient_precision_and_stale_expected_physical(stock):
    svc = service(stock)
    assert svc.adjust("ingredient", body(quantity="0.123456"), "a")["physical"] == "0.123456"
    with pytest.raises(FoundationConflict) as exc:
        svc.adjust("ingredient", body(quantity="0.2", expected="0"), "b")
    assert exc.value.code == "VersionConflict"
    assert svc.adjust("ingredient", body(quantity="0.123455", expected="0.123456"), "c")["delta"] == "-0.000001"
    with pytest.raises(ValidationError):
        body(quantity="0.1234567")


def test_negative_legacy_bucket_can_be_corrected_to_zero(stock):
    stock.add(InventoryStockMovement(
        id="old-negative", tenant_id="tenant-a", item_id="ingredient", location_id="room",
        source_type="manual_entry", source_id="historical", movement_type="out",
        quantity_delta=Decimal("-2"), unit_cost=Decimal("0"), reason="legacy",
    ))
    stock.commit()
    result = service(stock).adjust("ingredient", body(quantity="0", expected="-2", location_id="room"), "repair")
    assert result["delta"] == "2.000000" and result["physical"] == "0.000000"
    assert service(stock).buckets("ingredient")[0]["physical"] == "0.000000"


def test_replay_payload_conflict_and_business_identity(stock):
    svc = service(stock)
    command = body(quantity="5")
    first = svc.adjust("ingredient", command, "same-http-key")
    assert svc.adjust("ingredient", command, "same-http-key") == first
    with pytest.raises(FoundationConflict) as changed:
        svc.adjust("ingredient", command.model_copy(update={"quantity": Decimal("6")}), "same-http-key")
    assert changed.value.code == "IdempotencyConflict"
    with pytest.raises(FoundationConflict) as duplicate:
        svc.adjust("ingredient", command, "different-http-key")
    assert duplicate.value.code == "BusinessIdentityConflict"
    assert stock.query(InventoryOperation).count() == 1
    assert stock.query(InventoryStockMovement).count() == 1


def test_reservations_prevent_loss_and_negative_balance(stock):
    svc = service(stock)
    svc.adjust("ingredient", body(quantity="10"), "seed")
    stock.add(InventoryReservation(
        id="reservation", tenant_id="tenant-a", business_key="reservation-1", item_id="ingredient",
        location_id="room", lot_id=None, source_type="manual", source_id="document", quantity=Decimal("7"),
        status="active", actor_id="actor",
    ))
    stock.commit()
    assert svc.buckets("ingredient")[0]["reserved"] == "7.000000"
    with pytest.raises(FoundationConflict):
        svc.adjust("ingredient", body(kind="loss", quantity="4", expected="10"), "too-low")
    with pytest.raises(FoundationConflict):
        svc.adjust("ingredient", body(quantity="6", expected="10"), "correction-too-low")
    with pytest.raises(FoundationConflict):
        svc.adjust("ingredient", body(kind="loss", quantity="11", expected="10"), "negative")
    assert svc.adjust("ingredient", body(kind="loss", quantity="3", expected="10"), "safe")["available"] == "0.000000"


@pytest.mark.parametrize("status,expires_on", [("blocked", None), ("available", date(2020, 1, 1))])
def test_exact_bucket_and_blocked_or_expired_lot_loss(stock, status, expires_on):
    stock.add(InventoryLot(id="lot", tenant_id="tenant-a", item_id="ingredient", location_id="room",
                           lot_code="L-1", status=status, expires_on=expires_on, actor_id="actor"))
    stock.add(InventoryStockMovement(
        id="empty-no-lot", tenant_id="tenant-a", item_id="ingredient", location_id="room",
        source_type="manual_entry", source_id="historical", movement_type="in",
        quantity_delta=Decimal("0"), unit_cost=Decimal("0"), reason="legacy",
    ))
    stock.commit()
    svc = service(stock)
    svc.adjust("ingredient", body(quantity="3", location_id="room", lot_id="lot"), "lot-seed")
    svc.adjust("ingredient", body(quantity="2", location_id="room"), "without-lot")
    result = svc.adjust("ingredient", body(kind="loss", quantity="1", expected="3", lot_id="lot"), "blocked-loss")
    assert result["location_id"] == "room" and result["lot_id"] == "lot"
    stock.add(InventoryReservation(
        id="lot-reservation", tenant_id="tenant-a", business_key="lot-reservation",
        item_id="ingredient", location_id="room", lot_id="lot", source_type="manual",
        source_id="document", quantity=Decimal("1"), status="active", actor_id="actor",
    ))
    stock.commit()
    with pytest.raises(FoundationConflict):
        svc.adjust("ingredient", body(kind="loss", quantity="2", expected="2", lot_id="lot"), "reserved-lot-loss")
    assert svc.buckets("ingredient")[0]["lot_code"] is None
    with pytest.raises(FoundationInvalid):
        svc.adjust("ingredient", body(quantity="1", location_id="other-room", lot_id="lot"), "wrong-location")
    with pytest.raises(FoundationNotFound):
        svc.adjust("ingredient", body(quantity="1", lot_id="missing"), "unknown-lot")
    assert svc.adjust("ingredient", body(quantity="4", expected="2", location_id="room"), "no-lot")["lot_id"] is None


def test_null_bucket_is_selected_exactly_among_other_locations(stock):
    stock.add(InventoryStockMovement(
        id="other-bucket", tenant_id="tenant-a", item_id="finished", location_id="room",
        source_type="manual_entry", source_id="historical", movement_type="in",
        quantity_delta=Decimal("3"), unit_cost=Decimal("0"), reason="legacy",
    ))
    stock.add(InventoryStockMovement(
        id="null-bucket", tenant_id="tenant-a", item_id="finished", location_id=None,
        source_type="manual_entry", source_id="historical", movement_type="in",
        quantity_delta=Decimal("0"), unit_cost=Decimal("0"), reason="legacy",
    ))
    stock.commit()
    result = service(stock).adjust("finished", body(quantity="2"), "null-only")
    assert result["location_id"] is None and result["physical"] == "2.000000"
    assert {row["location_id"]: row["physical"] for row in service(stock).buckets("finished")} == {
        None: "2.000000", "room": "3.000000",
    }


def test_tenant_isolation_and_foreign_location(stock):
    svc = service(stock)
    with pytest.raises(FoundationNotFound):
        svc.buckets("foreign")
    with pytest.raises(FoundationNotFound):
        svc.adjust("foreign", body(quantity="1"), "foreign-item")
    with pytest.raises(FoundationNotFound):
        svc.adjust("ingredient", body(quantity="1", location_id="foreign-room"), "foreign-location")
    assert stock.query(InventoryOperation).count() == 0


def test_prq_and_legacy_portion_output_require_integers(stock):
    svc = service(stock)
    with pytest.raises(FoundationInvalid) as exc:
        svc.adjust("finished", body(quantity="1.5"), "fraction-prq")
    assert exc.value.code == "InvalidQuantityPrecision"
    stock.add(InventoryPortionConfig(
        id=str(uuid4()), tenant_id="tenant-a", source_item_id="ingredient", output_item_id="legacy-portion",
        usage="mandatory", portion_weight=Decimal("10"), unit_id="gr", reference_fraction=Decimal("1"),
    ))
    stock.commit()
    with pytest.raises(FoundationInvalid):
        svc.adjust("legacy-portion", body(quantity="1.5"), "fraction-legacy")
    assert svc.adjust("legacy-portion", body(quantity="2"), "whole-legacy")["physical"] == "2"
    with pytest.raises(FoundationInvalid):
        svc.adjust("legacy-portion", body(kind="loss", quantity="0.5", expected="2"), "fraction-loss")

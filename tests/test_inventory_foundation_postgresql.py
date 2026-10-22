"""Real PostgreSQL acceptance for F1. Never uses the application's configured DB.

The CLI gate also verifies that CI actually ran the critical PostgreSQL suites.
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4


def verify_pg_report(path):
    from xml.etree import ElementTree

    cases = list(ElementTree.parse(path).getroot().iter("testcase"))
    required = {
        "test_inventory_foundation_postgresql": {
            "test_pg_manual_idempotence_and_business_identity",
            "test_pg_concurrent_reservations_and_manual_out_share_stock_lock",
            "test_pg_conversion_and_packaging_are_explicit_decimal",
            "test_pg_tenant_isolation_and_reconciliation",
        },
        "test_inventory_foundation_models": set(),
        "test_inventory_recipe_details_models": set(),
        "test_recipe_images": {"test_pg_recipe_image_roundtrip_auth_tenant_and_no_public_fallback"},
        "test_product_recipe_operations": {
            "test_pg_aggregate_stock_prevents_separate_lines_exceeding_balance",
            "test_pg_concurrent_preparation_serializes_idempotence_and_shared_stock",
        },
        "test_product_order_postgresql": {
            "test_checkout_reconfirmation_prevents_creation_and_preserves_option_snapshots",
        },
    }
    for module, names in required.items():
        found = [case for case in cases if module in case.get("classname", "")]
        if not found:
            raise SystemExit(f"Critical PostgreSQL suite was not collected: {module}")
        for name in names:
            if not any(case.get("name", "").split("[")[0] == name for case in found):
                raise SystemExit(f"Critical PostgreSQL case was not collected: {module}.{name}")
        incomplete = [case.get("name") for case in found if any(case.find(tag) is not None for tag in ("skipped", "failure", "error"))]
        if incomplete:
            raise SystemExit(f"Critical PostgreSQL cases did not pass: {module}: {incomplete}")
    print("Critical PostgreSQL gate: collected and passed, no skips")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--verify-pg-report":
        raise SystemExit("Usage: python tests/test_inventory_foundation_postgresql.py --verify-pg-report report.xml")
    verify_pg_report(sys.argv[2])
    raise SystemExit(0)

import pytest
from sqlalchemy import create_engine, func, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


@pytest.fixture
def foundation():
    url = os.environ.get("INVENTORY_FOUNDATION_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Requires explicit disposable INVENTORY_FOUNDATION_TEST_DATABASE_URL")
    parsed = make_url(url)
    assert parsed.get_backend_name() == "postgresql"
    assert parsed.host in ("127.0.0.1", "localhost", "postgres"), "Use an isolated local/CI PostgreSQL"
    assert "test" in (parsed.database or "") or (parsed.database or "").endswith("_ci")
    from backend.main import app  # noqa: F401 — register all existing relationships
    from backend.core.tenant_context import TenantContext, TenantSource
    from backend.models.admin import AdminUser
    from backend.models.tenant import Tenant
    from backend.models.inventory import InventoryItem, InventoryLocation, InventoryUnit
    from backend.services.inventory_foundation_service import InventoryFoundationService

    engine = create_engine(url, connect_args={"connect_timeout": 5}, pool_size=6)
    token = uuid4().hex
    tenant_id, other_id, actor_id = f"foundation-{token}", f"other-{token}", f"actor-{token}"
    context = TenantContext(tenant_id, TenantSource.JOB)
    with Session(engine) as db:
        assert db.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == "20261022_kds_production"
        db.add_all([Tenant(id=tenant_id, slug=tenant_id, name="Synthetic foundation", timezone="America/Sao_Paulo"),
                    Tenant(id=other_id, slug=other_id, name="Synthetic isolation", timezone="America/Sao_Paulo")])
        db.flush()
        db.add(AdminUser(id=actor_id, email=f"{token}@example.invalid", name="Synthetic operator", password_hash="not-a-login"))
        units = {}
        for code, dimension, factor in (("kg", "mass", "1"), ("g", "mass", "0.001"), ("l", "volume", "1"), ("piece", "count", "1")):
            uid = f"{code}-{token}"
            units[code] = uid
            db.add(InventoryUnit(id=uid, tenant_id=tenant_id, name=code, symbol=code, code=code,
                                 dimension=dimension, conversion_factor=Decimal(factor)))
        location_id, item_id = f"location-{token}", f"item-{token}"
        db.add(InventoryLocation(id=location_id, tenant_id=tenant_id, name="Synthetic room"))
        db.flush()
        db.add(InventoryItem(id=item_id, tenant_id=tenant_id, name="Synthetic cheese", unit_id=units["kg"], default_location_id=location_id))
        db.commit()

    def service(db, tenant=tenant_id):
        ctx = context if tenant == tenant_id else TenantContext(tenant, TenantSource.JOB)
        return InventoryFoundationService(db, tenant, actor_id, ctx)

    yield SimpleNamespace(engine=engine, tenant_id=tenant_id, other_id=other_id, actor_id=actor_id,
                          context=context, units=units, item_id=item_id, location_id=location_id, service=service)
    # UUID-scoped synthetic rows stay only in this explicitly selected disposable DB.
    # No drop_all, schema replacement, app DB fallback or deletion of other suites.
    engine.dispose()


def operation(case, quantity, *, kind="manual_in", business_key=None, lot_id=None):
    from backend.schemas.inventory_foundation import OperationIn
    return OperationIn(expected_version=0, kind=kind, business_key=business_key or uuid4().hex,
                       reason="synthetic acceptance", lines=[dict(item_id=case.item_id, quantity=quantity,
                       unit_id=case.units["kg"], location_id=case.location_id, lot_id=lot_id, unit_cost="37.00000000")])


def reservation(case, quantity, *, business_key=None, lot_id=None):
    from backend.schemas.inventory_foundation import ReservationIn
    return ReservationIn(expected_version=0, business_key=business_key or uuid4().hex, item_id=case.item_id,
                         location_id=case.location_id, lot_id=lot_id, quantity=quantity, unit_id=case.units["kg"],
                         source_type="manual", source_id="synthetic-source", reason="synthetic reservation")


def test_pg_manual_idempotence_and_business_identity(foundation):
    from backend.models.inventory import InventoryStockMovement
    from backend.models.inventory_foundation import InventoryOperation
    from backend.services.inventory_foundation_service import FoundationConflict
    case = foundation
    body = operation(case, "0.100001", business_key="physical-event")
    with Session(case.engine) as db:
        service = case.service(db)
        first = service.create_operation(body, "http-key")
        assert service.create_operation(body, "http-key") == first
        with pytest.raises(FoundationConflict):
            service.create_operation(operation(case, "0.200001", business_key="different-event"), "http-key")
        with pytest.raises(FoundationConflict):
            service.create_operation(body, "another-http-key")
        stored = db.query(InventoryOperation).filter_by(tenant_id=case.tenant_id, kind="manual_in").one()
        assert stored.result_json["_request_snapshot"]["lines"][0]["quantity"] == "0.100001"
        assert stored.result_json["_request_snapshot"]["lines"][0]["unit_id"] == case.units["kg"]
        assert "_request_snapshot" not in first
        movements = db.query(InventoryStockMovement).filter_by(tenant_id=case.tenant_id).all()
        assert len(movements) == 1
        assert movements[0].quantity_delta == Decimal("0.100001")
        assert movements[0].unit_cost == Decimal("37.00000000")


def test_pg_multi_line_failure_rolls_back_entire_operation(foundation):
    from backend.models.inventory import InventoryStockMovement
    from backend.services.inventory_foundation_service import FoundationConflict
    case = foundation
    with Session(case.engine) as db:
        service = case.service(db)
        service.create_operation(operation(case, "1"), "seed")
        body = operation(case, "0.6", kind="manual_out")
        body.lines.append(body.lines[0].model_copy())
        with pytest.raises(FoundationConflict):
            service.create_operation(body, "too-much")
        assert db.query(InventoryStockMovement).filter_by(tenant_id=case.tenant_id).count() == 1
        assert service.balances(case.item_id)["items"][0]["physical"] == "1.000000"


def test_pg_concurrent_reservations_and_manual_out_share_stock_lock(foundation):
    from backend.models.inventory_foundation import InventoryReservation
    from backend.services.inventory_foundation_service import FoundationConflict
    case = foundation
    with Session(case.engine) as db:
        case.service(db).create_operation(operation(case, "10"), "seed")
    barrier = Barrier(2)

    def run(index):
        with Session(case.engine) as db:
            barrier.wait(timeout=15)
            try:
                service = case.service(db)
                if index == 0:
                    service.reserve(reservation(case, "7"), "reserve")
                else:
                    service.create_operation(operation(case, "7", kind="manual_out"), "withdraw")
                return "ok"
            except FoundationConflict:
                return "insufficient"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, [0, 1])) == ["insufficient", "ok"]
    with Session(case.engine) as db:
        balance = case.service(db).balances(case.item_id)["items"][0]
        assert Decimal(balance["available"]) == Decimal("3")
        reserved = db.query(func.coalesce(func.sum(InventoryReservation.quantity), 0)).filter_by(tenant_id=case.tenant_id, status="active").scalar()
        assert Decimal(balance["physical"]) - reserved == Decimal("3")


def test_pg_concurrent_identical_command_commits_once(foundation):
    from backend.models.inventory import InventoryStockMovement
    case = foundation
    body = operation(case, "2.000001")
    barrier = Barrier(2)

    def run(_):
        with Session(case.engine) as db:
            barrier.wait(timeout=15)
            return case.service(db).create_operation(body, "same-key")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, [0, 1]))
    assert results[0] == results[1]
    with Session(case.engine) as db:
        assert db.query(InventoryStockMovement).filter_by(tenant_id=case.tenant_id).count() == 1


def test_pg_reservation_release_retry_preserves_physical_balance(foundation):
    from backend.schemas.inventory_foundation import ReleaseIn
    case = foundation
    with Session(case.engine) as db:
        service = case.service(db)
        service.create_operation(operation(case, "10"), "seed")
        body = reservation(case, "7")
        held = service.reserve(body, "reserve")
        assert service.reserve(body, "reserve") == held
        assert service.balances(case.item_id)["items"][0]["available"] == "3.000000"
        command = ReleaseIn(expected_version=held["version"], reason="synthetic release")
        released = service.release(held["id"], command, "release")
        assert service.release(held["id"], command, "release") == released
        balance = service.balances(case.item_id)["items"][0]
        assert Decimal(balance["physical"]) == Decimal("10")
        assert Decimal(balance["available"]) == Decimal("10")


def test_pg_conversion_and_packaging_are_explicit_decimal(foundation):
    from backend.schemas.inventory_foundation import ConversionPreviewIn, PackagingIn
    from backend.services.inventory_foundation_service import FoundationInvalid
    case = foundation
    with Session(case.engine) as db:
        service = case.service(db)
        result = service.preview(ConversionPreviewIn(item_id=case.item_id, quantity="150", unit_id=case.units["g"]))
        assert result["quantity"] == "0.150000"
        fixed = service.create_packaging(PackagingIn(expected_version=0, name="4 kg piece", item_id=case.item_id,
            commercial_unit_id=case.units["piece"], base_unit_id=case.units["kg"], factor="4"), "fixed-pack")
        result = service.preview(ConversionPreviewIn(item_id=case.item_id, quantity="10", unit_id=case.units["piece"], packaging_id=fixed["id"]))
        assert result["quantity"] == "40.000000"
        variable = service.create_packaging(PackagingIn(expected_version=0, name="weighed piece", item_id=case.item_id,
            commercial_unit_id=case.units["piece"], base_unit_id=case.units["kg"], variable_weight=True), "variable-pack")
        with pytest.raises(FoundationInvalid):
            service.preview(ConversionPreviewIn(item_id=case.item_id, quantity="10", unit_id=case.units["piece"], packaging_id=variable["id"]))
        measured = service.preview(ConversionPreviewIn(item_id=case.item_id, quantity="10", unit_id=case.units["piece"],
            packaging_id=variable["id"], measured_quantity="40001", measured_unit_id=case.units["g"]))
        assert measured["quantity"] == "40.001000"
        with pytest.raises(FoundationInvalid):
            service.preview(ConversionPreviewIn(item_id=case.item_id, quantity="1", unit_id=case.units["l"]))


def test_pg_tenant_isolation_and_reconciliation(foundation):
    from backend.services.inventory_foundation_service import FoundationNotFound
    case = foundation
    with Session(case.engine) as db:
        service = case.service(db)
        service.create_operation(operation(case, "1.500001"), "seed")
        before = service.balances(case.item_id)
        report = service.reconciliation()
        assert report["read_only"] is True
        assert report["items"][0]["issues"] == ["legacy_without_lot"]
        assert service.balances(case.item_id) == before
        other = case.service(db, case.other_id)
        with pytest.raises(FoundationNotFound):
            other.balances(case.item_id)
        db.rollback()
        with pytest.raises(FoundationNotFound):
            other.create_operation(operation(case, "1"), "seed")
        assert other.balances()["items"] == []


def test_pg_legacy_bucket_reservation_does_not_reserve_a_different_lot(foundation):
    from backend.schemas.inventory_foundation import LotIn
    case = foundation
    with Session(case.engine) as db:
        service = case.service(db)
        lot = service.create_lot(LotIn(expected_version=0, item_id=case.item_id, location_id=case.location_id,
            lot_code="synthetic", received_at=datetime.now(timezone.utc),
            effective_expires_at=datetime.now(timezone.utc)+timedelta(days=2)), "lot")
        service.create_operation(operation(case, "5"), "legacy-seed")
        service.create_operation(operation(case, "5", lot_id=lot["id"]), "lot-seed")
        service.reserve(reservation(case, "5"), "legacy-reserve")
        service.create_operation(operation(case, "5", kind="manual_out", lot_id=lot["id"]), "lot-out")
        rows = service.balances(case.item_id)["items"]
        assert sum((Decimal(row["physical"]) for row in rows), Decimal(0)) == Decimal("5")
        assert sum((Decimal(row["reserved"]) for row in rows), Decimal(0)) == Decimal("5")


def test_pg_legacy_preparing_consumes_split_lots_once_and_preserves_reserved_stock(foundation):
    from backend.models.product import Product
    from backend.models.order import Order, OrderItem, OrderStatus
    from backend.models.gestao import GestaoModuleSettings
    from backend.models.inventory import InventoryRecipeVersion, InventoryRecipeItem, InventoryStockMovement
    from backend.schemas.inventory_foundation import LotIn
    from backend.services.inventory_service import InventoryService
    case = foundation
    with Session(case.engine) as db:
        service = case.service(db)
        lot_ids = []
        for index, quantity in enumerate(("0.4", "0.6")):
            lot = service.create_lot(LotIn(expected_version=0, item_id=case.item_id, location_id=case.location_id,
                lot_code=f"split-{index}", received_at=datetime.now(timezone.utc),
                effective_expires_at=datetime.now(timezone.utc)+timedelta(days=index+1)), f"lot-{index}")
            service.create_operation(operation(case, quantity, lot_id=lot["id"]), f"in-{index}")
            lot_ids.append(lot["id"])
        service.reserve(reservation(case, "0.2", lot_id=lot_ids[0]), "reserve-other")
        pid, oid, rid = uuid4().hex, uuid4().hex, uuid4().hex
        db.add(Product(id=pid, tenant_id=case.tenant_id, name="Synthetic pizza", description="", price=50, product_type="pizza"))
        db.add(GestaoModuleSettings(id=uuid4().hex, tenant_id=case.tenant_id, module_key="inventory", title="Inventory",
            enabled=True, status="active", settings_json='{"sales_control_enabled":true,"auto_consume_on_preparing":true}'))
        db.flush()
        db.add(InventoryRecipeVersion(id=rid, tenant_id=case.tenant_id, product_id=pid, component_role="flavor", reference_fraction=1, active=True))
        db.add(Order(id=oid, tenant_id=case.tenant_id, status=OrderStatus.preparing, subtotal=50,total=50,
            fulfillment_type="pickup",preparation_started_at=datetime.now(timezone.utc)))
        db.flush()
        db.add(InventoryRecipeItem(id=uuid4().hex,tenant_id=case.tenant_id,recipe_id=rid,inventory_item_id=case.item_id,quantity=Decimal("0.6"),waste_percent=0))
        db.add(OrderItem(id=uuid4().hex,tenant_id=case.tenant_id,order_id=oid,product_id=pid,quantity=1,unit_price=50,total_price=50))
        db.commit()
        legacy=InventoryService(db,case.tenant_id,case.context)
        assert legacy.consume_order_sale(oid)["deducted"]
        db.commit()
        assert legacy.consume_order_sale(oid)["reason"] == "already_deducted"
        movements=db.query(InventoryStockMovement).filter_by(tenant_id=case.tenant_id,source_type="foundation_order_sale",source_id=oid).all()
        assert len(movements)==2
        assert sum((-m.quantity_delta for m in movements),Decimal(0))==Decimal("0.6")
        assert {m.lot_id for m in movements}==set(lot_ids)
        assert all(m.operation_id and m.operation_sequence for m in movements)
        balances=service.balances(case.item_id)["items"]
        assert sum((Decimal(b["physical"]) for b in balances),Decimal(0))==Decimal("0.4")
        assert sum((Decimal(b["reserved"]) for b in balances),Decimal(0))==Decimal("0.2")
        assert legacy.reverse_order_sale(oid)["reason"]=="production_loss_recorded"
        db.commit()
        assert legacy.reverse_order_sale(oid)["reason"]=="loss_already_recorded"
        assert sum((Decimal(b["physical"]) for b in service.balances(case.item_id)["items"]),Decimal(0))==Decimal("0.4")


def test_pg_manual_reversal_is_audited_and_cannot_remove_reserved_stock(foundation):
    from backend.schemas.inventory import InventoryManualEntryIn
    from backend.schemas.inventory_foundation import ReleaseIn
    from backend.services.inventory_service import InventoryService
    from backend.services.inventory_foundation_service import FoundationConflict
    from backend.models.inventory import InventoryStockMovement
    case=foundation
    with Session(case.engine) as db:
        service=case.service(db)
        legacy=InventoryService(db,case.tenant_id,case.context)
        entry=legacy.create_manual_entry(InventoryManualEntryIn(item_id=case.item_id,location_id=case.location_id,quantity="0.5",unit_cost="37"))
        held=service.reserve(reservation(case,"0.4"),"hold")
        with pytest.raises(FoundationConflict):
            legacy.delete_manual_entry(entry["id"])
        db.rollback()
        service.release(held["id"],ReleaseIn(expected_version=held["version"],reason="synthetic release"),"release")
        legacy.delete_manual_entry(entry["id"])
        legacy.delete_manual_entry(entry["id"])
        assert db.query(InventoryStockMovement).filter_by(tenant_id=case.tenant_id).count()==2
        assert legacy.list_manual_entries()[0]["reversed"] is True
        assert service.balances(case.item_id)["items"][0]["physical"]=="0.000000"


def test_pg_http_dto_strings_and_header_replay(foundation):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.routes import inventory_foundation as routes
    from backend.database import get_db
    case=foundation
    app=FastAPI()
    app.include_router(routes.router,prefix="/api")
    actor=SimpleNamespace(tenant_id=case.tenant_id,user_id=case.actor_id,tenant_context=case.context)
    def db_session():
        with Session(case.engine) as db:
            yield db
    app.dependency_overrides[get_db]=db_session
    for permission in (routes.view,routes.manage,routes.create,routes.edit):
        app.dependency_overrides[permission]=lambda: actor
    with TestClient(app) as client:
        path="/api/gestao/inventory/v1/operations"
        body=operation(case,"0.100001").model_dump(mode="json")
        assert client.post(path,json=body).status_code==422
        response=client.post(path,json=body,headers={"Idempotency-Key":"http-test"})
        assert response.status_code==201, response.text
        assert response.json()["lines"][0]["quantity"]=="0.100001"
        assert client.post(path,json=body,headers={"Idempotency-Key":"http-test"}).json()==response.json()
        balance=client.get("/api/gestao/inventory/v1/balances").json()["items"][0]
        assert balance["physical"]=="0.100001"


def test_pg_cancel_before_production_releases_order_reservation_and_forbids_new_hold(foundation):
    from backend.models.order import Order, OrderStatus
    from backend.schemas.inventory_foundation import ReservationIn
    from backend.services.inventory_service import InventoryService
    from backend.services.inventory_foundation_service import FoundationConflict
    case=foundation
    oid=uuid4().hex
    with Session(case.engine) as db:
        service=case.service(db)
        service.create_operation(operation(case,"1"),"stock")
        db.add(Order(id=oid,tenant_id=case.tenant_id,status=OrderStatus.pending,subtotal=50,total=50,fulfillment_type="pickup"))
        db.commit()
        body=reservation(case,"0.7").model_copy(update={"source_type":"order","source_id":oid})
        service.reserve(body,"reserve-order")
        order=db.query(Order).filter_by(id=oid,tenant_id=case.tenant_id).with_for_update().one()
        order.status=OrderStatus.cancelled
        db.flush()
        assert InventoryService(db,case.tenant_id,case.context).reverse_order_sale(oid)["reason"]=="no_sale_movements"
        db.commit()
        assert service.list_reservations()["items"][0]["status"]=="released"
        assert service.balances(case.item_id)["items"][0]["available"]=="1.000000"
        with pytest.raises(FoundationConflict):
            service.reserve(body.model_copy(update={"business_key":"new-hold"}),"new-key")


def test_pg_legacy_http_keeps_numeric_dto_and_audits_authenticated_actor(foundation):
    import json
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.routes import inventory as routes
    from backend.database import get_db
    from backend.models.inventory import InventoryStockMovement
    case=foundation
    actor=SimpleNamespace(tenant_id=case.tenant_id,user_id=case.actor_id,tenant_context=case.context)
    app=FastAPI()
    app.include_router(routes.router,prefix="/api")
    def db_session():
        with Session(case.engine) as db:
            yield db
    app.dependency_overrides[get_db]=db_session
    app.dependency_overrides[routes.panel_operation_context]=lambda:case.context
    for route in app.routes:
        for dependency in getattr(getattr(route,"dependant",None),"dependencies",[]):
            if dependency.name=="_actor":
                app.dependency_overrides[dependency.call]=lambda:actor
    with TestClient(app) as client:
        url="/api/gestao/inventory/manual-entries"
        created=client.post(url,json={"item_id":case.item_id,"location_id":case.location_id,"quantity":0.4,"unit_cost":37})
        assert created.status_code==201,created.text
        assert created.json()["quantity"]==0.4
        assert created.json()["unit_cost"]==37
        with Session(case.engine) as db:
            movement=db.query(InventoryStockMovement).filter_by(tenant_id=case.tenant_id).one()
            assert json.loads(movement.notes)["actor_id"]==case.actor_id
        assert client.delete(url+"/"+created.json()["id"]).status_code==204
        assert client.delete(url+"/"+created.json()["id"]).status_code==204
        rows=client.get(url).json()
        assert len(rows)==1 and rows[0]["reversed"] is True

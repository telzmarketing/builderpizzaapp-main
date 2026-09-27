from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.tenant_context import TenantContext, TenantSource
from backend.main import app
from backend.database import Base
from backend.models.label import (
    LabelPrinter, LabelPrinterTemplate, LabelPrintJob, LabelSetting, LabelTemplate,
    LabelVersion, LabelVolume, LabelVolumeRule,
)
from backend.models.order import Order, OrderItem, OrderItemFlavor, OrderStatus
from backend.models.platform_saas import TenantProfile
from backend.models.product import Product
from backend.models.tenant import Tenant
from backend.schemas.label import LabelPrintIn, LabelPrinterIn, LabelReprintIn, LabelTemplateIn
from backend.services.label_service import LabelService


ROOT = Path(__file__).resolve().parents[1]


def test_label_routes_are_registered_on_dispatch_surface():
    paths = {route.path for route in app.routes}
    expected = {
        "/api/kds/dispatch/label-printers",
        "/api/kds/dispatch/label-templates",
        "/api/kds/dispatch/label-settings",
        "/api/kds/dispatch/label-volume-rules",
        "/api/kds/dispatch/orders/{order_id}/labels/preview",
        "/api/kds/dispatch/orders/{order_id}/labels/print",
        "/api/kds/dispatch/orders/{order_id}/labels/reprint",
        "/api/kds/dispatch/orders/{order_id}/labels/history",
        "/api/kds/dispatch/labels/test",
        "/api/kds/dispatch/label-jobs/{job_id}/dialog-opened",
    }
    assert expected <= paths


def test_browser_first_contract_is_bounded_and_has_no_credentials():
    printer = LabelPrinterIn(name="Expedicao")
    assert printer.connection_type == "browser"
    assert printer.model_dump().keys().isdisjoint({"password", "token", "secret", "username"})
    with pytest.raises(ValidationError):
        LabelPrinterIn(name="x", connection_type="usb")
    with pytest.raises(ValidationError):
        LabelPrintIn(idempotency_key="short")


def test_template_has_individual_calibration_fields_and_bounds():
    template = LabelTemplateIn(name="100x50")
    assert (template.width_mm, template.height_mm, template.dpi) == (100, 50, 203)
    assert template.default_copies == 1
    assert "margin_mm" not in template.model_fields
    with pytest.raises(ValidationError):
        LabelTemplateIn(name="bad", scale_percent=300)
    checks = {constraint.name for constraint in LabelTemplate.__table__.constraints}
    assert {"ck_label_templates_margins", "ck_label_templates_dpi", "ck_label_templates_scales"} <= checks


def test_reprint_reason_is_optionally_shaped_but_validated_when_present():
    payload = LabelReprintIn(idempotency_key="reprint-123")
    assert payload.reason is None
    with pytest.raises(ValidationError):
        LabelReprintIn(idempotency_key="reprint-123", reason=" x ")


def test_volume_snapshot_is_deterministic_and_product_rule_wins_over_category():
    db = MagicMock()
    product_rule = SimpleNamespace(scope_type="product", scope_value="pizza-1", volumes_per_unit=2)
    category_rule = SimpleNamespace(scope_type="category", scope_value="Pizzas", volumes_per_unit=3)
    db.query.return_value.filter.return_value.all.return_value = [category_rule, product_rule]
    service = LabelService(db, TenantContext(tenant_id="tenant-a", source=TenantSource.JOB))
    pizza = SimpleNamespace(id="pizza-1", name="Meia a meia", description="Pizza grande", category="Pizzas", product_type="pizza")
    drink = SimpleNamespace(id="drink-1", name="Cola", description="Lata", category="Bebidas", product_type="drink")
    flavor = SimpleNamespace(flavor_name="Calabresa", position=0)
    items = [
        SimpleNamespace(id="item-b", position=1, product_id="drink-1", quantity=1, selected_size="Lata",
                        selected_crust_type=None, selected_drink_variant="Zero", notes=None, add_ons=[], flavors=[]),
        SimpleNamespace(id="item-a", position=0, product_id="pizza-1", quantity=2, selected_size="Grande",
                        selected_crust_type="Catupiry", selected_drink_variant=None, notes="Sem cebola",
                        add_ons=["Bacon"], flavors=[flavor]),
    ]
    order = SimpleNamespace(id="order-1", order_code="101", delivery_name="Maria", notes="Portaria", items=items)
    snapshot, volumes = service._snapshot(order, {"pizza-1": pizza, "drink-1": drink}, include_drinks=False,
                                          identity={"name": "Loja A", "logo_url": "/logo.png"})
    assert len(volumes) == 4
    assert [volume["sequence"] for volume in volumes] == [1, 2, 3, 4]
    assert all(volume["order_item_id"] == "item-a" for volume in volumes)
    assert snapshot["items"][0]["product_description"] == "Pizza grande"
    assert snapshot["items"][0]["add_ons"] == ["Bacon"]
    assert snapshot["customer_name"] == "Maria"
    assert snapshot["restaurant"]["logo_url"] == "/logo.png"


def test_models_preserve_item_snapshot_and_never_claim_physical_success():
    assert {"position", "add_ons"} <= set(OrderItem.__table__.c.keys())
    result_check = next(c for c in LabelPrintJob.__table__.constraints if c.name == "ck_label_print_jobs_result")
    assert "physical" not in str(result_check.sqltext)
    assert "requested" in str(result_check.sqltext)
    assert "dialog_opened" in str(result_check.sqltext)


def test_migration_is_linear_and_backfills_order_item_snapshots():
    source = (ROOT / "backend/migrations/versions/20260926_dispatch_labels.py").read_text(encoding="utf-8")
    assert 'down_revision = "20260924_kds_kitchen_dispatch"' in source
    assert "row_number() OVER (PARTITION BY order_id ORDER BY id)" in source
    assert "'[]'::json" in source
    assert "connection_type" in source and "browser" in source
    assert "label_print_jobs" in source


def test_preview_versions_idempotency_reprint_test_print_and_tenant_isolation():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    tables = [
        Tenant.__table__, TenantProfile.__table__, Product.__table__, Order.__table__,
        OrderItem.__table__, OrderItemFlavor.__table__, LabelPrinter.__table__,
        LabelTemplate.__table__, LabelPrinterTemplate.__table__, LabelSetting.__table__,
        LabelVolumeRule.__table__, LabelVersion.__table__, LabelVolume.__table__, LabelPrintJob.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    session = sessionmaker(bind=engine)()
    session.add_all([
        Tenant(id="tenant-a", slug="a", name="Loja A"),
        # SQLite ignores the PostgreSQL-only partial predicate on the legacy
        # tenant unique index, so keep the two fixture values distinct.
        Tenant(id="tenant-b", slug="b", name="Loja B", is_legacy=True),
        TenantProfile(tenant_id="tenant-a", trade_name="Pizzaria A", logo_url="/a.png"),
        Product(id="pizza-1", tenant_id="tenant-a", name="Pizza", description="Pizza grande",
                price=50, category="Pizzas", product_type="pizza"),
        Order(id="order-1", tenant_id="tenant-a", status=OrderStatus.ready_for_pickup,
              order_code="101", fulfillment_type="delivery", sales_channel="delivery",
              delivery_name="Maria", subtotal=50, total=50),
        OrderItem(id="item-1", tenant_id="tenant-a", order_id="order-1", product_id="pizza-1",
                  position=0, quantity=1, selected_size="Grande", add_ons=["Bacon"],
                  unit_price=50, total_price=50),
    ])
    session.commit()
    service = LabelService(session, TenantContext(tenant_id="tenant-a", source=TenantSource.JOB))

    first = service.preview("order-1")
    again = service.preview("order-1")
    assert first["version"]["id"] == again["version"]["id"]
    assert first["volume_count"] == 1 and first["is_first_print"] is True
    assert first["restaurant"] == {"name": "Pizzaria A", "logo_url": "/a.png"}

    item = session.query(OrderItem).filter(OrderItem.id == "item-1").one()
    item.notes = "Sem cebola"
    session.commit()
    changed = service.preview("order-1")
    assert changed["version"]["number"] == 2
    old = session.query(LabelVersion).filter(LabelVersion.id == first["version"]["id"]).one()
    assert old.invalidated_at is not None

    request = LabelPrintIn(idempotency_key="print-order-1")
    printed = service.request_print("order-1", request, actor_id="admin-1", reprint=False)
    duplicate = service.request_print("order-1", request, actor_id="admin-1", reprint=False)
    assert printed["job"]["id"] == duplicate["job"]["id"]
    assert printed["job"]["result_status"] == "requested"
    with pytest.raises(Exception) as missing_reason:
        service.request_print("order-1", LabelReprintIn(idempotency_key="reprint-order-1"),
                              actor_id="admin-1", reprint=True)
    assert "motivo" in str(missing_reason.value).lower()
    reprinted = service.request_print(
        "order-1", LabelReprintIn(idempotency_key="reprint-order-2", reason="Etiqueta danificada"),
        actor_id="admin-1", reprint=True,
    )
    assert reprinted["job"]["job_type"] == "reprint"

    test_result = service.request_test(
        LabelPrintIn(idempotency_key="label-test-1"), actor_id="admin-1",
    )
    assert test_result["preview"]["content"]["large_number"] == "123"
    assert test_result["preview"]["print_area"]["margins_mm"] == {"top": 2, "right": 2, "bottom": 2, "left": 2}

    other = LabelService(session, TenantContext(tenant_id="tenant-b", source=TenantSource.JOB))
    with pytest.raises(Exception) as tenant_error:
        other.preview("order-1")
    assert "order-1" in str(tenant_error.value)
    session.close()

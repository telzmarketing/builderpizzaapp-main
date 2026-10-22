from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.schemas.inventory_foundation import ConversionPreviewIn, MovementLine, PackagingIn, LotIn, OperationIn, ReservationIn
from backend.services.inventory_foundation_service import (
    FoundationInvalid, InventoryFoundationService, convert_decimal, normalized_quantity, output,
)


def test_decimal_conversion_preserves_six_places_and_rounds_only_at_boundary():
    assert convert_decimal(Decimal("1"), Decimal("1"), Decimal("1000")) == Decimal("0.001000")
    assert convert_decimal(Decimal("1"), Decimal("1"), Decimal("3")) == Decimal("0.333333")
    assert normalized_quantity(Decimal("0.0000015")) == Decimal("0.000002")
    assert output(Decimal("1480.00000000")) == "1480.00000000"


@pytest.mark.parametrize("quantity", [1.25, 1, "1e3", "NaN", "Infinity", "1,25", "0", "0.1234567"])
def test_inputs_reject_binary_numbers_noncanonical_or_invalid_quantities(quantity):
    with pytest.raises(ValidationError):
        ConversionPreviewIn(item_id="i", quantity=quantity, unit_id="u")


def test_conversion_does_not_silently_zero_or_overflow():
    with pytest.raises(FoundationInvalid):
        convert_decimal(Decimal("0.000001"), Decimal("1"), Decimal("1000000"))
    with pytest.raises(FoundationInvalid):
        normalized_quantity(Decimal("100000000000000"))


def test_variable_packaging_forbids_invented_fixed_factor():
    base = dict(expected_version=0, name="Caixa pesada", item_id="i", commercial_unit_id="box", base_unit_id="kg", variable_weight=True)
    assert PackagingIn(**base).factor is None
    with pytest.raises(ValidationError):
        PackagingIn(**base, factor="12")
    with pytest.raises(ValidationError):
        PackagingIn(**{**base, "variable_weight": False})


def preview_service():
    service = InventoryFoundationService(SimpleNamespace(), "tenant-a", "operator")
    rows = {
        "item": SimpleNamespace(id="item", unit_id="kg", active=True),
        "box": SimpleNamespace(id="box", active=True, dimension="count", conversion_factor=Decimal(1)),
        "kg": SimpleNamespace(id="kg", active=True, dimension="mass", conversion_factor=Decimal(1)),
        "g": SimpleNamespace(id="g", active=True, dimension="mass", conversion_factor=Decimal("0.001")),
        "pack": SimpleNamespace(id="pack", active=True, item_id="item", commercial_unit_id="box", base_unit_id="kg", variable_weight=True, version=1),
    }
    service._get = lambda model, resource_id, **kwargs: rows[resource_id]
    return service, rows


def test_preview_variable_measurement_is_total_not_multiplied_by_package_count():
    service, _ = preview_service()
    result = service.preview(ConversionPreviewIn(item_id="item", quantity="4", unit_id="box", packaging_id="pack", measured_quantity="12500", measured_unit_id="g"))
    assert result["quantity"] == "12.500000"


def test_cross_dimension_preview_requires_confirmed_packaging():
    service, _ = preview_service()
    with pytest.raises(FoundationInvalid, match="dimensoes"):
        service.preview(ConversionPreviewIn(item_id="item", quantity="4", unit_id="box"))


def test_unconfirmed_legacy_unit_cannot_be_guessed_from_symbol():
    service, rows = preview_service()
    rows["kg"].dimension = None
    with pytest.raises(FoundationInvalid, match="confirmados"):
        service.preview(ConversionPreviewIn(item_id="item", quantity="1", unit_id="kg"))


def test_unknown_command_fields_cannot_supply_tenant_or_actor():
    with pytest.raises(ValidationError):
        OperationIn(expected_version=0, kind="manual_in", business_key="entry-1", reason="contagem", tenant_id="other", lines=[dict(item_id="i", quantity="1", unit_id="u", location_id="l")])


def test_tenant_context_mismatch_rejected_before_database_access():
    with pytest.raises(FoundationInvalid):
        InventoryFoundationService(SimpleNamespace(), "tenant-a", "user", SimpleNamespace(tenant_id="tenant-b"))


def test_timezone_required_and_no_expiry_policy_inferred():
    with pytest.raises(ValidationError):
        LotIn(expected_version=0, item_id="i", location_id="l", lot_code="L", received_at="2026-10-21T10:00:00")
    reservation = ReservationIn(expected_version=0, business_key="r", item_id="i", location_id="l", quantity="1", unit_id="u", source_type="manual", source_id="document", reason="reserva explicita")
    assert reservation.expires_at is None
    service = InventoryFoundationService(SimpleNamespace(), "tenant", "user")
    assert not service._eligible(SimpleNamespace(status="available", effective_expires_at=None, expires_on=None))
    assert not service._eligible(SimpleNamespace(status="available", effective_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1), expires_on=None))


def test_no_lot_reservation_does_not_reduce_other_lot_bucket():
    service = InventoryFoundationService(SimpleNamespace(), "tenant", "user")
    service._physical = lambda *args: Decimal("10")
    service._active_reservations = lambda item: [SimpleNamespace(location_id="l", lot_id=None, quantity=Decimal("7"), source_type="manual", source_id="r")]
    assert service._available("i", "l", "tracked-lot") == Decimal("10")
    assert service._available("i", "l", None) == Decimal("3")


def test_line_cost_default_is_decimal_not_float():
    line = MovementLine(item_id="i", quantity="1", unit_id="u", location_id="l")
    assert isinstance(line.unit_cost, Decimal)


def test_stock_composition_uses_decimal_fraction_without_legacy_float_rounding():
    from backend.services.recipe_resolution import resolve_recipes
    from backend.services.inventory_service import required_decimal
    from types import SimpleNamespace as S
    recipes={}
    for pid in ("a","b","c"):
        recipes[pid]=[S(component_role="flavor",reference_fraction=Decimal("0.5"),product_size_id=None,
            product_crust_type_id=None,product_drink_variant_id=None,complement_key=None,
            items=[S(inventory_item_id=pid,quantity=Decimal("0.1"),waste_percent=Decimal(0))])]
    item=S(product_id="a",quantity=123456789013,flavors=[S(product_id=p) for p in recipes])
    required=required_decimal(resolve_recipes(item,recipes))
    assert required=={p:Decimal("8230452600.866667") for p in recipes}


def test_packaging_cannot_bypass_missing_mass_volume_density():
    from types import SimpleNamespace as S
    service,rows=preview_service()
    rows["l"]=S(id="l",active=True,dimension="volume",conversion_factor=Decimal(1))
    rows["pack"].commercial_unit_id="l"
    rows["pack"].variable_weight=False
    rows["pack"].factor=Decimal("0.9")
    with pytest.raises(FoundationInvalid,match="densidade"):
        service.preview(ConversionPreviewIn(item_id="item",quantity="1",unit_id="l",packaging_id="pack"))

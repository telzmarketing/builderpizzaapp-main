from decimal import Decimal
from types import SimpleNamespace

from backend.services.purchase_planning_service import PurchasePlanningService, positive


def test_planning_shortage_never_goes_below_zero():
    assert positive(Decimal("10") - Decimal("4") - Decimal("3")) == Decimal("3.000000")
    assert positive(Decimal("4") - Decimal("10")) == Decimal("0.000000")


def test_direct_planning_states_distinguish_confirmed_transit_and_shortage():
    item = SimpleNamespace(unit_id="unit-kg")
    assert PurchasePlanningService._direct_state(item, Decimal("0"), Decimal("2")) == ("pending", "covered", "Necessidade coberta por compra confirmada em transito.")
    assert PurchasePlanningService._direct_state(item, Decimal("3"), Decimal("0"))[1] == "purchase_required"
    assert PurchasePlanningService._direct_state(SimpleNamespace(unit_id=None), Decimal("3"), Decimal("0"))[0] == "blocked"

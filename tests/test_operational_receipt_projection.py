from types import SimpleNamespace

from backend.services.label_service import LabelService


def _item(item_id, product_id, quantity=1, drink_variant=None):
    return SimpleNamespace(
        id=item_id,
        position=0,
        product_id=product_id,
        quantity=quantity,
        selected_size="",
        selected_drink_variant=drink_variant,
        notes=None,
        flavors=[],
    )


def test_receipt_separates_drinks_and_exposes_real_payment_data():
    order = SimpleNamespace(
        order_code="1258",
        delivery_name="Joao Silva",
        fulfillment_type="delivery",
        items=[_item("pizza-item", "pizza"), _item("drink-item", "drink", 2)],
        payment=SimpleNamespace(
            method="cash",
            status="pending",
            provider="on_delivery",
            pay_on_delivery=True,
            cash_change_for=100,
            delivery_payment_method="cash",
            cash_needs_change=True,
        ),
        subtotal=74.99,
        shipping_fee=0,
        discount=0,
        total=74.99,
    )
    service = LabelService.__new__(LabelService)
    receipt = service._receipt(
        order,
        {"pizza": SimpleNamespace(name="Pizza Calabresa", product_type="pizza"),
         "drink": SimpleNamespace(name="Kuat 2 L", product_type="drink")},
        {"name": "Gran Torino", "logo_url": "/uploads/logo.png"},
    )

    assert receipt["restaurant"]["logo_url"] == "/uploads/logo.png"
    assert receipt["has_drinks"] is True
    assert receipt["drinks"] == [{
        "quantity": 2,
        "name": "Kuat 2 L",
        "selected_size": "",
        "selected_drink_variant": None,
        "flavors": [],
        "notes": None,
    }]
    assert receipt["payment"]["status"] == "pending"
    assert receipt["payment"]["paid_online"] is False
    assert receipt["payment"]["cash_change_amount"] == 25.01

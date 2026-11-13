from backend.models.print_order import PrintOrderCatalogMapping, PrintOrderImport
from types import SimpleNamespace
from pathlib import Path

import pytest

from backend.core.exceptions import DomainError
from backend.services.print_order_service import (
    build_print_order_cart_item,
    detect_platform,
    normalize_print_text,
    parse_print_text,
    print_order_external_reference,
    resolve_safe_catalog_match,
    resolve_flavor_candidates,
)

def test_deterministic_parser_detects_platform_number_and_items_without_claiming_ai():
    parsed = parse_print_text("iFood\nPedido #ABC-123\n2x Pizza Calabresa G\nTotal: R$ 59,90")
    assert parsed["platform"] == "ifood"
    assert parsed["external_order_number"] == "ABC-123"
    assert parsed["items"][0]["quantity"] == 2
    assert parsed["parser"] == "deterministic-v1"

def test_normalization_is_accent_and_punctuation_insensitive():
    assert normalize_print_text("Pizza Calabresa — Grande") == "pizza calabresa grande"
    assert detect_platform("comanda keeta") == "keeta"

def test_parser_preserves_half_and_half_flavors_for_catalog_review():
    parsed = parse_print_text("99Food\nPedido: 99-456\nMeia Calabresa / Meia Mussarela")
    assert parsed["items"][0]["flavor_names"] == ["Calabresa", "Mussarela"]

def test_database_contract_has_tenant_scoped_dedupe_and_catalog_mapping():
    assert PrintOrderImport.__table__.c.tenant_id is not None
    assert any(i.name == "uq_print_order_imports_dedupe_key" and i.unique for i in PrintOrderImport.__table__.indexes)
    assert {"tenant_id", "platform", "normalized_external_name"}.issubset({c.name for c in PrintOrderCatalogMapping.__table__.constraints if hasattr(c, "columns") for c in c.columns})


def _catalog_product(product_id, name, price=40.0):
    return SimpleNamespace(id=product_id, name=name, price=price, icon="", active=True, sizes=[])


def test_print_order_converts_safe_half_and_half_without_flattening_flavors():
    primary = _catalog_product("calabresa", "Pizza Calabresa")
    secondary = _catalog_product("frango", "Pizza Frango")
    item = SimpleNamespace(
        product_id="calabresa", quantity=1, selected_size="Grande", flavor_names=["pizza calabresa", "PIZZA FRANGO"],
        customizations={"notes": "sem cebola"}, unit_price=None,
    )

    cart = build_print_order_cart_item(item, [primary, secondary], selected_size_id="size-grande")

    assert cart.flavor_division == 2
    assert [flavor.product_id for flavor in cart.flavors] == ["calabresa", "frango"]
    assert cart.selected_size == "Grande"
    assert cart.selected_size_id == "size-grande"
    assert cart.notes == "sem cebola"


def test_print_order_blocks_unresolved_flavor_and_uncontracted_customization():
    primary = _catalog_product("calabresa", "Pizza Calabresa")
    item = SimpleNamespace(
        product_id="calabresa", quantity=1, selected_size="Grande", flavor_names=["Pizza Calabresa", "Sabor inexistente"],
        customizations={}, unit_price=None,
    )
    with pytest.raises(DomainError) as error:
        build_print_order_cart_item(item, [primary])
    assert error.value.code == "PrintOrderFlavorNotResolved"

    item.flavor_names = []
    item.customizations = {"border_name": "Catupiry"}
    with pytest.raises(DomainError) as error:
        build_print_order_cart_item(item, [primary])
    assert error.value.code == "PrintOrderCompositionReviewRequired"


def test_print_order_confirmation_reference_is_stable_for_concurrent_replays():
    assert print_order_external_reference("tenant-a", "iFood", " AB-123 ") == "print-pedido:tenant-a:ifood:ab 123"

def test_confirmation_preserves_operational_boundaries():
    source = Path("backend/services/print_order_service.py").read_text(encoding="utf-8")
    assert 'payment_status="pending"' in source
    assert 'payment_source="manual"' in source
    assert "OrderCmvSnapshotService" in Path("backend/services/order_service.py").read_text(encoding="utf-8")
    assert "KdsProductionService(self.db, self.tenant_context).initialize_order" in Path("backend/services/kds_service.py").read_text(encoding="utf-8")
    assert 'if status != "preparing"' in Path("backend/services/inventory_service.py").read_text(encoding="utf-8")


def test_catalog_auto_match_accepts_only_unique_exact_name_or_approved_alias():
    products = [_catalog_product("p1", "Pizza Calabresa"), _catalog_product("p2", "Pizza Mussarela")]
    assert resolve_safe_catalog_match("pizza calabresa", products) == ("p1", "matched", "exact_catalog_name")
    assert resolve_safe_catalog_match("pizza inexistente", products) == (None, "unmatched", None)
    assert resolve_safe_catalog_match("nome externo", products, "p2") == ("p2", "matched", "approved_mapping")


def test_catalog_auto_match_keeps_ambiguous_name_in_review():
    products = [_catalog_product("p1", "Pizza Calabresa"), _catalog_product("p2", "Pizza Calabresa")]
    assert resolve_safe_catalog_match("pizza calabresa", products) == (None, "review", "ambiguous_exact_catalog_name")


def test_flavor_candidates_resolve_half_prefixes_and_keep_ambiguity_for_review():
    products = [_catalog_product("calabresa", "Calabresa"), _catalog_product("mussarela", "Mussarela"), _catalog_product("duplicate", "Mussarela")]
    assert resolve_flavor_candidates(["1/2 Calabresa", "1/2 Mussarela"], products) == {"1/2 Calabresa": ["calabresa"], "1/2 Mussarela": ["mussarela", "duplicate"]}
    assert resolve_flavor_candidates(["Calabresa", "Mussarela"], products) == {"Calabresa": ["calabresa"], "Mussarela": ["mussarela", "duplicate"]}


def test_parser_splits_comma_separated_flavors():
    parsed = parse_print_text("iFood\nPedido #ABC-123\nPizza: Calabresa, Mussarela")
    assert parsed["items"][0]["flavor_names"] == ["Calabresa", "Mussarela"]


KEETA_REAL_OCR_TEXT = """Keeta
Entrega Keeta
#9399
Retirada as
17:33
Edder Cezar Galvao de Souza
Novos clientes
Pago
1 item
Obs. do pedido
Verifique a quantidade de detalhes selecionada pelo cliente.
Qtd Itens Preco(R$)
1x Compre 1 Pizza e Ganhe 1 Guarana
2L
1x 1/2 Calabresa -
1x 1/2 Mussarela
Total do item 71,99
Taxa de entrega 13,99
Taxa de servico 0,99
Promocao financiada pela loja -24,99
Promocao financiada pela Keeta -23,19
Valor pago pelo cliente R$ 38,79
"""


def test_keeta_real_ocr_extracts_identity_items_pickup_and_reconciliation():
    parsed = parse_print_text(KEETA_REAL_OCR_TEXT, "keeta")

    assert parsed["platform"] == "keeta"
    assert parsed["external_order_number"] == "9399"
    assert parsed["customer_name"] == "Edder Cezar Galvao de Souza"
    assert parsed["payment_method"] == "Pago"
    assert parsed["fulfillment_type"] == "pickup"
    assert [item["external_name"] for item in parsed["items"]] == [
        "Compre 1 Pizza e Ganhe 1 Guarana 2L", "1/2 Calabresa", "1/2 Mussarela"
    ]
    assert parsed["financials"] == {
        "subtotal": 71.99, "delivery_fee": 13.99, "service_fee": 0.99,
        "store_discount": 24.99, "platform_discount": 23.19, "total_paid": 38.79,
    }
    assert parsed["reconciliation"] == {"status": "matched", "expected_total": 38.79, "printed_total": 38.79, "delta": 0.0}


def test_keeta_financial_divergence_blocks_ready_state():
    parsed = parse_print_text(KEETA_REAL_OCR_TEXT.replace("38,79", "39,79"), "keeta")
    assert parsed["reconciliation"]["status"] == "divergent"
    assert any("Divergência financeira" in note for note in parsed["review_notes"])

"""Recipe line normalization shared by legacy and versioned publication."""
from decimal import Decimal, localcontext, ROUND_HALF_UP

from backend.models.inventory import InventoryItem, InventoryUnit
from backend.services.inventory_foundation_service import InventoryFoundationService, FoundationInvalid, normalized_quantity


def normalize_recipe_line(db, tenant_id, values):
    data = dict(values)
    item = db.query(InventoryItem).filter(InventoryItem.id == data["inventory_item_id"], InventoryItem.tenant_id == tenant_id).first()
    if item is None or not item.active:
        raise FoundationInvalid("Insumo nao encontrado ou inativo neste tenant.")
    if data.get("unit_id") and data["unit_id"] != item.unit_id:
        raise FoundationInvalid("Unidade base informada difere da unidade oficial do insumo.")
    entered_unit, entered_quantity = data.get("entered_unit_id"), data.get("entered_quantity")
    if (entered_unit is None) != (entered_quantity is None):
        raise FoundationInvalid("Conversao exige quantidade e unidade digitadas juntas.")
    if entered_unit is not None:
        foundation = InventoryFoundationService(db, tenant_id, "system:recipe-normalization")
        source, target = foundation._unit(entered_unit), foundation._unit(item.unit_id)
        if source.dimension != target.dimension:
            raise FoundationInvalid("Unidades da ficha possuem dimensoes incompativeis.")
        with localcontext() as context:
            context.prec = 50
            factor = (Decimal(source.conversion_factor) / Decimal(target.conversion_factor)).quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_UP)
            quantity = normalized_quantity(Decimal(entered_quantity) * factor)
        if factor <= 0:
            raise FoundationInvalid("Conversao inferior a precisao suportada.")
        if data.get("quantity") is not None and Decimal(str(data["quantity"])) != quantity:
            raise FoundationInvalid("Quantidade base diverge da conversao confirmada.")
        data.update(quantity=quantity, unit_id=item.unit_id, entered_unit_id=source.id,
                    entered_quantity=Decimal(entered_quantity), conversion_factor_snapshot=factor)
    else:
        if data.get("quantity") is None:
            raise FoundationInvalid("Quantidade base obrigatoria.")
        data["quantity"] = normalized_quantity(Decimal(str(data["quantity"])))
        data["conversion_factor_snapshot"] = None
    if data.get("show_public") and not (data.get("public_name") or "").strip():
        raise FoundationInvalid("Divulgacao publica exige nome autorizado.")
    return data

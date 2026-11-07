"""Resolve the physical stock source of a technical-recipe line.

The recipe line keeps ``inventory_item_id`` as the canonical item consumed by
all existing availability, production and CMV consumers. Portion metadata is
an immutable explanation of how that item was selected at publication time.
"""

from decimal import Decimal, ROUND_HALF_UP, localcontext

from backend.models.inventory import InventoryItem, InventoryUnit
from backend.models.inventory_portion import InventoryPortionConfig
from backend.services.inventory_foundation_service import (
    FoundationConflict,
    FoundationInvalid,
    InventoryFoundationService,
    normalized_quantity,
)


class RecipeSupplyResolver:
    def __init__(self, db, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def resolve_line(self, values: dict) -> dict:
        data = dict(values)
        mode = data.get("supply_mode") or ("portion" if data.get("portion_config_id") else "direct")
        if mode not in {"direct", "portion"}:
            raise FoundationInvalid("Modo de abastecimento da ficha invalido.")

        if mode == "portion":
            config_id = data.get("portion_config_id")
            if not config_id:
                raise FoundationInvalid("Configuracao de porcao e obrigatoria para este abastecimento.")
            config = (
                self.db.query(InventoryPortionConfig)
                .filter(
                    InventoryPortionConfig.id == config_id,
                    InventoryPortionConfig.tenant_id == self.tenant_id,
                )
                .with_for_update()
                .first()
            )
            if config is None or not config.active:
                raise FoundationInvalid("Configuracao de porcao nao encontrada ou inativa neste tenant.")
            requested_version = data.get("portion_config_version")
            if requested_version is not None and int(requested_version) != int(config.version):
                raise FoundationConflict("Configuracao de porcao foi alterada; recarregue a ficha.", code="PortionConfigVersionConflict")
            item = (
                self.db.query(InventoryItem)
                .filter(
                    InventoryItem.id == config.output_item_id,
                    InventoryItem.tenant_id == self.tenant_id,
                )
                .first()
            )
            if item is None or not item.active:
                raise FoundationInvalid("Produto porcionado da configuracao nao esta disponivel neste tenant.")
            data.update(
                inventory_item_id=item.id,
                supply_mode="portion",
                portion_config_id=config.id,
                portion_config_version=int(config.version),
            )
        else:
            if data.get("portion_config_id") or data.get("portion_config_version"):
                raise FoundationInvalid("Abastecimento direto nao aceita configuracao de porcao.")
            item_id = data.get("inventory_item_id")
            if not item_id:
                raise FoundationInvalid("Item de estoque e obrigatorio para abastecimento direto.")
            item = (
                self.db.query(InventoryItem)
                .filter(InventoryItem.id == item_id, InventoryItem.tenant_id == self.tenant_id)
                .first()
            )
            if item is None or not item.active:
                raise FoundationInvalid("Insumo nao encontrado ou inativo neste tenant.")
            generated_portion = (
                self.db.query(InventoryPortionConfig.id)
                .filter(
                    InventoryPortionConfig.tenant_id == self.tenant_id,
                    InventoryPortionConfig.output_item_id == item.id,
                )
                .first()
            )
            if generated_portion is not None:
                raise FoundationInvalid("Produto porcionado deve ser selecionado pela configuracao de porcao.")
            data.update(supply_mode="direct", portion_config_id=None, portion_config_version=None)

        if data.get("unit_id") and data["unit_id"] != item.unit_id:
            raise FoundationInvalid("Unidade base informada difere da unidade oficial do insumo.")
        data["unit_id"] = item.unit_id
        entered_unit, entered_quantity = data.get("entered_unit_id"), data.get("entered_quantity")
        if (entered_unit is None) != (entered_quantity is None):
            raise FoundationInvalid("Conversao exige quantidade e unidade digitadas juntas.")
        if entered_unit is not None:
            foundation = InventoryFoundationService(self.db, self.tenant_id, "system:recipe-normalization")
            source = foundation._unit(entered_unit)
            target = foundation._unit(item.unit_id)
            if source.dimension != target.dimension:
                raise FoundationInvalid("Unidades da ficha possuem dimensoes incompativeis.")
            with localcontext() as context:
                context.prec = 50
                factor = (
                    Decimal(source.conversion_factor) / Decimal(target.conversion_factor)
                ).quantize(Decimal("0.000000000001"), rounding=ROUND_HALF_UP)
                quantity = normalized_quantity(Decimal(entered_quantity) * factor)
            if factor <= 0:
                raise FoundationInvalid("Conversao inferior a precisao suportada.")
            if data.get("quantity") is not None and Decimal(str(data["quantity"])) != quantity:
                raise FoundationInvalid("Quantidade base diverge da conversao confirmada.")
            data.update(
                quantity=quantity,
                entered_unit_id=source.id,
                entered_quantity=Decimal(entered_quantity),
                conversion_factor_snapshot=factor,
            )
        else:
            if data.get("quantity") is None:
                raise FoundationInvalid("Quantidade base obrigatoria.")
            data["quantity"] = normalized_quantity(Decimal(str(data["quantity"])))
            data["conversion_factor_snapshot"] = None
        if data.get("show_public") and not (data.get("public_name") or "").strip():
            raise FoundationInvalid("Divulgacao publica exige nome autorizado.")
        return data


def resolve_recipe_line(db, tenant_id: str, values: dict) -> dict:
    return RecipeSupplyResolver(db, tenant_id).resolve_line(values)

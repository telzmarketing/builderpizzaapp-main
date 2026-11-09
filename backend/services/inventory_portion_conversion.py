"""Convert one configured portion into the purchased item's stock unit.

Unit dimensions/factors are explicit tenant data. A symbol such as KG is never
enough to infer a conversion for an unclassified legacy unit.
"""
from decimal import Decimal, InvalidOperation, localcontext

from backend.services.inventory_foundation_service import FoundationInvalid, convert_decimal, normalized_quantity


class PortionConversionError(ValueError):
    pass


def source_quantity_for_portion(source, source_unit, portion_unit, portion_weight, yield_percent=100, weight_unit=None):
    if source is None:
        raise PortionConversionError("Insumo de origem nao encontrado.")
    if source_unit is None:
        raise PortionConversionError(f"Cadastre a unidade de compra/estoque do insumo {source.name}.")
    if portion_unit is None:
        raise PortionConversionError("Cadastre a unidade de peso da porcao na ficha de porcionamento.")
    if not getattr(source_unit, "active", True) or not getattr(portion_unit, "active", True):
        raise PortionConversionError("A unidade do insumo ou da porcao esta inativa.")
    if getattr(portion_unit, "dimension", None) != "mass" or not getattr(portion_unit, "conversion_factor", None):
        raise PortionConversionError(
            f"Classifique a unidade da porcao {portion_unit.name} como massa e informe seu fator de conversao."
        )
    try:
        weight = Decimal(str(portion_weight))
        yield_ratio = Decimal(str(yield_percent)) / Decimal("100")
        if not weight.is_finite() or weight <= 0 or not yield_ratio.is_finite() or yield_ratio <= 0 or yield_ratio > 1:
            raise PortionConversionError("Peso da porcao ou rendimento invalido.")
        with localcontext() as context:
            context.prec = 50
            required_weight = weight / yield_ratio
            if source_unit.dimension == "mass" and source_unit.conversion_factor:
                quantity = convert_decimal(required_weight, portion_unit.conversion_factor, source_unit.conversion_factor)
                if quantity <= 0:
                    raise PortionConversionError("Peso da porcao inferior a precisao do estoque.")
                return quantity
            if source_unit.dimension == "volume":
                raise PortionConversionError("Nao e possivel converter volume em gramas sem densidade cadastrada.")
            if source_unit.dimension is None or not source_unit.conversion_factor:
                raise PortionConversionError(
                    f"Classifique a unidade de compra {source_unit.name} em Base do Estoque; "
                    "use massa para KG/GR ou contagem para embalagem/porcao."
                )
            package_weight = getattr(source, "weight_quantity", None)
            if package_weight is not None and getattr(source, "weight_unit_id", None):
                if weight_unit is None or weight_unit.id != source.weight_unit_id or weight_unit.dimension != "mass" or not weight_unit.conversion_factor or not getattr(weight_unit, "active", True):
                    raise PortionConversionError("Classifique a unidade do peso da embalagem como massa com fator de conversao.")
                package_weight = Decimal(str(package_weight))
                if not package_weight.is_finite() or package_weight <= 0:
                    raise PortionConversionError("Peso total da embalagem invalido no cadastro do insumo.")
                required_in_weight_unit = required_weight * Decimal(str(portion_unit.conversion_factor)) / Decimal(str(weight_unit.conversion_factor))
                quantity = normalized_quantity(required_in_weight_unit / package_weight)
                if quantity <= 0:
                    raise PortionConversionError("Peso da porcao inferior a precisao da unidade de compra.")
                return quantity
            raise PortionConversionError(
                f"O insumo {source.name} e comprado por {source_unit.name}. "
                "Cadastre o peso total por embalagem para usar uma ficha em gramas."
            )
    except (FoundationInvalid, InvalidOperation, OverflowError, ZeroDivisionError) as exc:
        raise PortionConversionError("Peso ou fator de conversao invalido.") from exc

"""One recipe calculation shared by availability, frozen CMV and stock."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, localcontext
import re

from backend.core.exceptions import DomainError


class RecipeCompositionError(DomainError):
    http_status = 422


def _component_key(value):
    return re.sub(r"\s+", "-", str(value).strip().casefold())


@dataclass(frozen=True)
class RecipeUse:
    recipe: object
    multiplier: float
    decimal_multiplier: Decimal | None = None


@dataclass(frozen=True)
class RecipeResolution:
    uses: list[RecipeUse]
    missing: tuple[str, ...]
    customizations: tuple = ()
    selected_option_ids: tuple = ()


def _preferred_uses(uses):
    """A specific complete component replaces its generic fallback.

    Distinct selected crusts and addons remain independent components. Recipe
    publication deactivates identical scopes; deterministic version/id tie-break
    also protects imported legacy scopes from being counted twice.
    """
    groups = {}
    for use in uses:
        recipe = use.recipe
        role = getattr(recipe, "component_role", None) or "flavor"
        component = (getattr(recipe, "product_crust_type_id", None), getattr(recipe, "complement_key", None), getattr(recipe, "product_drink_variant_id", None)) if role in {"crust", "addon"} else ()
        # Lightweight legacy fixtures may omit product_id/id. Preserve each
        # distinct recipe in that case; collapsing all of them would drop
        # secondary flavor slots from Decimal stock arithmetic.
        recipe_identity = getattr(recipe, "id", None)
        product_identity = getattr(recipe, "product_id", None)
        if recipe_identity is None and product_identity is None:
            recipe_identity = id(recipe)
        key = (product_identity, role, component, recipe_identity if product_identity is None else None)
        specificity = sum(bool(getattr(recipe, attr, None)) for attr in ("product_size_id", "product_crust_type_id", "product_drink_variant_id", "complement_key"))
        rank = (specificity, getattr(recipe, "version_number", 0) or 0, getattr(recipe, "id", "") or "")
        if key not in groups or rank > groups[key][0]:
            groups[key] = rank, use
    return [pair[1] for pair in groups.values()]


def resolve_recipes(item, recipes: dict[str, list]) -> RecipeResolution:
    quantity = float(item.quantity or 0)
    flavors = list(getattr(item, "flavors", None) or [])
    slots = Counter(flavor.product_id for flavor in flavors) or Counter({item.product_id: 1})
    division = sum(slots.values())
    weights = {}
    explicit = [getattr(flavor, "fraction", None) for flavor in flavors]
    if any(value is not None for value in explicit):
        if any(value is None for value in explicit) or sum((Decimal(str(value)) for value in explicit), Decimal(0)) != 1:
            raise RecipeCompositionError("Fracoes explicitas devem somar uma unidade.")
        for flavor in flavors:
            value = Decimal(str(flavor.fraction))
            if value <= 0:
                raise RecipeCompositionError("Fracao deve ser positiva.")
            weights[flavor.product_id] = weights.get(flavor.product_id, Decimal(0)) + value
    size = getattr(item, "selected_size_id", None)
    crusts = {value for value in (getattr(item, "selected_crust_type_id", None), getattr(item, "selected_border_id", None)) if value}
    drink = getattr(item, "selected_drink_variant_id", None)
    addons = {_component_key(value) for value in (getattr(item, "add_ons", None) or [])}
    uses = []
    missing = []
    for product_id, count in slots.items():
        matched_flavor = False
        for recipe in recipes.get(product_id, []):
            role = getattr(recipe, "component_role", None) or "flavor"
            is_primary = product_id == item.product_id
            if role != "flavor" and not is_primary:
                continue
            if recipe.product_size_id:
                same_size = recipe.product_size_id == size if is_primary else bool(
                    getattr(recipe, "product_size", None)
                    and str(recipe.product_size.label).strip().casefold() == str(getattr(item, "selected_size", "")).strip().casefold()
                )
                if not same_size:
                    continue
            if recipe.product_crust_type_id and (not is_primary or recipe.product_crust_type_id not in crusts):
                continue
            if recipe.product_drink_variant_id and (not is_primary or recipe.product_drink_variant_id != drink):
                continue
            if recipe.complement_key and _component_key(recipe.complement_key) not in addons:
                continue
            if not recipe.items:
                continue
            occupied = float(weights.get(product_id, Decimal(count) / Decimal(division))) if role == "flavor" else 1.0
            reference = float(getattr(recipe, "reference_fraction", None) or 1.0)
            # Legacy CMV consumers retain their float adapter. Physical stock
            # receives an independent exact Decimal ratio, never that adapter.
            with localcontext() as context:
                context.prec = 50
                decimal_occupied = weights.get(product_id, Decimal(count) / Decimal(division)) if role == "flavor" else Decimal(1)
                decimal_reference = Decimal(str(getattr(recipe, "reference_fraction", None) or 1))
                decimal_multiplier = Decimal(str(item.quantity or 0)) * decimal_occupied / decimal_reference
            uses.append(RecipeUse(recipe, quantity * occupied / reference, decimal_multiplier))
            matched_flavor = matched_flavor or role == "flavor" or (is_primary and not flavors)
        if not matched_flavor:
            missing.append(f"product:{product_id}")
    # Non-flavor components belong to the primary commercial product even
    # when a custom flavor selection does not contain that product.
    if item.product_id not in slots:
        primary = resolve_recipes(_PrimaryComponents(item), {item.product_id: [r for r in recipes.get(item.product_id, []) if (getattr(r, "component_role", None) or "flavor") != "flavor"]})
        uses.extend(primary.uses)
    uses = _preferred_uses(uses)
    primary_rows = recipes.get(item.product_id, [])
    used_recipes = [use.recipe for use in uses]
    for attr, selected in (("product_size_id", size), ("product_drink_variant_id", drink)):
        if selected and any(getattr(r, attr) for r in primary_rows) and not any(getattr(r, attr) == selected for r in used_recipes):
            missing.append(f"{attr}:{selected}")
    if any(r.product_crust_type_id for r in primary_rows):
        missing.extend(f"crust:{selected}" for selected in crusts if not any(r.product_crust_type_id == selected for r in used_recipes))
    if any(r.complement_key for r in primary_rows):
        missing.extend(f"addon:{selected}" for selected in addons if not any(r.complement_key and _component_key(r.complement_key) == selected for r in used_recipes))
    customizations = tuple(getattr(item, "customizations", None) or [])
    selected_options = tuple(crusts | ({drink} if drink else set()))
    resolution = RecipeResolution(uses, tuple(missing), customizations, selected_options)
    # Validate even when callers only inspect missing/uses for availability.
    list(resolved_ingredients(resolution))
    return resolution


class _PrimaryComponents:
    def __init__(self, item):
        self.__dict__.update({name: getattr(item, name, None) for name in ("quantity", "product_id", "selected_size_id", "selected_crust_type_id", "selected_border_id", "selected_drink_variant_id", "add_ons")})
        self.flavors = []


def required_ingredients(resolution: RecipeResolution) -> dict[str, float]:
    return {key: float(value) for key, value in required_decimal_ingredients(resolution).items()}


def _data(value):
    return value.model_dump() if hasattr(value, "model_dump") else value


def resolved_ingredients(resolution: RecipeResolution, *, removed=False):
    """Yield (use, ingredient, exact base quantity) for every domain consumer.

    Substitutions remove the named original and reference an already selected
    configured addon recipe. Its ingredients already occur once in uses; this
    function never invents a new unpriced ingredient or duplicates that addon.
    """
    excluded = set()
    for raw in resolution.customizations:
        change = _data(raw)
        matches = []
        for index, use in enumerate(resolution.uses):
            if change.get("scope_product_id") and use.recipe.product_id != change["scope_product_id"]:
                continue
            if change.get("scope_component_role") and getattr(use.recipe, "component_role", "flavor") != change["scope_component_role"]:
                continue
            for line_index, line in enumerate(use.recipe.items):
                if line.inventory_item_id == change.get("inventory_item_id"):
                    if not getattr(line, "allow_removal", False):
                        raise RecipeCompositionError("Retirada ou substituicao nao autorizada pela ficha.", code="IngredientRemovalNotAllowed")
                    matches.append((index, line_index))
        if not matches:
            raise RecipeCompositionError("Personalizacao referencia ingrediente ausente no escopo selecionado.")
        if excluded.intersection(matches):
            raise RecipeCompositionError("Personalizacao duplicada para o mesmo ingrediente/escopo.")
        if change.get("action") == "substitute":
            replacement = change.get("replacement_recipe_id")
            replacement_use = next((use for use in resolution.uses if use.recipe.id == replacement and getattr(use.recipe, "component_role", "flavor") == "addon"), None)
            if replacement_use is None:
                raise RecipeCompositionError("Substituicao exige receita adicional oficialmente selecionada.")
            option_ids = (getattr(replacement_use.recipe, "product_crust_type_id", None), getattr(replacement_use.recipe, "product_drink_variant_id", None))
            if not any(option and option in resolution.selected_option_ids for option in option_ids):
                raise RecipeCompositionError("Substituicao exige adicional vinculado a opcao comercial precificada.", code="UnpricedReplacement")
        elif change.get("action") != "remove":
            raise RecipeCompositionError("Acao de personalizacao invalida.")
        excluded.update(matches)
    with localcontext() as context:
        context.prec = 50
        for index, use in enumerate(resolution.uses):
            multiplier = use.decimal_multiplier if use.decimal_multiplier is not None else Decimal(str(use.multiplier))
            for line_index, ingredient in enumerate(use.recipe.items):
                is_removed = (index, line_index) in excluded
                if is_removed != removed:
                    continue
                amount = Decimal(str(ingredient.quantity)) * (1 + Decimal(str(ingredient.waste_percent or 0)) / 100) * multiplier
                yield use, ingredient, amount


def required_decimal_ingredients(resolution: RecipeResolution) -> dict[str, Decimal]:
    required = {}
    for _, ingredient, amount in resolved_ingredients(resolution):
        required[ingredient.inventory_item_id] = required.get(ingredient.inventory_item_id, Decimal(0)) + amount
    return required

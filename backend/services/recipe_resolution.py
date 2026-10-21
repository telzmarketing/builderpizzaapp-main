"""One recipe calculation shared by availability, frozen CMV and stock."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re


def _component_key(value):
    return re.sub(r"\s+", "-", str(value).strip().casefold())


@dataclass(frozen=True)
class RecipeUse:
    recipe: object
    multiplier: float


@dataclass(frozen=True)
class RecipeResolution:
    uses: list[RecipeUse]
    missing: tuple[str, ...]


def resolve_recipes(item, recipes: dict[str, list]) -> RecipeResolution:
    quantity = float(item.quantity or 0)
    flavors = list(getattr(item, "flavors", None) or [])
    slots = Counter(flavor.product_id for flavor in flavors) or Counter({item.product_id: 1})
    division = sum(slots.values())
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
            occupied = count / division if role == "flavor" else 1.0
            reference = float(getattr(recipe, "reference_fraction", None) or 1.0)
            uses.append(RecipeUse(recipe, quantity * occupied / reference))
            matched_flavor = matched_flavor or role == "flavor" or (is_primary and not flavors)
        if not matched_flavor:
            missing.append(f"product:{product_id}")
    # Non-flavor components belong to the primary commercial product even
    # when a custom flavor selection does not contain that product.
    if item.product_id not in slots:
        primary = resolve_recipes(_PrimaryComponents(item), {item.product_id: [r for r in recipes.get(item.product_id, []) if (getattr(r, "component_role", None) or "flavor") != "flavor"]})
        uses.extend(primary.uses)
    primary_rows = recipes.get(item.product_id, [])
    used_recipes = [use.recipe for use in uses]
    for attr, selected in (("product_size_id", size), ("product_drink_variant_id", drink)):
        if selected and any(getattr(r, attr) for r in primary_rows) and not any(getattr(r, attr) == selected for r in used_recipes):
            missing.append(f"{attr}:{selected}")
    if any(r.product_crust_type_id for r in primary_rows):
        missing.extend(f"crust:{selected}" for selected in crusts if not any(r.product_crust_type_id == selected for r in used_recipes))
    if any(r.complement_key for r in primary_rows):
        missing.extend(f"addon:{selected}" for selected in addons if not any(r.complement_key and _component_key(r.complement_key) == selected for r in used_recipes))
    return RecipeResolution(uses, tuple(missing))


class _PrimaryComponents:
    def __init__(self, item):
        self.__dict__.update({name: getattr(item, name, None) for name in ("quantity", "product_id", "selected_size_id", "selected_crust_type_id", "selected_border_id", "selected_drink_variant_id", "add_ons")})
        self.flavors = []


def required_ingredients(resolution: RecipeResolution) -> dict[str, float]:
    required = {}
    for use in resolution.uses:
        for ingredient in use.recipe.items:
            amount = float(ingredient.quantity) * (1 + float(ingredient.waste_percent or 0) / 100) * use.multiplier
            required[ingredient.inventory_item_id] = required.get(ingredient.inventory_item_id, 0.0) + amount
    return required

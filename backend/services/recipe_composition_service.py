"""Technical composition shared by admin preview and immutable order snapshots."""
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace
import hashlib
import uuid

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from backend.models.inventory import InventoryRecipeVersion, InventoryRecipeItem, InventoryItem
from backend.models.product import Product
from backend.services.inventory_foundation_service import InventoryFoundationService, FoundationConflict, FoundationInvalid, output
from backend.services.recipe_details import normalize_recipe_line
from backend.services.recipe_resolution import resolve_recipes, resolved_ingredients, required_decimal_ingredients


def qstring(value):
    return format(Decimal(value).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP), "f")


def composition_for_item(item, recipes, products):
    resolution = resolve_recipes(item, recipes)
    # Quantize the shared ingredient total once, then allocate its micro-units.
    # Rounding every flavor separately can otherwise display more than stock
    # consumes (e.g. three thirds of the same herb). Largest remainders retain
    # nonnegative quantities; stable domain IDs break ties, not query order.
    from decimal import ROUND_DOWN, localcontext
    quantum = Decimal("0.000001")
    raw_entries = list(resolved_ingredients(resolution))
    with localcontext() as context:
        context.prec = 60
        totals = required_decimal_ingredients(resolution)
        allocated = [amount.quantize(quantum, rounding=ROUND_DOWN) for _, _, amount in raw_entries]
        groups = {}
        for index, (_, line, _) in enumerate(raw_entries):
            groups.setdefault(line.inventory_item_id, []).append(index)
        for inventory_item_id, indexes in groups.items():
            target = totals[inventory_item_id].quantize(quantum, rounding=ROUND_HALF_UP)
            remaining = int((target - sum((allocated[index] for index in indexes), Decimal(0))) / quantum)
            def priority(index):
                use, line, amount = raw_entries[index]
                return (-(amount - allocated[index]), str(use.recipe.product_id), str(use.recipe.id),
                        int(getattr(line, "position", 0) or 0), str(getattr(line, "id", line.inventory_item_id)), index)
            for index in sorted(indexes, key=priority)[:remaining]:
                allocated[index] += quantum
            totals[inventory_item_id] = target
    def ingredient(use, line, amount):
        inventory_item = getattr(line, "inventory_item", None)
        unit = getattr(inventory_item, "unit", None)
        return {"inventory_item_id": line.inventory_item_id,
                "name": inventory_item.name if inventory_item else line.inventory_item_id,
                "quantity": format(amount, ".6f"), "unit_id": getattr(line, "unit_id", None) or getattr(inventory_item, "unit_id", None),
                "unit_symbol": unit.symbol if unit else None, "recipe_version_id": use.recipe.id,
                "component_role": getattr(use.recipe, "component_role", None) or "flavor",
                "scope_product_id": use.recipe.product_id, "position": getattr(line, "position", 0),
                "waste_percent": format(Decimal(str(line.waste_percent or 0)), "f")}
    entries = [ingredient(use, line, allocated[index]) for index, (use, line, _) in enumerate(raw_entries)]
    removed = [ingredient(use, line, Decimal(0)) for use, line, amount in resolved_ingredients(resolution, removed=True)]
    consolidated = []
    for item_id, amount in totals.items():
        template = next(row for row in entries if row["inventory_item_id"] == item_id)
        consolidated.append({**template, "quantity": format(amount, ".6f"), "recipe_version_id": None,
                             "component_role": "consolidated", "scope_product_id": None, "waste_percent": "0"})
    slots = list(getattr(item, "flavors", None) or [])
    weights = {}
    if slots:
        explicit = all(getattr(flavor, "fraction", None) is not None for flavor in slots)
        for flavor in slots:
            weights[flavor.product_id] = weights.get(flavor.product_id, Decimal(0)) + (Decimal(str(flavor.fraction)) if explicit else Decimal(1) / len(slots))
    else:
        weights[item.product_id] = Decimal(1)
    methods, seen = [], set()
    for use in resolution.uses:
        if use.recipe.id in seen:
            continue
        seen.add(use.recipe.id)
        methods.append({"recipe_version_id": use.recipe.id, "instructions": getattr(use.recipe, "instructions", None),
                        "preparation_steps": list(getattr(use.recipe, "preparation_steps", None) or []),
                        "reference_image_url": getattr(use.recipe, "reference_image_url", None)})
    return {"product_id": item.product_id, "quantity": int(item.quantity), "complete": not resolution.missing,
            "missing": list(resolution.missing), "recipe_version_ids": list(dict.fromkeys(use.recipe.id for use in resolution.uses)),
            "common_components": [row for row in entries if row["component_role"] != "flavor"],
            "flavors": [{"product_id": product_id, "name": products[product_id].name if product_id in products else product_id,
                         "fraction": format(weight, "f"), "ingredients": [row for row in entries if row["component_role"] == "flavor" and row["scope_product_id"] == product_id]}
                        for product_id, weight in weights.items()],
            "ingredients": consolidated, "removed_ingredients": removed,
            "substitutions": [change.model_dump() if hasattr(change, "model_dump") else change for change in (getattr(item, "customizations", None) or [])
                              if (change.action if hasattr(change, "action") else change.get("action")) == "substitute"],
            "methods": methods, "notes": getattr(item, "notes", None)}


class RecipeCompositionService(InventoryFoundationService):
    def __init__(self, db, tenant_id, actor_id, tenant_context=None):
        super().__init__(db, tenant_id, actor_id, tenant_context)
        self.tenant_context = tenant_context

    def _recipes(self, product_ids, *, active=True):
        query = self._query(InventoryRecipeVersion).options(
            joinedload(InventoryRecipeVersion.items).joinedload(InventoryRecipeItem.inventory_item).joinedload(InventoryItem.unit),
            joinedload(InventoryRecipeVersion.product_size),
        ).filter(InventoryRecipeVersion.product_id.in_(product_ids))
        if active:
            query = query.filter(InventoryRecipeVersion.active.is_(True))
        rows = query.order_by(InventoryRecipeVersion.version_number.desc()).all()
        grouped = {}
        for recipe in rows:
            grouped.setdefault(recipe.product_id, []).append(recipe)
        return grouped

    def list_recipes(self, product_id):
        self._get(Product, product_id)
        rows = self._recipes([product_id], active=False).get(product_id, [])
        return {"items": [self.serialize_recipe(row) for row in rows],
                "latest_version": max((row.version_number for row in rows), default=0), "next_cursor": None}

    def serialize_recipe(self, row):
        data = {name: getattr(row, name) for name in ("id", "product_id", "version_number", "component_role", "reference_fraction",
            "product_size_id", "product_crust_type_id", "product_drink_variant_id", "complement_key", "complement_name", "active", "notes",
            "instructions", "preparation_steps", "reference_image_url", "created_at")}
        data["preparation_steps"] = data["preparation_steps"] or []
        data["items"] = [{**{name: getattr(line, name) for name in ("id", "inventory_item_id", "quantity", "unit_id", "entered_quantity",
            "entered_unit_id", "conversion_factor_snapshot", "position", "waste_percent", "notes", "public_name", "show_public")},
            "inventory_item_name": line.inventory_item.name, "unit_symbol": line.inventory_item.unit.symbol if line.inventory_item.unit else None}
            for line in row.items]
        return output(data)

    def publish(self, product_id, body, key, recipe_id=None):
        def execute(operation):
            product = self._get(Product, product_id, lock=True)
            from backend.services.inventory_service import InventoryService
            legacy = InventoryService(self.db, self.tenant_id, self.tenant_context, actor_id=self.actor_id)
            data = body.model_dump(exclude={"expected_version", "items"})
            lines = [line.model_dump() for line in body.items]
            legacy._validate_recipe_refs(product_id, data, lines)
            latest = self._query(InventoryRecipeVersion).filter(InventoryRecipeVersion.product_id == product_id).with_entities(func.max(InventoryRecipeVersion.version_number)).scalar() or 0
            old = None
            if recipe_id:
                old = self._get(InventoryRecipeVersion, recipe_id)
                if old.product_id != product_id or not old.active or old.version_number != body.expected_version:
                    raise FoundationConflict("Versao de receita substituida nao esta vigente.", code="VersionConflict")
            elif latest != body.expected_version:
                raise FoundationConflict("Historico de receita mudou; recarregue.", code="VersionConflict")
            from backend.services.recipe_image_service import RecipeImageService
            data["reference_image_url"] = RecipeImageService(self.db, self.tenant_id, self.actor_id).validate_reference(data.get("reference_image_url"))
            self._lock_items(line["inventory_item_id"] for line in lines)
            unit_ids = [unit for line in lines for unit in (line.get("unit_id"), line.get("entered_unit_id")) if unit]
            unit_ids += [self._get(InventoryItem, line["inventory_item_id"]).unit_id for line in lines]
            self._lock_units(unit_ids)
            for line in lines:
                if not line.get("unit_id"):
                    line["unit_id"] = self._get(InventoryItem, line["inventory_item_id"]).unit_id
            normalized = [normalize_recipe_line(self.db, self.tenant_id, line) for line in lines]
            if old:
                old.active = False
            if data["active"]:
                legacy._deactivate_matching_recipe_scope(product_id, data)
            recipe = InventoryRecipeVersion(id=str(uuid.uuid4()), tenant_id=self.tenant_id, product_id=product_id, version_number=latest+1, **data)
            self.db.add(recipe)
            for line in normalized:
                self.db.add(InventoryRecipeItem(id=str(uuid.uuid4()), tenant_id=self.tenant_id, recipe_id=recipe.id, **line))
            self.db.flush()
            self.db.expire(recipe, ["items"])
            return self.serialize_recipe(recipe)
        scope = f"products/{product_id}/recipes" + (f"/{recipe_id}" if recipe_id else "")
        return self._command("recipes:" + hashlib.sha256(scope.encode()).hexdigest(), key, body, "recipe_publication",
                             hashlib.sha256(f"{scope}:{key}".encode()).hexdigest(), execute)

    def archive(self, product_id, recipe_id, body, key):
        def execute(operation):
            self._get(Product, product_id, lock=True)
            recipe = self._get(InventoryRecipeVersion, recipe_id)
            if recipe.product_id != product_id:
                from backend.services.inventory_foundation_service import FoundationNotFound
                raise FoundationNotFound("Receita nao encontrada neste produto.")
            if recipe.version_number != body.expected_version or not recipe.active:
                raise FoundationConflict("Versao nao esta vigente.", code="VersionConflict")
            recipe.active = False
            self.db.flush()
            return self.serialize_recipe(recipe)
        return self._command(f"products/{product_id}/recipes/{recipe_id}/archive", key, body, "recipe_archive", f"{recipe_id}:{body.expected_version}", execute)

    def preview(self, body):
        product_ids = list({body.product_id, *[flavor.product_id for flavor in body.flavors]})
        products = {product_id: self._get(Product, product_id) for product_id in product_ids}
        product = products[body.product_id]
        from backend.models.product import ProductSize, ProductCrustType, ProductDrinkVariant
        for attr, model in (("selected_size_id", ProductSize), ("selected_crust_type_id", ProductCrustType), ("selected_border_id", ProductCrustType), ("selected_drink_variant_id", ProductDrinkVariant)):
            selected = getattr(body, attr)
            if selected and self._get(model, selected).product_id != product.id:
                raise FoundationInvalid("Opcao nao pertence ao produto.")
        item = SimpleNamespace(**body.model_dump(exclude={"flavors", "customizations"}),
            flavors=[SimpleNamespace(**flavor.model_dump()) for flavor in body.flavors],
            customizations=[change.model_dump() for change in body.customizations],
            selected_size=self._get(ProductSize, body.selected_size_id).label if body.selected_size_id else None)
        return composition_for_item(item, self._recipes(product_ids), products)

    def public_ingredients(self, product_id):
        from backend.services.product_catalog_service import assert_public_product
        assert_public_product(self._get(Product, product_id))
        names = []
        for recipe in self._recipes([product_id]).get(product_id, []):
            for line in recipe.items:
                if line.show_public and line.public_name and line.public_name not in names:
                    names.append(line.public_name)
        return {"ingredients": names}

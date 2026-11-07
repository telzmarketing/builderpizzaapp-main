"""Backward-compatible entry point for recipe-line normalization."""

from backend.services.recipe_supply_resolver import resolve_recipe_line


def normalize_recipe_line(db, tenant_id, values):
    return resolve_recipe_line(db, tenant_id, values)

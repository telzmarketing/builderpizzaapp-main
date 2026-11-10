import type { InventoryPortionConfig, PreparationRecipe } from "./api";
import { formatQuantity } from "./formatQuantity";

type PortionLabelConfig = Pick<InventoryPortionConfig, "source_item_name" | "portion_weight" | "unit_symbol" | "size">;

export function formatPortionTitle(config: PortionLabelConfig | null | undefined, fallback: string | null | undefined) {
  if (!config) return fallback || "Produto porcionado";
  const source = config.source_item_name || fallback || "Produto porcionado";
  return `${source} - porção ${formatQuantity(config.portion_weight)} ${config.unit_symbol || "GR"}${config.size ? ` - ${config.size}` : ""}`;
}

export function formatRequestedPortions(value: string | number | null | undefined) {
  return `${formatQuantity(value, "0")} porções`;
}

export function formatPortionIngredient(config: Pick<InventoryPortionConfig, "portion_weight" | "unit_symbol"> | null | undefined, fallbackQuantity: string | number | null | undefined, fallbackUnit: string | null | undefined) {
  if (config) return `${formatQuantity(config.portion_weight, "0")} ${config.unit_symbol || "GR"}`;
  return `${formatQuantity(fallbackQuantity, "0")}${fallbackUnit ? ` ${fallbackUnit}` : ""}`;
}

export function resolvePreparationPortionConfig(recipe: Pick<PreparationRecipe, "output_item_id" | "ingredients">, configs: InventoryPortionConfig[]) {
  return configs.find((config) => config.output_item_id === recipe.output_item_id)
    || configs.find((config) => recipe.ingredients.some((ingredient) => ingredient.inventory_item_id === config.source_item_id));
}

import type { ApiProduct } from "./api";

export type ProductCardAction = "direct" | "configure";

const active = <T extends { active: boolean }>(items?: T[]) => (items ?? []).some((item) => item.active);

/**
 * Cards may only quick-add products whose catalog contract proves that no
 * configuration is needed. Missing optional configuration data is safe for
 * simple non-pizza products; any configuration that is present forces the
 * canonical Product configurator.
 */
export function getProductCardAction(product: ApiProduct): ProductCardAction {
  if (product.inventory_available === false) return "configure";
  if (product.promotion_applied) return "configure";
  if (!product.product_type || product.product_type === "pizza") return "configure";
  if (active(product.sizes) || active(product.crust_types) || active(product.drink_variants)) return "configure";
  if ((product.option_groups ?? []).some((group) => group.active)) return "configure";
  return "direct";
}

import type { ApiProductCategory } from "@/lib/api";
import { sortCategoryNamesByCatalogOrder } from "@/lib/catalogOrdering";

export const PROMO_LABEL = "Promoções";
// A distinct key prevents a real category named "Todos" from becoming a catch-all.
export const ALL_PRODUCTS_CATEGORY = Symbol("home-all-products");
export type HomeCatalogCategory = string | typeof ALL_PRODUCTS_CATEGORY;
type HomeCatalogProduct = {
  active: boolean;
  category?: string | null;
  subcategory?: string | null;
  promotion_applied?: boolean;
};

export function normalizeHomeCategory(value?: string | null) {
  return (value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

export function productMatchesHomeCategory(product: HomeCatalogProduct, category: HomeCatalogCategory) {
  if (category === ALL_PRODUCTS_CATEGORY) return true;
  if (category === PROMO_LABEL) return !!product.promotion_applied;
  return [product.subcategory, product.category]
    .map(normalizeHomeCategory)
    .filter(Boolean)
    .includes(normalizeHomeCategory(category));
}

export function getHomeCatalogCategories(
  products: HomeCatalogProduct[],
  categories: ApiProductCategory[],
): HomeCatalogCategory[] {
  const activeProducts = products.filter((product) => product.active);
  const names = [...new Set(activeProducts
    .map((product) => product.subcategory?.trim() || product.category?.trim())
    .filter((name): name is string => !!name))];
  const hasUncategorized = activeProducts.some((product) => (
    !normalizeHomeCategory(product.category) && !normalizeHomeCategory(product.subcategory)
  ));
  const navigation: HomeCatalogCategory[] = [];
  if (hasUncategorized) navigation.push(ALL_PRODUCTS_CATEGORY);
  if (activeProducts.some((product) => product.promotion_applied)) navigation.push(PROMO_LABEL);
  navigation.push(...sortCategoryNamesByCatalogOrder(names, categories));
  return navigation;
}

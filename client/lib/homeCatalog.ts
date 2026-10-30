import type { ApiProductCategory } from "@/lib/api";
import { sortCategoryNamesByCatalogOrder } from "@/lib/catalogOrdering";

export const PROMO_LABEL = "Promoções";
// A distinct key prevents a real category named "Todos" from becoming a catch-all.
export const ALL_PRODUCTS_CATEGORY = Symbol("home-all-products");
export type HomeCatalogCategory = string | typeof ALL_PRODUCTS_CATEGORY;
type HomeCatalogProduct = {
  active: boolean;
  name?: string | null;
  category?: string | null;
  category_id?: string | null;
  subcategory?: string | null;
  subcategory_id?: string | null;
  product_type?: string | null;
  promotion_applied?: boolean;
};

export function normalizeHomeCategory(value?: string | null) {
  return (value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();
}

export function getHomeCatalogParentName(
  product: HomeCatalogProduct,
  categories: ApiProductCategory[] = [],
) {
  const category = product.category_id
    ? categories.find((item) => item.id === product.category_id)
    : undefined;
  const subcategory = product.subcategory_id
    ? categories.find((item) => item.id === product.subcategory_id)
    : undefined;
  const parent = subcategory?.parent_id
    ? categories.find((item) => item.id === subcategory.parent_id)
    : category?.parent_id
      ? categories.find((item) => item.id === category.parent_id)
      : category;
  return (parent?.name || product.category || product.subcategory || "").trim();
}

export function getHomeCatalogSubcategories(
  products: HomeCatalogProduct[],
  categories: ApiProductCategory[],
  parentName: string,
) {
  const parent = categories.find(
    (item) => !item.parent_id && normalizeHomeCategory(item.name) === normalizeHomeCategory(parentName),
  );
  const childNames = categories
    .filter((item) => item.active && item.parent_id === parent?.id)
    .map((item) => item.name.trim());
  const productNames = products
    .filter((product) => normalizeHomeCategory(getHomeCatalogParentName(product, categories)) === normalizeHomeCategory(parentName))
    .map((product) => product.subcategory?.trim())
    .filter((name): name is string => !!name);
  return sortCategoryNamesByCatalogOrder(
    [...new Set([...childNames, ...productNames])],
    categories.filter((item) => item.parent_id === parent?.id),
  );
}

export function productMatchesHomeSubcategory(product: HomeCatalogProduct, subcategory: string) {
  return normalizeHomeCategory(product.subcategory) === normalizeHomeCategory(subcategory);
}

export function productMatchesHomeCategory(
  product: HomeCatalogProduct,
  category: HomeCatalogCategory,
  categories: ApiProductCategory[] = [],
) {
  if (category === ALL_PRODUCTS_CATEGORY) return true;
  if (category === PROMO_LABEL) return !!product.promotion_applied;
  return normalizeHomeCategory(getHomeCatalogParentName(product, categories)) === normalizeHomeCategory(category);
}

export function getHomeCatalogCategories(
  products: HomeCatalogProduct[],
  categories: ApiProductCategory[],
): HomeCatalogCategory[] {
  const activeProducts = products.filter((product) => product.active);
  const names = [...new Set(activeProducts
    .map((product) => getHomeCatalogParentName(product, categories))
    .filter((name): name is string => !!name))];
  const hasUncategorized = activeProducts.some((product) => (
    !normalizeHomeCategory(getHomeCatalogParentName(product, categories))
  ));
  const navigation: HomeCatalogCategory[] = [];
  if (hasUncategorized) navigation.push(ALL_PRODUCTS_CATEGORY);
  if (activeProducts.some((product) => product.promotion_applied)) navigation.push(PROMO_LABEL);
  navigation.push(...sortCategoryNamesByCatalogOrder(
    names,
    categories.filter((category) => !category.parent_id),
  ));
  return navigation;
}

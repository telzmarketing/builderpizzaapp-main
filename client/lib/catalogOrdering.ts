import type { ApiProduct, ApiProductCategory } from "@/lib/api";

function normalized(value: string) {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLowerCase();
}

/** Stable commercial navigation order shared by storefront and backoffice. */
export function sortCommercialCategoryNames(names: string[]) {
  const priority = new Map([
    ["pizzas", 0],
    ["pizza", 0],
    ["bebidas", 1],
    ["bebida", 1],
  ]);
  return [...names].sort((a, b) => {
    const aPriority = priority.get(normalized(a));
    const bPriority = priority.get(normalized(b));
    if (aPriority !== undefined || bPriority !== undefined) {
      if (aPriority === undefined) return 2;
      if (bPriority === undefined) return -2;
      if (aPriority !== bPriority) return aPriority - bPriority;
    }
    return a.localeCompare(b, "pt-BR");
  });
}

/** Category tabs for PDV and manual orders: commercial categories first, catch-all last. */
export function getCommercialCategoryTabs(names: string[]) {
  return [...sortCommercialCategoryNames(names), ""];
}

/** Selects the first category that actually contains the preferred product type. */
export function getPreferredInitialCategory(
  products: Array<Pick<ApiProduct, "category" | "product_type">>,
  preferredProductType: string,
) {
  const preferred = normalized(preferredProductType);
  const matchingCategories = products
    .filter((product) => {
      const productType = normalized(product.product_type || "");
      const category = normalized(product.category || "");
      return productType === preferred || category.includes(preferred);
    })
    .map((product) => product.category)
    .filter((category): category is string => !!category?.trim());

  return sortCommercialCategoryNames([...new Set(matchingCategories)])[0] || "";
}

export function sortCategoryNamesByCatalogOrder(
  names: string[],
  categories: ApiProductCategory[],
) {
  const orderedNames = new Map<string, number>();

  [...categories]
    .filter((category) => category.active)
    .sort((a, b) => {
      if (a.sort_order !== b.sort_order) return a.sort_order - b.sort_order;
      return a.name.localeCompare(b.name);
    })
    .forEach((category, index) => {
      orderedNames.set(category.name.trim().toLowerCase(), index);
    });

  return [...names].sort((a, b) => {
    const aOrder = orderedNames.get(a.trim().toLowerCase());
    const bOrder = orderedNames.get(b.trim().toLowerCase());
    if (aOrder !== undefined && bOrder !== undefined) return aOrder - bOrder;
    if (aOrder !== undefined) return -1;
    if (bOrder !== undefined) return 1;
    return sortCommercialCategoryNames([a, b])[0] === a ? -1 : 1;
  });
}

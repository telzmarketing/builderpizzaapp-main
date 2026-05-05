import type { ApiProductCategory } from "@/lib/api";

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
    return a.localeCompare(b);
  });
}

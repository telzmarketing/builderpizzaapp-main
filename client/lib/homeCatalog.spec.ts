import { describe, expect, it } from "vitest";
import type { ApiProductCategory } from "./api";
import {
  ALL_PRODUCTS_CATEGORY,
  PROMO_LABEL,
  getHomeCatalogCategories,
  productMatchesHomeCategory,
  getHomeCatalogParentName,
  getHomeCatalogSubcategories,
  productMatchesHomeSubcategory,
} from "./homeCatalog";

describe("home catalog navigation", () => {
  it("shows uncategorized active products instead of an empty home", () => {
    const products = [
      { active: true, category: null, subcategory: null },
      { active: true, category: " ", subcategory: "" },
    ];
    const categories = getHomeCatalogCategories(products, []);
    expect(categories).toEqual([ALL_PRODUCTS_CATEGORY]);
    expect(products.filter((product) => productMatchesHomeCategory(product, categories[0])))
      .toEqual(products);
  });

  it("keeps mixed catalogs reachable and preserves specific category and promo filters", () => {
    const products = [
      { active: true, category: null },
      { active: true, category: "Pizzas", subcategory: "Clássicas", promotion_applied: true },
      { active: true, category: "Bebidas" },
    ];
    const categories = getHomeCatalogCategories(products, []);
    expect(categories).toEqual([ALL_PRODUCTS_CATEGORY, PROMO_LABEL, "Bebidas", "Pizzas"]);
    expect(products.filter((product) => productMatchesHomeCategory(product, ALL_PRODUCTS_CATEGORY)))
      .toHaveLength(3);
    expect(products.filter((product) => productMatchesHomeCategory(product, "pizzas")))
      .toEqual([products[1]]);
    expect(products.filter((product) => productMatchesHomeCategory(product, PROMO_LABEL)))
      .toEqual([products[1]]);
  });

  it("preserves configured category order and does not add Todos for a categorized catalog", () => {
    const products = [
      { active: true, category: "Pizzas" },
      { active: true, category: "Bebidas" },
      { active: false, category: null },
    ];
    const categories = [
      { name: "Pizzas", active: true, sort_order: 0 },
      { name: "Bebidas", active: true, sort_order: 1 },
    ] as ApiProductCategory[];
    expect(getHomeCatalogCategories(products, categories)).toEqual(["Pizzas", "Bebidas"]);
    expect(getHomeCatalogCategories([], [])).toEqual([]);
    expect(getHomeCatalogCategories([{ active: false }], [])).toEqual([]);
  });

  it("keeps a real category named Todos distinct from the fallback", () => {
    const namedProduct = { active: true, category: "Todos" };
    const uncategorizedProduct = { active: true };
    expect(getHomeCatalogCategories([namedProduct, uncategorizedProduct], []))
      .toEqual([ALL_PRODUCTS_CATEGORY, "Todos"]);
    expect(productMatchesHomeCategory(uncategorizedProduct, "Todos")).toBe(false);
    expect(productMatchesHomeCategory(namedProduct, "Todos")).toBe(true);
  });

  it("uses the available category when only one level is populated", () => {
    const products = [
      { active: true, category: null, subcategory: "Doces" },
      { active: true, category: "Pizzas", subcategory: " " },
    ];
    expect(getHomeCatalogCategories(products, [])).toEqual(["Doces", "Pizzas"]);
    expect(productMatchesHomeCategory(products[0], "Doces")).toBe(true);
    expect(productMatchesHomeCategory(products[1], "Pizzas")).toBe(true);
  });

  it("resolves parent categories and exposes subcategories separately", () => {
    const categories = [
      { id: "pizza", parent_id: null, name: "Pizzas", active: true, sort_order: 0 },
      { id: "classic", parent_id: "pizza", name: "Clássicas", active: true, sort_order: 0 },
      { id: "special", parent_id: "pizza", name: "Especiais", active: true, sort_order: 1 },
    ] as ApiProductCategory[];
    const products = [{ active: true, category: "Pizzas", category_id: "pizza", subcategory: "Clássicas", subcategory_id: "classic" }];
    expect(getHomeCatalogParentName(products[0], categories)).toBe("Pizzas");
    expect(getHomeCatalogSubcategories(products, categories, "Pizzas")).toEqual(["Clássicas", "Especiais"]);
    expect(productMatchesHomeSubcategory(products[0], "Clássicas")).toBe(true);
  });
});

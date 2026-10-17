import { describe, expect, it } from "vitest";
import type { ApiProductCategory } from "./api";
import {
  ALL_PRODUCTS_CATEGORY,
  PROMO_LABEL,
  getHomeCatalogCategories,
  productMatchesHomeCategory,
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
    expect(categories).toEqual([ALL_PRODUCTS_CATEGORY, PROMO_LABEL, "Bebidas", "Clássicas"]);
    expect(products.filter((product) => productMatchesHomeCategory(product, ALL_PRODUCTS_CATEGORY)))
      .toHaveLength(3);
    expect(products.filter((product) => productMatchesHomeCategory(product, "classicas")))
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
});

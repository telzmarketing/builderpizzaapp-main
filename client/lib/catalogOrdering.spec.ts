import { describe, expect, it } from "vitest";
import {
  getCommercialCategoryTabs,
  getPreferredInitialCategory,
  sortCommercialCategoryNames,
} from "./catalogOrdering";

describe("commercial category ordering", () => {
  it("keeps pizzas first, beverages second, and the catch-all tab last", () => {
    expect(getCommercialCategoryTabs(["Todos", "Bebidas", "Doces", "Pizzas"]))
      .toEqual(["Pizzas", "Bebidas", "Doces", "Todos", ""]);
  });

  it("recognizes singular and accented commercial names", () => {
    expect(sortCommercialCategoryNames(["Bebida", "Pizza", "Sobremesas"]))
      .toEqual(["Pizza", "Bebida", "Sobremesas"]);
  });

  it("selects pizzas initially even when beverages arrive first", () => {
    expect(getPreferredInitialCategory([
      { category: "Bebidas", product_type: "drink" },
      { category: "Pizzas", product_type: "pizza" },
    ], "pizza")).toBe("Pizzas");
  });

  it("uses a custom category containing pizza products", () => {
    expect(getPreferredInitialCategory([
      { category: "Refrigerantes", product_type: "drink" },
      { category: "Clássicas", product_type: "pizza" },
    ], "pizza")).toBe("Clássicas");
  });

  it("keeps the catch-all selection when there are no pizza products", () => {
    expect(getPreferredInitialCategory([
      { category: "Bebidas", product_type: "drink" },
    ], "pizza")).toBe("");
  });
});

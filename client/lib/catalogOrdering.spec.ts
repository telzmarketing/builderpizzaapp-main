import { describe, expect, it } from "vitest";
import { getCommercialCategoryTabs, sortCommercialCategoryNames } from "./catalogOrdering";

describe("commercial category ordering", () => {
  it("keeps pizzas first, beverages second, and the catch-all tab last", () => {
    expect(getCommercialCategoryTabs(["Todos", "Bebidas", "Doces", "Pizzas"]))
      .toEqual(["Pizzas", "Bebidas", "Doces", "Todos", ""]);
  });

  it("recognizes singular and accented commercial names", () => {
    expect(sortCommercialCategoryNames(["Bebida", "Pizza", "Sobremesas"]))
      .toEqual(["Pizza", "Bebida", "Sobremesas"]);
  });
});

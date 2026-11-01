import { describe, expect, it } from "vitest";
import type { ApiProduct } from "./api";
import { getProductCardAction } from "./productCardAction";

const product = (overrides: Partial<ApiProduct> = {}) => ({
  id: "product", name: "Produto", description: "", price: 10, icon: "", category: null,
  subcategory: null, product_type: "other", rating: 5, active: true,
  created_at: "", updated_at: "", ...overrides,
} as ApiProduct);

describe("getProductCardAction", () => {
  it("allows direct add for an available simple product", () => {
    expect(getProductCardAction(product())).toBe("direct");
  });

  it.each([
    { product_type: "pizza" },
    { product_type: null },
    { sizes: [{ active: true }] },
    { crust_types: [{ active: true }] },
    { drink_variants: [{ active: true }] },
    { option_groups: [{ active: true }] },
    { promotion_applied: true },
  ])("requires configuration for %j", (overrides) => {
    expect(getProductCardAction(product(overrides as Partial<ApiProduct>))).toBe("configure");
  });

  it("does not quick-add unavailable products", () => {
    expect(getProductCardAction(product({ inventory_available: false }))).toBe("configure");
  });
});

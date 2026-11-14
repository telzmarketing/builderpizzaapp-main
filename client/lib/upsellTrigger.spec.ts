import { describe, expect, it } from "vitest";
import { applyUpsellTrigger, getUpsellTriggerMode } from "./upsellTrigger";
import type { ApiUpsellInput } from "./api";

const base: ApiUpsellInput = {
  internal_name: "Teste",
  product_id: "offer",
  main_text: "Oferta",
  trigger_type: "product_in_cart",
  trigger_product_id: "product",
  trigger_category: "Pizzas",
};

describe("upsell trigger selection", () => {
  it("serializes a product-in-cart trigger", () => {
    expect(applyUpsellTrigger(base, "product", "product")).toMatchObject({
      trigger_type: "product_in_cart",
      trigger_product_id: "product",
      trigger_category: null,
    });
  });

  it("serializes a category trigger and clears the product trigger", () => {
    expect(applyUpsellTrigger(base, "category", "Pizzas")).toMatchObject({
      trigger_type: "category",
      trigger_product_id: null,
      trigger_category: "Pizzas",
    });
  });

  it("detects the mode when editing persisted rules", () => {
    expect(getUpsellTriggerMode({ trigger_type: "category", trigger_product_id: null, trigger_category: "Pizzas" })).toBe("category");
    expect(getUpsellTriggerMode({ trigger_type: "product_in_cart", trigger_product_id: "product", trigger_category: null })).toBe("product");
    expect(getUpsellTriggerMode({ trigger_type: "min_value", trigger_product_id: null, trigger_category: null })).toBe("any");
  });
});

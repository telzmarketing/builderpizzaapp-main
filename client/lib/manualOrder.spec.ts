import { describe, expect, it } from "vitest";
import { canCreateManualOrder, configuredManualLine } from "./manualOrder";
import type { ApiEffectivePermissions, ApiProduct } from "./api";

describe("operator order adaptation", () => {
  it("uses create permission independently of editing existing orders", () => {
    expect(canCreateManualOrder(null)).toBe(false);
    expect(canCreateManualOrder({ is_master: false, modules: { pedidos: { edit: true } } } as ApiEffectivePermissions)).toBe(false);
    expect(canCreateManualOrder({ is_master: false, modules: { pedidos: { create: true } } } as ApiEffectivePermissions)).toBe(true);
  });

  it("preserves configured fractions, option identities and unit quote without recalculating prices", () => {
    const product = { id: "pizza", name: "Pizza", price: 99 } as ApiProduct;
    const line = configuredManualLine([product, 2, "Grande", ["extra"], [
      { productId: "pizza", name: "Muçarela", price: 50, icon: "🍕" },
      { productId: "second", name: "Calabresa", price: 60, icon: "🍕" },
    ], 2, 57.5, "Sem cebola", { id: "dough", name: "Massa", priceAddition: 1 }, null, "large", undefined, { id: "border", name: "Borda", priceAddition: 2 }], "line");
    expect(line.item.quantity).toBe(2);
    expect(line.item.final_price).toBe(57.5);
    expect(line.item.flavor_division).toBe(2);
    expect(line.item.flavors.map((flavor) => flavor.product_id)).toEqual(["pizza", "second"]);
    expect(line.item.selected_size_id).toBe("large");
    expect(line.item.selected_crust_type_id).toBe("dough");
    expect(line.item.selected_border_id).toBe("border");
    expect(line.item.notes).toBe("Sem cebola");
  });
});

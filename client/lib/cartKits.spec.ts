import { describe, expect, it } from "vitest";
import { cartItemIdsForRemoval, groupCartItems } from "./cartKits";
import type { CartItem } from "@/context/AppContext";

function item(cartItemId: string, productId: string, kit?: CartItem["kit"]): CartItem {
  return {
    cartItemId,
    productId,
    quantity: 1,
    selectedSize: "M",
    selectedAddOns: [],
    productData: { id: productId, name: productId, price: 10, icon: "🍕" } as CartItem["productData"],
    flavorDivision: 1,
    flavors: [],
    finalPrice: 10,
    selectedOptions: [],
    kit,
  };
}

const kit = {
  instanceId: "instance-1",
  id: "kit-1",
  name: "Combo Família",
  components: [
    { productId: "pizza", name: "Pizza", icon: "🍕", quantity: 1 },
    { productId: "drink", name: "Refrigerante", icon: "🥤", quantity: 2 },
  ],
};

describe("cart promotional kits", () => {
  it("groups one kit instance while preserving normal product rows", () => {
    const groups = groupCartItems([item("normal", "salad"), item("pizza-row", "pizza", kit), item("drink-row", "drink", kit)]);

    expect(groups).toHaveLength(2);
    expect(groups[0]).toMatchObject({ kind: "item", item: { cartItemId: "normal" } });
    expect(groups[1]).toMatchObject({ kind: "kit", kit: { name: "Combo Família" } });
    expect(groups[1].kind === "kit" && groups[1].items.map((entry) => entry.cartItemId)).toEqual(["pizza-row", "drink-row"]);
  });

  it("removes every component of a kit instance, but only the requested normal item otherwise", () => {
    const items = [item("normal", "salad"), item("pizza-row", "pizza", kit), item("drink-row", "drink", kit)];

    expect(cartItemIdsForRemoval(items, "drink-row")).toEqual(["pizza-row", "drink-row"]);
    expect(cartItemIdsForRemoval(items, "normal")).toEqual(["normal"]);
  });
});

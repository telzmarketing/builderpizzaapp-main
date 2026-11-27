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

  it("groups and removes a strategic offer as one commercial unit", () => {
    const strategicGroup = {
      instanceId: "offer-instance",
      name: "Black Friday",
      campaignVersion: 2,
      compositionRevision: 1,
      referenceType: "mixed_subcategories" as const,
      stepKey: "traditional:1",
    };
    const items = [
      { ...item("strategic-1", "pizza"), strategicOfferId: "offer-1", strategicGroup },
      { ...item("strategic-2", "special"), strategicOfferId: "offer-1", strategicGroup: { ...strategicGroup, stepKey: "special:1" } },
    ];

    const groups = groupCartItems(items);

    expect(groups).toHaveLength(1);
    expect(groups[0]).toMatchObject({ kind: "strategic", key: "strategic:offer-instance" });
    expect(cartItemIdsForRemoval(items, "strategic-2")).toEqual(["strategic-1", "strategic-2"]);
  });
});

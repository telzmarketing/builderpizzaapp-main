import { describe, expect, it } from "vitest";
import { addKitItemDraft, kitItemDraftsFromItems, removeKitItemDraft } from "./promotionalKitItems";

describe("promotional kit item drafts", () => {
  it("adds several different products and preserves quantities", () => {
    let items = addKitItemDraft([], "pizza", 2);
    items = addKitItemDraft(items, "refrigerante", 1);

    expect(items).toEqual([
      { product_id: "pizza", quantity: 2 },
      { product_id: "refrigerante", quantity: 1 },
    ]);
  });

  it("increments a product instead of creating duplicate rows", () => {
    expect(addKitItemDraft([{ product_id: "pizza", quantity: 2 }], "pizza", 3))
      .toEqual([{ product_id: "pizza", quantity: 5 }]);
  });

  it("loads existing items and removes only the selected draft row", () => {
    const loaded = kitItemDraftsFromItems([{ id: "item-1", product_id: "pizza", quantity: 2 }]);
    expect(removeKitItemDraft([...loaded, { product_id: "refrigerante", quantity: 1 }], 1))
      .toEqual(loaded);
  });
});

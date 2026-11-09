import { describe, expect, it } from "vitest";
import {
  buildPreparationAllocationDrafts,
  emptyPreparationRecipe,
  preparationAllocationPayload,
  validatePreparationAllocationDrafts,
} from "./PreparationOperationsPanel";
import type { FoundationLot, InventoryOverview, PreparationRecipe } from "@/lib/api";

const recipe: PreparationRecipe = {
  preparation_order_id: "order-1",
  recipe_version_id: "recipe-1",
  executable: true,
  output_item_id: "sauce",
  target_quantity: "10",
  output_unit_id: "kg",
  preparation_steps: [],
  ingredients: [
    { inventory_item_id: "tomato", inventory_item_name: "Tomate", quantity: "4.000000", unit_id: "kg", unit_symbol: "kg" },
    { inventory_item_id: "salt", inventory_item_name: "Sal", quantity: "0.100000", unit_id: "kg", unit_symbol: "kg" },
  ],
  warnings: [],
};

const inventory = {
  items: [
    { id: "tomato", name: "Tomate", default_location_id: "cold-room", active: true },
    { id: "salt", name: "Sal", default_location_id: "dry-store", active: true },
  ],
  locations: [
    { id: "cold-room", name: "Câmara fria", active: true },
    { id: "dry-store", name: "Despensa", active: true },
  ],
} as InventoryOverview;

const lots: FoundationLot[] = [{
  id: "lot-tomato",
  item_id: "tomato",
  location_id: "cold-room",
  lot_code: "T-001",
  status: "available",
  version: 1,
  received_at: "2026-11-07T10:00:00Z",
  expires_on: null,
  effective_expires_at: null,
}];

describe("PreparationOperationsPanel structured allocations", () => {
  it("keeps the technical sheet available as an empty pending sheet", () => {
    const empty = emptyPreparationRecipe({
      id: "order-empty",
      recipe_id: "missing-recipe",
      recipe_name: null,
      output_item_name: "Brócolis porcionado",
      output_unit_symbol: "GR",
      target_quantity: "20",
      produced_quantity: "0",
      lost_quantity: "0",
      discarded_quantity: "0",
      status: "waiting",
      version: 1,
      execution_id: null,
    });

    expect(empty.executable).toBe(false);
    expect(empty.ingredients).toEqual([]);
    expect(empty.warnings[0].code).toBe("missing_recipe");
    expect(empty.output_item_name).toBe("Brócolis porcionado");
  });

  it("builds one editable row per recipe ingredient using the item's default location", () => {
    const drafts = buildPreparationAllocationDrafts(recipe, inventory, lots);

    expect(drafts).toEqual([
      expect.objectContaining({ item_id: "tomato", unit_id: "kg", quantity: "4.000000", location_id: "cold-room", lot_id: null }),
      expect.objectContaining({ item_id: "salt", unit_id: "kg", quantity: "0.100000", location_id: "dry-store", lot_id: null }),
    ]);
  });

  it("serializes only the official backend allocation fields", () => {
    const drafts = buildPreparationAllocationDrafts(recipe, inventory, lots).map((draft) => ({ ...draft, lot_id: draft.item_id === "tomato" ? "lot-tomato" : null }));

    expect(preparationAllocationPayload(drafts)).toEqual([
      { item_id: "tomato", unit_id: "kg", quantity: "4.000000", location_id: "cold-room", lot_id: "lot-tomato" },
      { item_id: "salt", unit_id: "kg", quantity: "0.100000", location_id: "dry-store", lot_id: null },
    ]);
    expect(preparationAllocationPayload(drafts)[0]).not.toHaveProperty("ingredientIndex");
  });

  it("blocks incomplete structured allocations before sending the report", () => {
    const drafts = buildPreparationAllocationDrafts(recipe, inventory, lots);
    expect(validatePreparationAllocationDrafts(drafts)).toBeNull();
    expect(validatePreparationAllocationDrafts([{ ...drafts[0], location_id: "" }, drafts[1]])).toContain("local");
    expect(validatePreparationAllocationDrafts([{ ...drafts[0], quantity: "0" }, drafts[1]])).toContain("quantidades");
  });
});
